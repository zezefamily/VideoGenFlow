"""LangGraph 状态(方案第四节)。

Phase 1 只填充子集。注意:不使用 MessagesState 的 messages 累加 reducer,
历史消息以 DB 为唯一真源,每轮由 load_context 整体覆盖 history 字段。

Phase 2:新增 project_id(作品隔离)、scope/instruction(局部修改)。
"""

from typing import Optional, TypedDict


class ChatState(TypedDict, total=False):
    # 运行上下文
    user_id: str
    conversation_id: str
    run_id: str
    user_input: str  # 本轮用户消息文本

    # 意图与上下文
    intent: Optional[str]  # chat | create/revise script/storyboard | generate_images | generate_tts | render_video | analyze_video
    scope: Optional[str]  # 局部修改范围:opening | ending | whole | specific
    instruction: Optional[str]  # 局部修改要求(自然语言)
    history: list  # LangChain 消息列表(每轮从 DB 重建)
    project_id: Optional[str]  # 当前作品 id(Phase 2 作品隔离)
    script: Optional[dict]  # 当前激活脚本(artifact dict)
    script_id: Optional[str]
    storyboard: Optional[dict]  # 当前激活分镜(artifact dict, Phase 3)
    storyboard_id: Optional[str]
    images: list  # 分镜图列表(Phase 4)
    audio: Optional[dict]  # 当前音轨
    video: Optional[dict]  # 当前成片
    video_analysis: Optional[dict]  # 视频分析 artifact(抖音链接解析 / 做同款)
    active_artifact: Optional[str]

    # 输出
    final_text: str  # 助手最终回复文本
    message_type: str  # text | script_card | storyboard_card | image_gallery | video_analysis_card
    artifact_id: Optional[str]

    # 运行状态
    run_status: str  # running | completed | error
    error: Optional[dict]
