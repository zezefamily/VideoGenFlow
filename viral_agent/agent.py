"""Agent 模块：创建 Agent + AgentExecutor + 运行入口"""

import queue
import threading
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm
from viral_agent.tools import ALL_TOOLS
from viral_agent.prompts import SYSTEM_PROMPT


def create_agent(return_intermediate_steps=False):
    """创建爆款心理学短视频 Agent"""
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
        early_stopping_method="generate",
        return_intermediate_steps=return_intermediate_steps,
    )

    return agent_executor


def run(user_input: str = "") -> str:
    """运行 Agent，返回结果文本"""
    executor = create_agent()

    if not user_input or not user_input.strip():
        user_input = "帮我创作一个心理学短视频脚本"

    result = executor.invoke({"input": user_input})
    return result["output"]


def run_with_steps(user_input: str = ""):
    """运行 Agent，返回 (结果文本, 推理步骤列表)

    steps 每项为 dict: {tool, input, output}
    """
    executor = create_agent(return_intermediate_steps=True)

    if not user_input or not user_input.strip():
        user_input = "帮我创作一个心理学短视频脚本"

    result = executor.invoke({"input": user_input})
    output = result["output"]

    steps = []
    for action, observation in result.get("intermediate_steps", []):
        steps.append({
            "tool": action.tool,
            "input": str(action.tool_input),
            "output": str(observation),
        })

    return output, steps


# ============================================================
# 流式执行：回调 + 线程 + 生成器
# ============================================================

class ProgressCallbackHandler(BaseCallbackHandler):
    """推送 Agent 执行事件到队列，供流式消费"""

    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self._current_tool = ""
        self._current_input = ""

    def on_agent_action(self, action, *, run_id, parent_run_id=None, **kwargs):
        self._current_tool = action.tool
        self._current_input = str(action.tool_input)
        self.event_queue.put({
            "type": "step_start",
            "tool": action.tool,
            "input": str(action.tool_input),
        })

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        self.event_queue.put({
            "type": "step_end",
            "tool": self._current_tool,
            "input": self._current_input,
            "output": str(output),
        })

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self.event_queue.put({
            "type": "step_error",
            "tool": self._current_tool,
            "error": str(error),
        })

    def on_agent_finish(self, finish, *, run_id, parent_run_id=None, **kwargs):
        self.event_queue.put({
            "type": "finish",
            "output": finish.return_values.get("output", ""),
        })


def run_streaming(user_input: str = ""):
    """流式运行 Agent，yield (event, steps) 每一步进度

    Yields:
        tuple: (event_dict, steps_list)
        event_dict type: step_start | step_end | step_error | finish | error
        steps_list: 累积的步骤列表 [{tool, input, output}, ...]
    """
    if not user_input or not user_input.strip():
        user_input = "帮我创作一个心理学短视频脚本"

    event_queue = queue.Queue()
    handler = ProgressCallbackHandler(event_queue)
    executor = create_agent(return_intermediate_steps=True)

    result_holder = {}

    def _run_in_thread():
        try:
            result = executor.invoke(
                {"input": user_input},
                config={"callbacks": [handler]},
            )
            result_holder["result"] = result
        except Exception as e:
            result_holder["error"] = e
        finally:
            event_queue.put(None)  # 哨兵：线程结束

    thread = threading.Thread(target=_run_in_thread, daemon=True)
    thread.start()

    steps = []

    while True:
        event = event_queue.get()  # 阻塞直到有事件

        if event is None:
            break  # 线程结束

        if event["type"] == "step_start":
            steps.append({"tool": event["tool"], "input": event["input"], "output": ""})
            yield event, steps

        elif event["type"] == "step_end":
            if steps:
                steps[-1]["output"] = event["output"]
            yield event, steps

        elif event["type"] == "step_error":
            if steps:
                steps[-1]["output"] = f"Error: {event['error']}"
            yield event, steps

        elif event["type"] == "finish":
            yield event, steps

    # 线程已结束，处理未捕获的异常
    if "error" in result_holder:
        yield {"type": "error", "error": str(result_holder["error"])}, steps
        return

    # 如果回调没正常触发，从 intermediate_steps 兜底
    result = result_holder.get("result", {})
    if not steps:
        for action, observation in result.get("intermediate_steps", []):
            steps.append({
                "tool": action.tool,
                "input": str(action.tool_input),
                "output": str(observation),
            })
        if steps:
            yield {"type": "finish", "output": result.get("output", "")}, steps


def main():
    """交互式入口"""
    print("=" * 60)
    print("  爆款心理学短视频制作大师")
    print("=" * 60)
    print()
    print("我可以帮你制作心理学类短视频口播脚本。")
    print("你可以：")
    print("  1. 直接告诉我主题（如：讨好型人格）")
    print("  2. 提供抖音分享链接作为参考")
    print("  3. 主题 + 链接一起给我")
    print("  4. 什么都不说，我来帮你选话题")
    print()
    print("-" * 60)

    user_input = input("请输入：").strip()
    print("-" * 60)
    print()

    result = run(user_input)
    print()
    print("=" * 60)
    print("  最终口播脚本")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
