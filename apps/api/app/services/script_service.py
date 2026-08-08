"""脚本服务:热门研究 + 全新生成 + 局部修改(Phase 2)。

Phase 2 的 revise_script 只改局部,其余原样保留(方案第六节"局部修改"核心能力)。
"""

import json
import re

from langchain_core.prompts import ChatPromptTemplate

from app.prompts import (
    REVISE_SCRIPT_PROMPT,
    SCOPE_LABELS,
    SCRIPT_EXPAND_PROMPT,
    SCRIPT_GENERATION_PROMPT,
    SCRIPT_SHORTEN_PROMPT,
    TRENDING_RESEARCH_PROMPT,
)
from app.services.llm import get_llm
from app.utils import parse_llm_json

_FALLBACK_TOPICS = """以下是心理学领域的热门话题（备用列表）：
1. 讨好型人格 | 痛点：不敢拒绝别人 | 金句："你的善良，需要有点锋芒"
2. 情绪内耗 | 痛点：想太多做太少 | 金句："内耗的本质，是在用脑子和心打架"
3. 高敏感人群 | 痛点：被说太敏感 | 金句："高敏感不是病，是出厂设置不同"
4. 边界感 | 痛点：人际关系累 | 金句："没有边界感的好人，最后都成了坏人"
5. 原生家庭 | 痛点：重复父母的命运 | 金句："原生家庭是起点，不是终点\""""


def _count_chinese_chars(text: str) -> int:
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    return chinese_chars if chinese_chars > 0 else len(text)


def _parse_script_json(result_text: str, fallback_topic: str = "") -> dict:
    """把 LLM 输出解析为脚本 dict,容错 markdown 代码块与常见瑕疵。"""
    data = parse_llm_json(result_text)
    if not isinstance(data, dict):
        data = {
            "title": (fallback_topic or "心理学脚本")[:15],
            "keywords": ["心理学"],
            "duration_sec": 60,
            "content": result_text,
            "golden_sentence": "",
            "psychology_theory": "",
            "interaction_guide": "",
        }
    data["content"] = data.get("content", "") or result_text
    return data


async def _adjust_length(data: dict) -> dict:
    """字数校验:200-300 中文字符,超出/不足则扩缩 content。"""
    content = data.get("content", "")
    char_count = _count_chinese_chars(content)
    if char_count < 200:
        retry = ChatPromptTemplate.from_messages(
            [("system", SCRIPT_EXPAND_PROMPT), ("human", "{script}")]
        ) | get_llm(temperature=0.8, thinking="disabled")  # 扩缩长度是机械改写,关思考提速
        data["content"] = (await retry.ainvoke({"script": content})).content.strip()
    elif char_count > 300:
        retry = ChatPromptTemplate.from_messages(
            [("system", SCRIPT_SHORTEN_PROMPT), ("human", "{script}")]
        ) | get_llm(temperature=0.8, thinking="disabled")  # 扩缩长度是机械改写,关思考提速
        data["content"] = (await retry.ainvoke({"script": content})).content.strip()
    return data


async def research_trending_topics(psychology_field: str = "") -> str:
    """研究热门心理学话题,返回文本。"""
    try:
        llm = get_llm(temperature=0.5)
        field_instruction = (
            f"请重点关注「{psychology_field}」这个细分方向。"
            if psychology_field and psychology_field.strip()
            else ""
        )
        prompt = ChatPromptTemplate.from_messages(
            [("system", TRENDING_RESEARCH_PROMPT), ("human", "请开始分析。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke({"field_instruction": field_instruction})
        return resp.content
    except Exception:
        return f"（研究工具异常，使用备用话题库）\n\n{_FALLBACK_TOPICS}"


async def generate_script(topic: str) -> dict:
    """全新生成口播脚本(统一提示词,与做同款同源),返回结构化 dict。"""
    try:
        llm = get_llm(
            response_format={"type": "json_object"},
            temperature=0.8,
            thinking="enabled",
            reasoning_effort="max",  # 口播文案创作质量优先,拉满思考强度(与做同款一致)
        )
        prompt = ChatPromptTemplate.from_messages(
            [("system", SCRIPT_GENERATION_PROMPT), ("human", "请开始创作。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke(
            {
                "topic": topic or "",  # 空则由模型自行拟定心理学效应主题
                "transcript": "",  # 直接生成无原视频文案,仅参考示例1
            }
        )
        data = _parse_script_json(resp.content.strip(), topic)
        return await _adjust_length(data)
    except Exception as e:
        return {
            "title": "生成失败",
            "keywords": ["错误"],
            "duration_sec": 0,
            "content": f"脚本生成失败：{type(e).__name__}。请稍后重试。",
            "golden_sentence": "",
            "psychology_theory": "",
            "interaction_guide": "",
        }


async def revise_script(
    previous_script: dict,
    instruction: str,
    scope: str = "whole",
) -> dict:
    """局部修改脚本:只改 scope 范围,其余原样保留。返回新脚本 dict。"""
    try:
        llm = get_llm(temperature=0.7, response_format={"type": "json_object"})
        prompt = ChatPromptTemplate.from_messages(
            [("system", REVISE_SCRIPT_PROMPT), ("human", "请修改。")]
        )
        chain = prompt | llm
        resp = await chain.ainvoke(
            {
                "previous_script": previous_script.get("content", ""),
                "instruction": instruction or "无",
                "scope": scope,
                "scope_label": SCOPE_LABELS.get(scope, scope),
            }
        )
        data = _parse_script_json(resp.content.strip(), previous_script.get("title", ""))
        # 局部修改通常无需再扩缩,但仍校验极端情况
        return await _adjust_length(data)
    except Exception as e:
        # 修改失败:返回旧脚本内容,附带错误标记
        return {
            **previous_script,
            "content": previous_script.get("content", "")
            + f"\n\n（修改失败：{type(e).__name__}，请稍后重试）",
        }
