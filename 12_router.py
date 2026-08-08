"""示例 12：条件路由（Router）

使用 RunnableBranch 根据输入内容的特征，将请求路由到不同的处理链。
例如：技术问题走详细模式，闲聊走简洁模式。
"""

from langchain_core.runnables import RunnableBranch, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from common import get_llm


def main():
    llm = get_llm(temperature=0)

    # 路由判断函数
    def is_tech(query: str) -> bool:
        tech_keywords = ["代码", "编程", "bug", "API", "框架", "数据库",
                         "Python", "Java", "算法", "部署", "服务器", "函数"]
        return any(kw in query.lower() for kw in tech_keywords)

    def is_math(query: str) -> bool:
        math_keywords = ["计算", "等于", "加", "减", "乘", "除", "求和", "平均"]
        return any(kw in query for kw in math_keywords)

    # 技术问题链：详细回答
    tech_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个资深技术专家，请详细专业地回答技术问题。"),
        ("human", "{input}"),
    ])
    tech_chain = tech_prompt | llm | StrOutputParser() | (lambda r: f"[技术模式] {r}")

    # 数学问题链：简洁回答
    math_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个数学老师，请简洁地回答，直接给出结果。"),
        ("human", "{input}"),
    ])
    math_chain = math_prompt | llm | StrOutputParser() | (lambda r: f"[数学模式] {r}")

    # 默认链：闲聊
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个友好的聊天伙伴，回答轻松简短。"),
        ("human", "{input}"),
    ])
    chat_chain = chat_prompt | llm | StrOutputParser() | (lambda r: f"[闲聊模式] {r}")

    # 条件路由
    router = RunnableBranch(
        (lambda x: is_math(x["input"]), math_chain),
        (lambda x: is_tech(x["input"]), tech_chain),
        chat_chain,  # 默认分支
    )

    # 测试不同类型的问题
    test_cases = [
        "帮我计算 25 乘以 4 等于多少",
        "Python 中如何定义一个函数？",
        "今天天气真好啊",
    ]

    for query in test_cases:
        print("=" * 50)
        print(f"输入：{query}")
        result = router.invoke({"input": query})
        print(f"输出：{result}\n")


if __name__ == "__main__":
    main()
