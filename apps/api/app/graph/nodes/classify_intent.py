"""意图分类(Phase 3 扩展)。

输出 {intent, scope, instruction},支持脚本与分镜两类意图:
chat | create_script | revise_script | generate_storyboard | revise_storyboard
"""

import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.graph.tracking import tracked
from app.prompts import CLASSIFY_INTENT_PROMPT
from app.services.llm import get_llm
from app.services.media_service import detect_share_link

_VALID_INTENTS = {
    "chat",
    "create_script",
    "revise_script",
    "generate_storyboard",
    "revise_storyboard",
    "generate_images",
    "analyze_video",
    "generate_tts",
    "render_video",
}
_VALID_SCOPES = {"opening", "ending", "whole", "specific"}
# 生成类意图(需要前置条件),分别依赖 script / storyboard
_NEEDS_SCRIPT = {"revise_script", "generate_storyboard"}
_NEEDS_STORYBOARD = {"revise_storyboard", "generate_images"}

_TTS_RE = re.compile(
    r"(重新|重做|再).{0,5}(语音|配音)|"
    r"(语音|配音|声音).{0,8}(重新|重做|再来|再生成|换成|改成|切换)|"
    r"(换成|改成|切换).{0,8}(豆包|火山|dubbingx).{0,8}(语音|配音|声音)?|"
    r"(语音|配音|声音).{0,8}(豆包|火山|dubbingx)"
)
_VIDEO_RE = re.compile(r"(重新|重做|再).{0,5}(合成|生成).{0,3}(视频|成片)|(视频|成片).{0,5}(重新合成|重做|再合成)")


@tracked("classify_intent")
async def classify_intent(state):
    user_input = state.get("user_input", "")
    has_script = state.get("script") is not None
    has_storyboard = state.get("storyboard") is not None
    has_audio = state.get("audio") is not None

    # 确定性优先:输入含短视频分享链接 -> 直接判为 analyze_video(避免 LLM 误判为 create_script)
    if detect_share_link(user_input):
        return {"intent": "analyze_video", "scope": "whole", "instruction": ""}

    # 制作动作使用确定性路由，避免被“重新”误判成修改文案。
    if _TTS_RE.search(user_input):
        return {"intent": "generate_tts" if has_script else "chat", "scope": "whole", "instruction": user_input}
    if _VIDEO_RE.search(user_input):
        return {"intent": "render_video" if has_audio and has_storyboard else "chat", "scope": "whole", "instruction": ""}

    llm = get_llm(
        temperature=0,
        max_tokens=128,
        response_format={"type": "json_object"},
        thinking="disabled",  # 意图分类是简单判别,关思考提速省 token
    )
    prompt = ChatPromptTemplate.from_messages(
        [("system", CLASSIFY_INTENT_PROMPT), ("human", "{message}")]
    )
    chain = prompt | llm | StrOutputParser()

    intent = "chat"
    scope = "whole"
    instruction = ""
    try:
        raw = await chain.ainvoke(
            {
                "message": user_input,
                "has_script": str(has_script),
                "has_storyboard": str(has_storyboard),
            }
        )
        data = json.loads(raw)
        intent = data.get("intent", "chat")
        scope = data.get("scope", "whole")
        instruction = (data.get("instruction") or "").strip()
    except Exception:
        intent = "chat"

    # 前置条件不满足时回退
    if intent in _NEEDS_SCRIPT and not has_script:
        intent = "create_script"
    if intent in _NEEDS_STORYBOARD and not has_storyboard:
        intent = "generate_storyboard" if has_script else "chat"
    if intent not in _VALID_INTENTS:
        intent = "create_script" if has_script else "chat"
    if scope not in _VALID_SCOPES:
        scope = "whole"
    if intent in ("revise_script", "revise_storyboard") and not instruction:
        instruction = user_input

    return {"intent": intent, "scope": scope, "instruction": instruction}
