"""LLM 工厂:从 common.py 移植,统一 DeepSeek 接入。"""

from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings


def get_llm(
    temperature: float = 0.7,
    *,
    thinking: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs,
):
    """返回配置好的 DeepSeek ChatOpenAI 实例。

    按任务调思考档(DeepSeek V4 思考模式默认开 / effort 默认 high):
    - thinking="disabled": 关闭深度思考,用于分类、闲聊等简单任务,提速省 token。
    - thinking="enabled" + reasoning_effort="max": 拉满思考强度,用于仿写等质量优先任务。
    - 均不传:走服务端默认(high)。
    """
    extra_body = dict(kwargs.pop("extra_body", None) or {})
    if thinking is not None:
        extra_body["thinking"] = {"type": thinking}
    if reasoning_effort is not None:
        extra_body["reasoning_effort"] = reasoning_effort
    if extra_body:
        kwargs["extra_body"] = extra_body
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
        **kwargs,
    )
