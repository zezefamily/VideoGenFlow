"""示例 9：结构化输出（Structured Output）

使用 JsonOutputParser + Pydantic 让大模型返回结构化数据。
DeepSeek 不支持 response_format，因此使用 Prompt 引导 + JSON 解析的方式。
"""

from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from common import get_llm


# 定义输出结构
class Person(BaseModel):
    """人物信息"""
    name: str = Field(description="人物姓名")
    age: int = Field(description="人物年龄")
    occupation: str = Field(description="职业")


class BookSummary(BaseModel):
    """书籍摘要"""
    title: str = Field(description="书名")
    author: str = Field(description="作者")
    summary: str = Field(description="一句话摘要")
    tags: List[str] = Field(description="标签列表，最多3个")


def main():
    llm = get_llm(temperature=0)

    # 测试 1：提取人物信息
    print("=" * 50)
    print("测试 1：提取人物信息")
    print("=" * 50)
    parser = JsonOutputParser(pydantic_object=Person)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "从用户输入中提取人物信息，严格按照以下 JSON 格式返回：\n{format_instructions}"),
        ("human", "{text}"),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser
    result = chain.invoke({"text": "李华今年30岁，在一家互联网公司担任产品经理"})
    print(f"姓名: {result['name']}")
    print(f"年龄: {result['age']}")
    print(f"职业: {result['occupation']}")
    print(f"类型: {type(result)}\n")

    # 测试 2：提取书籍信息
    print("=" * 50)
    print("测试 2：提取书籍信息")
    print("=" * 50)
    parser2 = JsonOutputParser(pydantic_object=BookSummary)
    prompt2 = ChatPromptTemplate.from_messages([
        ("system", "从用户输入中提取书籍信息，严格按照以下 JSON 格式返回：\n{format_instructions}"),
        ("human", "{text}"),
    ]).partial(format_instructions=parser2.get_format_instructions())

    chain2 = prompt2 | llm | parser2
    result2 = chain2.invoke({"text": "《三体》是刘慈欣创作的科幻小说，讲述了地球文明与三体文明的命运交织。"})
    print(f"书名: {result2['title']}")
    print(f"作者: {result2['author']}")
    print(f"摘要: {result2['summary']}")
    print(f"标签: {result2['tags']}")


if __name__ == "__main__":
    main()
