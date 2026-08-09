"""火山方舟 Seedance 异步视频生成客户端。"""

import asyncio
import base64
from pathlib import Path

import httpx

from app.config import settings


class ArkVideoError(RuntimeError): pass


def image_data_url(path: str) -> str:
    data = Path(path).read_bytes()
    suffix = Path(path).suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


async def create_task(*, prompt: str, image_url: str, duration: int, ratio: str) -> str:
    body = {
        "model": settings.ark_video_model,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}, "role": "first_frame"},
        ],
        "resolution": settings.ark_video_resolution,
        "ratio": ratio,
        "duration": max(4, min(15, round(duration))),
        "watermark": False,
        "generate_audio": False,
    }
    url = f"{settings.ark_base_url}/contents/generations/tasks"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {settings.ark_api_key}"}, json=body, timeout=120)
    if response.status_code not in (200, 201):
        raise ArkVideoError(f"创建视频任务失败 {response.status_code}: {response.text[:300]}")
    task_id = response.json().get("id")
    if not task_id: raise ArkVideoError("创建视频任务未返回 id")
    return task_id


async def wait_result(task_id: str, timeout_sec: int = 1800) -> str:
    url = f"{settings.ark_base_url}/contents/generations/tasks/{task_id}"
    deadline = asyncio.get_running_loop().time() + timeout_sec
    async with httpx.AsyncClient() as client:
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(url, headers={"Authorization": f"Bearer {settings.ark_api_key}"}, timeout=60)
            if response.status_code != 200:
                raise ArkVideoError(f"查询视频任务失败 {response.status_code}: {response.text[:300]}")
            payload = response.json(); status = payload.get("status")
            if status == "succeeded":
                video_url = (payload.get("content") or {}).get("video_url")
                if not video_url: raise ArkVideoError("视频任务完成但未返回 video_url")
                return video_url
            if status in {"failed", "cancelled", "expired"}:
                err = payload.get("error") or {}
                raise ArkVideoError(str(err.get("message") or err or f"任务状态 {status}"))
            await asyncio.sleep(5)
    raise ArkVideoError("视频生成等待超时")
