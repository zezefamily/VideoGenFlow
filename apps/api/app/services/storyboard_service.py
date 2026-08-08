"""分镜服务:基于脚本生成分镜 + 单镜头/局部修改(Phase 3)。

生成:把口播脚本拆成 8-12 个镜头(画面/旁白/时长/镜头运动)。
修改:scoped regenerate —— 旧分镜全文 + 修改要求,只改点名镜头,其余逐字保留。
"""

import json
import re
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from app.prompts import (
    DEFAULT_STYLE,
    STORYBOARD_GENERATE_PROMPT,
    STORYBOARD_REVISE_PROMPT,
    STORYBOARD_STYLES,
)
from app.services.llm import get_llm
from app.utils import parse_llm_json

# 画风名识别关键词(detect_style 用,匹配用户消息里的画风说法)
_STYLE_KEYWORDS = {
    "黑板粉笔手绘风": ["粉笔", "黑板", "chalk", "chalkboard"],
    "水彩插画风": ["水彩", "watercolor"],
    "扁平设计风": ["扁平", "flat design"],
    "写实摄影风": ["写实", "摄影", "realistic", "照片"],
    "暗黑系油画风": ["油画", "暗黑", "oil painting"],
    "极简线条风": ["极简", "线条画", "line art", "minimalist"],
    "港风动漫风": ["港风", "港式", "赛璐璐", "hong kong anime"],
}


def _resolve_style(name: str) -> str:
    """画风名 -> 详细描述(含 AI 关键词),未知名回退默认粉笔风。"""
    return STORYBOARD_STYLES.get(name, STORYBOARD_STYLES[DEFAULT_STYLE])


def detect_style(text: str, default: str = DEFAULT_STYLE) -> str:
    """从用户消息识别画风名,未识别返回默认(粉笔风)。"""
    if not text:
        return default
    t = text.lower()
    for name, kws in _STYLE_KEYWORDS.items():
        if any(kw.lower() in t for kw in kws):
            return name
    return default


def detect_style_explicit(text: str) -> Optional[str]:
    """用户消息是否明确指定了画风,返回画风名或 None(不兜底默认)。

    区别于 detect_style:后者未识别时返回默认粉笔风;
    本函数未识别返回 None,用于判断用户是否主动指定了画风(如生图时覆盖分镜画风)。
    """
    if not text:
        return None
    t = text.lower()
    for name, kws in _STYLE_KEYWORDS.items():
        if any(kw.lower() in t for kw in kws):
            return name
    return None

_ASPECT_HINT = {
    "9:16": "竖屏，适合抖音/视频号/小红书",
    "16:9": "横屏，适合 B站/YouTube",
    "1:1": "方屏，适合朋友圈/Instagram",
}


def _parse_shots_json(result_text: str) -> dict:
    """把 LLM 输出解析为 {"shots": [...]}。"""
    data = parse_llm_json(result_text)
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list):
        return {"shots": []}

    # 规整每个镜头字段 + 重排 index
    shots = []
    for i, sh in enumerate(data["shots"], start=1):
        if not isinstance(sh, dict):
            continue
        shots.append(
            {
                "index": i,
                "title": str(sh.get("title", "")).strip()[:30],
                "visual": str(sh.get("visual", "")).strip(),
                "video_prompt": str(sh.get("video_prompt", "")).strip(),
                "narration": str(sh.get("narration", "")).strip(),
                "duration_sec": int(sh.get("duration_sec", 0) or 0),
                "camera": str(sh.get("camera", "")).strip(),
                "notes": str(sh.get("notes", "")).strip(),
            }
        )
    return {"shots": shots}


async def generate_storyboard(
    script_content: str,
    aspect_ratio: str = "16:9",
    style: str = DEFAULT_STYLE,
) -> dict:
    """基于口播脚本生成分镜,返回 {shots, aspect_ratio, style}。

    style: 画风名(见 STORYBOARD_STYLES),内部映射为详细描述传给 LLM。
    返回的 style 字段为画风描述(image_service 出图直接用)。
    """
    style_desc = _resolve_style(style)
    try:
        llm = get_llm(temperature=0.8, response_format={"type": "json_object"})
        prompt = ChatPromptTemplate.from_messages(
            [("system", STORYBOARD_GENERATE_PROMPT), ("human", "请拆分镜头。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke(
            {
                "script_content": script_content or "（无脚本，请自行构思一段心理学口播）",
                "aspect_ratio": aspect_ratio,
                "aspect_hint": _ASPECT_HINT.get(aspect_ratio, aspect_ratio),
                "style": style_desc,
            }
        )
        data = _parse_shots_json(resp.content.strip())
        if not data["shots"]:
            # 解析失败兜底:单镜头
            data = {
                "shots": [
                    {
                        "index": 1,
                        "title": "全片",
                        "visual": "（生成失败，请重试）",
                        "narration": script_content[:60],
                        "duration_sec": 0,
                        "camera": "中景",
                        "notes": "",
                    }
                ]
            }
        return {**data, "aspect_ratio": aspect_ratio, "style": style_desc}
    except Exception as e:
        return {
            "shots": [],
            "aspect_ratio": aspect_ratio,
            "style": style_desc,
            "error": f"分镜生成失败：{type(e).__name__}",
        }


async def revise_storyboard(previous_shots: list, instruction: str) -> dict:
    """局部修改分镜:只改点名镜头,其余逐字保留。返回 {shots}。"""
    if not previous_shots:
        return {"shots": [], "error": "没有旧分镜，无法修改"}
    try:
        llm = get_llm(temperature=0.7, response_format={"type": "json_object"})
        prompt = ChatPromptTemplate.from_messages(
            [("system", STORYBOARD_REVISE_PROMPT), ("human", "请修改。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke(
            {
                "previous_shots": json.dumps(previous_shots, ensure_ascii=False),
                "instruction": instruction or "整体优化",
            }
        )
        data = _parse_shots_json(resp.content.strip())
        if not data["shots"]:
            # 修改失败:返回旧分镜
            return {"shots": previous_shots, "error": "修改未生效，已保留旧分镜"}
        return data
    except Exception as e:
        return {"shots": previous_shots, "error": f"分镜修改失败：{type(e).__name__}"}


def detect_aspect_ratio(text: str, default: str = "16:9") -> str:
    """从用户消息里识别画面比例。默认横屏 16:9。"""
    if not text:
        return default
    t = text.lower().replace("：", ":")
    if "9:16" in t or "竖屏" in text:
        return "9:16"
    if "16:9" in t or "横屏" in text:
        return "16:9"
    if "1:1" in t or "方屏" in text:
        return "1:1"
    return default
