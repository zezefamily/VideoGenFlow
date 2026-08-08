"""公共模块：DeepSeek LLM 初始化"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def get_llm(temperature=0.7, **kwargs):
    """返回配置好的 DeepSeek ChatOpenAI 实例"""
    load_dotenv()
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=temperature,
        **kwargs,
    )
