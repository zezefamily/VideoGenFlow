"""
LangChain 简单大模型调用示例

演示如何使用 LangChain 框架调用 DeepSeek 大模型，
包含：基础调用、带提示模板的调用、对话链调用。
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def main():
    # 加载 .env 环境变量
    load_dotenv()

    # 初始化 DeepSeek 模型（DeepSeek API 兼容 OpenAI 格式）
    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0.7,
    )

    # -------------------------------------------------------
    # 示例 1：最简单的直接调用
    # -------------------------------------------------------
    print("=" * 50)
    print("示例 1：直接调用")
    print("=" * 50)
    response = llm.invoke("用一句话解释什么是 LangChain？")
    print(response.content)
    print()

    # -------------------------------------------------------
    # 示例 2：使用消息列表（System + Human）
    # -------------------------------------------------------
    print("=" * 50)
    print("示例 2：使用 System + Human 消息")
    print("=" * 50)
    messages = [
        SystemMessage(content="你是一个资深 Python 开发者，回答简洁明了。"),
        HumanMessage(content="列出 3 个使用 LangChain 的优势。"),
    ]
    response = llm.invoke(messages)
    print(response.content)
    print()

    # -------------------------------------------------------
    # 示例 3：使用 PromptTemplate + Chain（LCEL 链式调用）
    # -------------------------------------------------------
    print("=" * 50)
    print("示例 3：使用 PromptTemplate + LCEL Chain")
    print("=" * 50)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个{role}，请用通俗易懂的语言回答。"),
        ("human", "{question}"),
    ])
    # LCEL 语法：prompt | llm | parser
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({
        "role": "技术老师",
        "question": "什么是大语言模型（LLM）？",
    })
    print(result)


if __name__ == "__main__":
    main()
