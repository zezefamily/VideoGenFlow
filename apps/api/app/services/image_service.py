"""图片生成服务(Phase 4,Phase 5 接入存储/任务抽象)。

基于火山引擎 ARK(豆包 Seedream)做链式生成:
- 第 1 镜文生图(text2image)
- 第 2~N 镜图生图(img2image),以上一镜成功图作参考 -> 画面/人物一致性

批量生成在后台任务里跑(DB 是真源),支持取消与单张重绘。
ARK 远端 URL 会过期,故下载后经 StorageBackend 落地(本地盘或 S3)。
"""

import asyncio
from typing import Optional

import httpx

from app.config import settings
from app.db import AsyncSessionLocal
from app.repositories import image_repo, storyboard_repo
from app.services import storage as storage_service
from app.services import task_runner

_ARK_URL = f"{settings.ark_base_url}/images/generations"

# 画面比例 -> 像素尺寸(2K 档,ARK 要求 >= 3,686,400 px)
_ASPECT_SIZES = {
    "1:1": "2048x2048",
    "4:3": "2304x1728",
    "3:4": "1728x2304",
    "16:9": "2848x1600",
    "9:16": "1600x2848",
}

# 已取消的分镜版本 id(运行中任务每镜前检查;进程内模式生效)
_cancelled: set[str] = set()


def _resolve_size(aspect_ratio: str) -> str:
    return _ASPECT_SIZES.get(aspect_ratio, "2048x2048")


def _build_prompt(visual: str, aspect_ratio: str, style: str) -> str:
    hint = {
        "9:16": "竖屏构图",
        "16:9": "横屏构图",
        "1:1": "方屏构图",
    }.get(aspect_ratio, "")
    parts = [style, visual]
    if hint:
        parts.append(hint)
    return ", ".join(p for p in parts if p)


def _storage_key(storyboard_version_id: str, shot_index: int) -> str:
    return f"{storyboard_version_id}/shot_{shot_index}.png"


async def _fetch_and_store(
    client: httpx.AsyncClient, url: str, key: str
) -> Optional[str]:
    """下载 ARK 图片字节并经存储后端落地,返回可访问路径(失败返回 None)。"""
    try:
        r = await client.get(url, timeout=60)
        if r.status_code != 200:
            return None
        return await storage_service.save(key, r.content)
    except Exception:
        return None


async def _call_ark(
    client: httpx.AsyncClient,
    prompt: str,
    size: str,
    reference_image: Optional[str] = None,
    max_retries: int = 2,
) -> dict:
    """返回 {"url": str|None, "error": str|None}。429 限流时短暂退避重试。"""
    if not settings.ark_api_key:
        return {"url": None, "error": "ARK_API_KEY 未配置"}

    body = {
        "model": settings.ark_image_model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ark_api_key}",
    }
    if reference_image:
        body["image"] = reference_image

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = await client.post(_ARK_URL, headers=headers, json=body, timeout=180)
        except httpx.TimeoutException:
            return {"url": None, "error": "ARK 请求超时(180s)"}
        except Exception as e:
            return {"url": None, "error": f"{type(e).__name__}: {e}"}

        if resp.status_code == 200:
            try:
                data = resp.json()
                images = data.get("data", [])
                url = images[0].get("url", "") if images else ""
                if not url:
                    return {"url": None, "error": "ARK 返回 URL 为空"}
                return {"url": url, "error": None}
            except Exception as e:
                return {"url": None, "error": f"解析 ARK 响应失败: {e}"}

        # 429 限流:短暂退避后重试(账号硬额度上限时不会成功,故只轻试)
        if resp.status_code == 429 and attempt < max_retries - 1:
            wait = 10 * (attempt + 1)
            last_err = f"ARK 429 限流,等待 {wait}s 重试({attempt+1}/{max_retries})"
            await asyncio.sleep(wait)
            continue

        return {
            "url": None,
            "error": f"ARK {resp.status_code}: {resp.text[:160]}",
        }
    return {"url": None, "error": last_err or "ARK 重试耗尽"}


async def start_generation(
    storyboard_artifact: dict,
    conversation_id: str,
    project_id: str,
    storyboard_version_id: str,
) -> list[dict]:
    """为激活分镜的每个镜头建 pending 图片记录,启动后台链式生成。

    返回初始图片 artifact 列表(全 pending)供立即回显。
    """
    shots = storyboard_artifact.get("shots", []) or []
    aspect_ratio = storyboard_artifact.get("aspect_ratio", "16:9")
    style = storyboard_artifact.get("style") or ""

    async with AsyncSessionLocal() as s:
        # 整批重新生成:物理删除旧图片记录(含历史 error/cancelled),避免累积
        await image_repo.delete_images_by_storyboard(s, storyboard_version_id)
        for i, sh in enumerate(shots, start=1):
            await image_repo.create_image(
                s,
                conversation_id=conversation_id,
                project_id=project_id,
                storyboard_version_id=storyboard_version_id,
                shot_index=i,
                status="pending",
                prompt=_build_prompt(sh.get("visual", ""), aspect_ratio, style),
            )
        images = await image_repo.list_images_by_storyboard(s, storyboard_version_id)

    # 启动后台任务(进程内或 Arq)
    _cancelled.discard(storyboard_version_id)
    await task_runner.submit(
        "image_generation",
        conversation_id=conversation_id,
        storyboard_version_id=storyboard_version_id,
        aspect_ratio=aspect_ratio,
    )

    return [image_repo.to_artifact_dict(img) for img in images]


async def run_generation_task(
    conversation_id: str, storyboard_version_id: str, aspect_ratio: str
) -> None:
    """后台链式生成:镜1文生图,镜2~N 以前镜为参考图生图。

    作为可注册任务(进程内 asyncio / Arq 共用)。
    """
    size = _resolve_size(aspect_ratio)
    prev_url: Optional[str] = None

    async with AsyncSessionLocal() as s:
        # 只处理 pending 的图,跳过历史 error/cancelled/done(避免重复处理旧记录)
        images = await image_repo.list_images_by_storyboard(s, storyboard_version_id, statuses=["pending"])

    async with httpx.AsyncClient() as client:
        for img in images:
            # 取消检查
            if storyboard_version_id in _cancelled:
                async with AsyncSessionLocal() as s:
                    await image_repo.update_image(
                        s, img.id, status="cancelled", error="用户取消"
                    )
                continue

            method = "img2image" if prev_url else "text2image"
            async with AsyncSessionLocal() as s:
                await image_repo.update_image(
                    s, img.id, status="generating", method=method
                )

            result = await _call_ark(
                client, prompt=img.prompt, size=size, reference_image=prev_url
            )

            # 取消检查:用户可能在 _call_ark 期间取消
            if storyboard_version_id in _cancelled:
                async with AsyncSessionLocal() as s:
                    await image_repo.update_image(
                        s, img.id, status="cancelled", error="用户取消"
                    )
                continue

            if result["error"]:
                # 若是图生图失败,兜底试一次纯文生图(参考图可能过期)
                if prev_url:
                    result = await _call_ark(
                        client, prompt=img.prompt, size=size, reference_image=None
                    )
                    method = "text2image"
                if result["error"]:
                    async with AsyncSessionLocal() as s:
                        await image_repo.update_image(
                            s, img.id, status="error", method=method, error=result["error"]
                        )
                    continue

            url = result["url"]
            key = _storage_key(storyboard_version_id, img.shot_index)
            web_path = await _fetch_and_store(client, url, key)

            async with AsyncSessionLocal() as s:
                await image_repo.update_image(
                    s,
                    img.id,
                    status="done",
                    method=method,
                    image_url=url,
                    local_path=web_path,
                    error=None,
                )
            prev_url = url  # 链式参考


# 注册为后台任务(供 task_runner 调度)
task_runner.register_task("image_generation", run_generation_task)


async def regenerate_single(image_id: str) -> Optional[dict]:
    """单张重绘:用前一镜的图为参考(若有),失败兜底文生图。"""
    async with AsyncSessionLocal() as s:
        img = await image_repo.get_image(s, image_id)
        if img is None:
            return None
        siblings = await image_repo.list_images_by_storyboard(
            s, img.storyboard_version_id
        )
        # 取原分镜的画面比例,保证重绘尺寸与批量生成一致
        sv = await storyboard_repo.get_storyboard(s, img.storyboard_version_id)
        aspect_ratio = sv.aspect_ratio if sv else "16:9"
        await image_repo.update_image(s, img.id, status="generating")

    # 找前一镜成功的图作参考
    prev_url = None
    for sb in siblings:
        if sb.shot_index < img.shot_index and sb.status == "done" and sb.image_url:
            prev_url = sb.image_url  # 取最近一个

    async with httpx.AsyncClient() as client:
        result = await _call_ark(
            client, prompt=img.prompt, size=_resolve_size(aspect_ratio), reference_image=prev_url
        )
        method = "img2image" if prev_url else "text2image"
        if result["error"] and prev_url:
            result = await _call_ark(
                client, prompt=img.prompt, size=_resolve_size(aspect_ratio), reference_image=None
            )
            method = "text2image"

        async with AsyncSessionLocal() as s:
            if result["error"]:
                updated = await image_repo.update_image(
                    s, img.id, status="error", method=method, error=result["error"]
                )
            else:
                url = result["url"]
                key = _storage_key(img.storyboard_version_id, img.shot_index)
                web_path = await _fetch_and_store(client, url, key)
                updated = await image_repo.update_image(
                    s,
                    img.id,
                    status="done",
                    method=method,
                    image_url=url,
                    local_path=web_path,
                    error=None,
                )

    return image_repo.to_artifact_dict(updated) if updated else None


async def cancel_generation(conversation_id: str) -> dict:
    """取消会话当前进行中的图片生成。"""
    async with AsyncSessionLocal() as s:
        images = await image_repo.list_images_by_conversation(s, conversation_id)
        sb_ids = {img.storyboard_version_id for img in images}
        for sb_id in sb_ids:
            _cancelled.add(sb_id)
        # DB 立即标 cancelled(pending/generating 的)
        for img in images:
            if img.status in ("pending", "generating"):
                await image_repo.update_image(
                    s, img.id, status="cancelled", error="用户取消"
                )
    return {"cancelled": len(sb_ids), "storyboards": list(sb_ids)}
