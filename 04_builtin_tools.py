"""示例 4：调用 LangChain 内置工具（PythonREPLTool）

使用 langchain-experimental 提供的 PythonREPLTool 工具，
让大模型通过执行 Python 代码来回答问题（数据处理、排序、统计等）。
"""

from langchain_experimental.tools import PythonREPLTool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm


def main():
    llm = get_llm(temperature=0)

    # 使用 LangChain 内置的 Python REPL 工具
    python_tool = PythonREPLTool()
    tools = [python_tool]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个数据分析助手，可以执行 Python 代码来解决问题。"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # 测试 1：排序
    print("=" * 50)
    print("测试 1：数据排序")
    print("=" * 50)
    result = agent_executor.invoke({
        "input": "把列表 [3, 1, 4, 1, 5, 9, 2, 6, 5] 从大到小排序，告诉我结果",
    })
    print("\n最终回答:", result["output"])
    print()

    # 测试 2：统计计算
    print("=" * 50)
    print("测试 2：统计计算")
    print("=" * 50)
    result = agent_executor.invoke({
        "input": "计算列表 [12, 15, 18, 22, 25, 30, 28, 20] 的平均值、最大值和最小值",
    })
    print("\n最终回答:", result["output"])


if __name__ == "__main__":
    main()
