"""分镜图动态化：策略选择、预算确认、Seedance 任务与本地持久化。"""

import json
import math
from pathlib import Path

import httpx

from app.config import settings
from app.db import AsyncSessionLocal
from app.repositories import image_repo, project_repo, shot_video_repo, storyboard_repo
from app.services import ark_video_client, task_runner


def select_shots(shots: list[dict], strategy: str, custom: list[int]) -> list[int]:
    n = len(shots)
    if n == 0: return []
    if strategy == "all": return list(range(1, n + 1))
    if strategy == "custom": return sorted({i for i in custom if 1 <= i <= n})
    target = min(n, max(2, math.ceil(n / 3) + 1))
    selected = {1, n}
    candidates = []
    motion_words = ("冲", "跑", "转", "推", "拉", "移动", "撞", "爆", "落", "飞", "镜头", "特写")
    for i, shot in enumerate(shots[1:-1], 2):
        text = f"{shot.get('video_prompt','')} {shot.get('camera','')} {shot.get('title','')}"
        score = sum(1 for word in motion_words if word in text) + min(len(text) / 80, 1)
        score += 0.4 if all(abs(i - old) > 1 for old in selected) else 0
        candidates.append((score, i))
    for _, i in sorted(candidates, reverse=True):
        if len(selected) >= target: break
        selected.add(i)
    return sorted(selected)


async def plan(conversation_id: str, strategy: str, custom: list[int]) -> dict:
    async with AsyncSessionLocal() as s:
        project = await project_repo.get_conversation_project(s, conversation_id)
        if not project: raise ValueError("当前没有作品")
        sb = await storyboard_repo.get_active_storyboard(s, project.id)
        if not sb: raise ValueError("当前没有分镜")
        shots = json.loads(sb.shots_json or "[]")
    selected = select_shots(shots, strategy, custom)
    estimated_cost = sum(
        max(4, min(15, round(shots[index - 1].get("duration_sec", 5) or 5)))
        * settings.ark_video_cost_per_second
        for index in selected
    )
    return {"strategy": strategy, "selected_shots": selected, "estimated_cost": round(estimated_cost, 2)}


async def start(conversation_id: str, strategy: str, custom: list[int], confirmed: bool) -> dict:
    info = await plan(conversation_id, strategy, custom)
    if not confirmed: raise ValueError(f"需要确认预计费用 ¥{info['estimated_cost']:.2f}")
    async with AsyncSessionLocal() as s:
        project = await project_repo.get_conversation_project(s, conversation_id)
        sb = await storyboard_repo.get_active_storyboard(s, project.id)
        shots = json.loads(sb.shots_json or "[]")
        images = await image_repo.list_images_by_storyboard(s, sb.id, statuses=["done"])
        image_map = {img.shot_index: img for img in images}
        existing = {row.shot_index: row for row in await shot_video_repo.list_by_storyboard(s, sb.id)}
        assets = []
        for index in info["selected_shots"]:
            shot = shots[index - 1]; image = image_map.get(index)
            duration_sec = max(4, min(15, round(shot.get("duration_sec", 5) or 5)))
            if not image: raise ValueError(f"第 {index} 镜缺少已完成分镜图")
            old = existing.get(index)
            if old and old.video_prompt == shot.get("video_prompt", ""):
                assets.append(old)
                continue
            if old and old.status in {"pending", "generating"}:
                raise ValueError(f"第 {index} 镜正在生成，请完成后再修改提示词重试")
            assets.append(await shot_video_repo.create(s, conversation_id=conversation_id, project_id=project.id, storyboard_version_id=sb.id, storyboard_image_id=image.id, shot_index=index, status="pending", strategy=strategy, video_prompt=shot.get("video_prompt", ""), model=settings.ark_video_model, resolution=settings.ark_video_resolution, duration_sec=duration_sec, estimated_cost=round(duration_sec * settings.ark_video_cost_per_second, 2)))
    pending = [row.id for row in assets if row.status != "done"]
    if pending: await task_runner.submit("shot_video_generation", asset_ids=pending, aspect_ratio=sb.aspect_ratio or "9:16")
    return await get_for_conversation(conversation_id)


async def run_generation(asset_ids: list[str], aspect_ratio: str):
    for asset_id in asset_ids:
        try:
            async with AsyncSessionLocal() as s:
                asset = await shot_video_repo.get(s, asset_id)
                image = await image_repo.get_image(s, asset.storyboard_image_id) if asset else None
            if not asset or not image: continue
            await _mark(asset_id, status="generating", error=None)
            image_path = image.local_path
            if image_path and image_path.startswith("/api/img/"):
                image_path = str(settings.images_dir / image_path.removeprefix("/api/img/"))
            source = ark_video_client.image_data_url(image_path) if image_path and Path(image_path).exists() else (image.image_url or image.local_path)
            task_id = asset.task_id
            if not task_id:
                task_id = await ark_video_client.create_task(prompt=asset.video_prompt, image_url=source, duration=asset.duration_sec, ratio=aspect_ratio)
                await _mark(asset_id, task_id=task_id)
            remote_url = await ark_video_client.wait_result(task_id)
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(remote_url, timeout=180); response.raise_for_status()
            settings.shot_video_dir.mkdir(parents=True, exist_ok=True)
            path = settings.shot_video_dir / f"{asset_id}.mp4"; path.write_bytes(response.content)
            await _mark(asset_id, status="done", video_url=remote_url, local_path=f"/api/shot-video/{asset_id}.mp4")
        except Exception as exc:
            await _mark(asset_id, status="error", error=f"{type(exc).__name__}: {exc}"[:500])


async def _mark(asset_id: str, **fields):
    async with AsyncSessionLocal() as s: await shot_video_repo.update(s, asset_id, **fields)


async def resume_active() -> int:
    """服务重启后恢复远端任务轮询，已有 task_id 时不会重复产生费用。"""
    async with AsyncSessionLocal() as s:
        rows = await shot_video_repo.list_active(s)
        jobs = []
        for row in rows:
            storyboard = await storyboard_repo.get_storyboard(s, row.storyboard_version_id)
            jobs.append((row.id, storyboard.aspect_ratio if storyboard else "9:16"))
    for asset_id, aspect_ratio in jobs:
        await task_runner.submit("shot_video_generation", asset_ids=[asset_id], aspect_ratio=aspect_ratio)
    return len(jobs)


async def get_for_conversation(conversation_id: str) -> dict:
    async with AsyncSessionLocal() as s:
        project = await project_repo.get_conversation_project(s, conversation_id)
        sb = await storyboard_repo.get_active_storyboard(s, project.id) if project else None
        rows = await shot_video_repo.list_by_storyboard(s, sb.id) if sb else []
    return {"strategy": rows[0].strategy if rows else None, "selected_shots": [r.shot_index for r in rows], "estimated_cost": round(sum(r.estimated_cost for r in rows), 2), "assets": [shot_video_repo.to_dict(r) for r in rows], "has_active": any(r.status in {"pending", "generating"} for r in rows)}


task_runner.register_task("shot_video_generation", run_generation)
