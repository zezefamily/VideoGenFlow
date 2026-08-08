"""示例 6：工具组合调用

将内置工具（PythonREPLTool）和自定义工具（计算器、时间查询）组合，
交给同一个 Agent 使用。大模型会根据问题自主决定调用哪个或哪几个工具。
"""

from langchain_experimental.tools import PythonREPLTool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm
from importlib import import_module

# 复用 05_custom_tools.py 中定义的自定义工具
custom = import_module("05_custom_tools")
calculate = custom.calculate
get_current_time = custom.get_current_time


def main():
    llm = get_llm(temperature=0)

    # 组合内置工具 + 自定义工具
    python_tool = PythonREPLTool()
    tools = [python_tool, calculate, get_current_time]

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "你是一个全能助手，具备以下能力：\n"
            "1. 执行 Python 代码进行复杂数据处理\n"
            "2. 使用计算器进行数学计算\n"
            "3. 查询当前时间\n"
            "请根据用户问题选择合适的工具，可以组合使用多个工具。"
        )),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # 测试 1：需要时间 + 计算
    print("=" * 60)
    print("测试 1：时间 + 计算")
    print("=" * 60)
    result = agent_executor.invoke({
        "input": "先告诉我现在的时间，然后计算 2024 年距离 2030 年还有多少天（用 Python 代码计算）",
    })
    print("\n最终回答:", result["output"])
    print()

    # 测试 2：需要 Python 代码处理 + 计算器
    print("=" * 60)
    print("测试 2：数据处理 + 计算器")
    print("=" * 60)
    result = agent_executor.invoke({
        "input": "用 Python 生成 1 到 10 的平方数列表，然后用计算器验证其中最大的那个平方数是否正确",
    })
    print("\n最终回答:", result["output"])


if __name__ == "__main__":
    main()
