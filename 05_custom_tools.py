"""示例 5：调用自定义工具

使用 @tool 装饰器自定义两个工具：
  - calculate: 安全的数学计算器
  - get_current_time: 获取当前时间
然后通过 create_tool_calling_agent 创建 Agent，让大模型自主选择调用。
"""

import ast
import operator
from datetime import datetime
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm

# 安全的运算符映射
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@tool
def calculate(expression: str) -> str:
    """计算数学表达式并返回结果。支持加减乘除、幂、取模。
    例如: '2 + 3 * 4'、'(10 + 5) / 3'、'2 ** 10'
    """
    try:
        node = ast.parse(expression, mode="eval").body
        result = _safe_eval(node)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


def _safe_eval(node):
    """递归安全求值，仅允许数字和基本运算符"""
    if isinstance(node, ast.Constant):  # 数字
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


@tool
def get_current_time() -> str:
    """获取当前日期和时间，格式为 YYYY-MM-DD HH:MM:SS。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    llm = get_llm(temperature=0)
    tools = [calculate, get_current_time]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个有用的助手，可以帮用户做数学计算和查询时间。请根据问题选择合适的工具。"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # 测试 1：计算
    print("=" * 50)
    print("测试 1：数学计算")
    print("=" * 50)
    result = agent_executor.invoke({
        "input": "帮我计算 (15 + 27) * 3 - 10 的结果",
    })
    print("回答:", result["output"])
    print()

    # 测试 2：时间查询
    print("=" * 50)
    print("测试 2：时间查询")
    print("=" * 50)
    result = agent_executor.invoke({
        "input": "现在几点了？",
    })
    print("回答:", result["output"])


if __name__ == "__main__":
    main()
