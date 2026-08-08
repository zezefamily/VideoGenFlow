"""通用工具函数。"""

import json
import re
from typing import Optional


def parse_llm_json(result_text: str) -> Optional[dict]:
    """鲁棒解析 LLM 返回的 JSON dict。

    LLM 偶发返回带前后缀文字、markdown 代码块包裹、尾随逗号等瑕疵导致 json.loads 失败。
    依次尝试多道防线,任一成功即返回,全部失败返回 None:
    1. 直接解析整段(剥离首尾空白)
    2. 剥离 markdown ```json``` 代码块后再解析
    3. 提取首个 { 到末个 } 的子串(处理前后缀文字)后解析
    4. 修复常见瑕疵(尾随逗号)后重试 1-3 的候选
    """
    if not result_text:
        return None
    text = result_text.strip()

    candidates: list[str] = [text]
    # markdown 代码块
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    # 首 { 到末 }
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])

    def _try(cand: str) -> Optional[dict]:
        try:
            data = json.loads(cand)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    for cand in candidates:
        data = _try(cand)
        if data is not None:
            return data

    # 修复尾随逗号(如 {"a":1,} / [1,2,])后重试
    fixed_candidates = [re.sub(r",\s*([}\]])", r"\1", c) for c in candidates]
    for cand in fixed_candidates:
        data = _try(cand)
        if data is not None:
            return data

    return None
