"""分镜图批量生成模块：调用火山引擎 ARK API 生成图片

- 第 1 镜：文生图（text-to-image）
- 第 2~N 镜：图生图链式（image-to-image，以前一镜图片为参考）
"""

import os
import json
import requests
from typing import Generator
from dotenv import load_dotenv

_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMAGES_DIR = os.path.join(_PROJECT_ROOT, "data", "images")

# 画面比例 -> 像素尺寸（2K 分辨率档位）
_ASPECT_RATIO_SIZES = {
    "1:1":  "2048x2048",   # 4,194,304 px
    "4:3":  "2304x1728",   # 3,981,312 px
    "3:4":  "1728x2304",   # 3,981,312 px
    "16:9": "2848x1600",   # 4,556,800 px
    "9:16": "1600x2848",   # 4,556,800 px
}


def _get_ark_config():
    """从环境变量读取 ARK API 配置"""
    load_dotenv()
    api_key = os.getenv("ARK_API_KEY", "")
    model = os.getenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    return api_key, model


def _resolve_size(aspect_ratio: str) -> str:
    """将画面比例转为 API 支持的像素尺寸字符串"""
    return _ASPECT_RATIO_SIZES.get(aspect_ratio, "2048x2048")


def _call_ark_api(prompt: str, size: str = "2048x2048", reference_image: str = None) -> dict:
    """调用 ARK 图片生成 API

    Args:
        prompt: 文生图提示词
        size: 像素尺寸，如 "2560x1440"（方式2，精确控制比例）
        reference_image: 图生图的参考图 URL

    返回 {"url": "...", "error": None} 或 {"url": None, "error": "错误信息"}
    """
    api_key, model = _get_ark_config()
    if not api_key:
        return {"url": None, "error": "ARK_API_KEY 未配置，请在 .env 中设置"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled",
        "stream": False,
    }

    if reference_image:
        body["image"] = reference_image

    try:
        response = requests.post(
            f"{_ARK_BASE_URL}/images/generations",
            headers=headers,
            json=body,
            timeout=120,
        )
        if response.status_code != 200:
            error_msg = f"API 返回 {response.status_code}: {response.text[:200]}"
            return {"url": None, "error": error_msg}

        data = response.json()
        images = data.get("data", [])
        if not images:
            return {"url": None, "error": "API 返回空数据"}

        url = images[0].get("url", "")
        if not url:
            return {"url": None, "error": "API 返回的 URL 为空"}

        return {"url": url, "error": None}

    except requests.exceptions.Timeout:
        return {"url": None, "error": "API 请求超时（120s）"}
    except Exception as e:
        return {"url": None, "error": f"{type(e).__name__}: {e}"}


def _download_image(url: str, save_path: str) -> bool:
    """下载图片到本地"""
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        return False
    except Exception:
        return False


def generate_storyboard_images(
    storyboard_json: str,
    aspect_ratio: str = "",
    record_id: int = 0,
    image_size: str = "",
) -> Generator:
    """批量生成分镜图（链式图生图）

    Args:
        storyboard_json: 分镜 JSON 字符串
        aspect_ratio: 画面比例（如 "16:9"），用于确定像素尺寸
        record_id: 记录 ID（用于图片保存路径）
        image_size: 直接指定像素尺寸（优先于 aspect_ratio）

    yield 事件:
    - {"type": "shot_start", "shot_number": 1, "total": 15, "method": "text2image"/"img2image"}
    - {"type": "shot_done", "shot_number": 1, "image_url": "...", "local_path": "..."}
    - {"type": "shot_error", "shot_number": 1, "error": "..."}
    - {"type": "all_done", "images": [...], "success_count": N, "fail_count": M}
    """
    try:
        shots = json.loads(storyboard_json)
    except (json.JSONDecodeError, TypeError):
        yield {"type": "all_done", "images": [], "success_count": 0, "fail_count": 0,
               "error": "分镜 JSON 解析失败"}
        return

    if not isinstance(shots, list) or not shots:
        yield {"type": "all_done", "images": [], "success_count": 0, "fail_count": 0,
               "error": "分镜数据为空"}
        return

    total = len(shots)
    images_result = []
    success_count = 0
    fail_count = 0
    last_success_url = None  # 用于链式图生图的参考图

    # 确定像素尺寸：优先 image_size，其次 aspect_ratio 转换
    api_size = image_size if image_size else _resolve_size(aspect_ratio)

    # 图片保存目录
    save_dir = os.path.join(_IMAGES_DIR, str(record_id)) if record_id else os.path.join(_IMAGES_DIR, "temp")

    for i, shot in enumerate(shots):
        shot_number = shot.get("shot_number", i + 1)
        image_prompt = shot.get("image_prompt", "")

        if not image_prompt:
            yield {"type": "shot_error", "shot_number": shot_number,
                   "error": "image_prompt 为空"}
            fail_count += 1
            continue

        method = "img2image" if last_success_url else "text2image"

        yield {
            "type": "shot_start",
            "shot_number": shot_number,
            "total": total,
            "method": method,
        }

        result = _call_ark_api(
            prompt=image_prompt,
            size=api_size,
            reference_image=last_success_url,
        )

        if result["error"]:
            yield {"type": "shot_error", "shot_number": shot_number,
                   "error": result["error"]}
            fail_count += 1
            # 失败时不更新 last_success_url，下一镜继续用上一个成功的图
            continue

        image_url = result["url"]

        # 下载到本地
        local_path = os.path.join(save_dir, f"shot_{shot_number}.png")
        downloaded = _download_image(image_url, local_path)
        local_path = local_path if downloaded else None

        # 更新链式参考图
        last_success_url = image_url

        images_result.append({
            "shot_number": shot_number,
            "image_url": image_url,
            "local_path": local_path,
            "method": method,
        })
        success_count += 1

        yield {
            "type": "shot_done",
            "shot_number": shot_number,
            "image_url": image_url,
            "local_path": local_path,
        }

    yield {
        "type": "all_done",
        "images": images_result,
        "success_count": success_count,
        "fail_count": fail_count,
    }
