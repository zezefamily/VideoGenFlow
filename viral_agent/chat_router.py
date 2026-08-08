"""对话路由模块：基于 LangChain 的意图检测 + 闲聊引导

利用 LangChain 优势：
1. LCEL 链式调用（prompt | llm | parser）
2. System Prompt 统一人设和行为控制
3. 状态感知 -- 根据当前对话阶段调整引导策略
"""

import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from common import get_llm


class ChatRoute:
    """意图检测结果"""
    def __init__(self, is_task: bool, task_type: str = "", reply: str = ""):
        self.is_task = is_task
        self.task_type = task_type
        self.reply = reply


# 各阶段的上下文提示
_STEP_CONTEXT = {
    "idle": "用户刚开始或已完成上一轮。如果用户给了话题/链接/明确需求，is_task=true。闲聊时引导用户输入话题或抖音链接。",
    "script_ready": "用户刚收到口播脚本。如果用户说重新生成/改写/继续/生成分镜，is_task=true。闲聊时提醒：回复1重新生成脚本，回复2进入分镜设计。",
    "storyboard_ready": "用户刚收到分镜设计，或分镜图生成刚失败。如果用户说重新生成分镜，task_type=regenerate。如果用户说继续/生成图片/再次尝试/重试生成分镜图，task_type=proceed。闲聊时提醒：回复1重新生成分镜，回复2生成分镜图。",
    "image_ready": "用户刚收到分镜图。如果用户给了新话题/链接，is_task=true。闲聊时引导用户输入新话题开始下一轮创作。",
    "agent_running": "Agent正在执行中。任何消息都 is_task=false，回复'正在处理中，请稍候'。",
}

_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是「爆款心理学短视频制作大师」，一个专注于心理学短视频创作的AI助手。

你的核心能力：
- 根据话题生成 60-90 秒心理学口播脚本
- 根据抖音链接提取爆款文案并仿写
- 生成分镜设计（15-20镜，含画面描述和镜头语言）
- 批量生成分镜配图（支持黑板粉笔手绘风等多种风格）

当前对话阶段: {step}
阶段说明: {step_desc}

判断用户消息的意图，只输出一个 JSON，不要输出其他内容：
```json
{{
  "is_task": true/false,
  "task_type": "new_task 或 regenerate 或 proceed（is_task=false 时留空）",
  "reply": "闲聊回复内容（is_task=true 时留空）"
}}
```

task_type 说明：
- new_task: 用户给了新话题/链接/明确创作需求
- regenerate: 用户想重新生成当前阶段的内容
- proceed: 用户想继续到下一步

闲聊回复规则：
1. 友好回应用户说的话（1-2句，不超过50字）
2. 始终在结尾自然引导到创作主线
3. 根据当前阶段提醒用户可以做什么
4. 不要长篇大论介绍功能
5. 语气轻松亲切"""),
    ("human", "{message}"),
])


def route_message(message: str, step: str = "idle") -> ChatRoute:
    """检测用户消息意图，返回路由结果

    Args:
        message: 用户消息
        step: 当前对话阶段 (idle/script_ready/storyboard_ready/image_ready/agent_running)

    Returns:
        ChatRoute: is_task=True 时走 Agent 流程，is_task=False 时用 reply 回复
    """
    llm = get_llm(temperature=0, max_tokens=300, response_format={"type": "json_object"})
    chain = _ROUTER_PROMPT | llm | StrOutputParser()

    step_desc = _STEP_CONTEXT.get(step, _STEP_CONTEXT["idle"])

    raw = chain.invoke({
        "message": message,
        "step": step,
        "step_desc": step_desc,
    })

    try:
        data = json.loads(raw)
        return ChatRoute(
            is_task=bool(data.get("is_task", False)),
            task_type=data.get("task_type", ""),
            reply=data.get("reply", ""),
        )
    except (json.JSONDecodeError, KeyError):
        # JSON 解析失败，默认当任务处理
        return ChatRoute(is_task=True, task_type="new_task", reply="")
