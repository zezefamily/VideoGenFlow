"""节点跟踪装饰器:向 RunManager 推送 node_start / node_end / node_error 事件。"""

from functools import wraps

from app.schemas.events import SSEEvent
from app.services.run_manager import run_manager
from app.db import AsyncSessionLocal
from app.repositories import run_repo

# 节点名 -> 前端展示文案
NODE_LABELS = {
    "load_context": "加载上下文",
    "classify_intent": "理解需求",
    "generate_script": "生成脚本",
    "revise_script": "局部修改",
    "generate_storyboard": "生成分镜",
    "revise_storyboard": "修改分镜",
    "generate_images": "生成图片",
    "analyze_video": "分析参考视频",
    "generate_tts": "重新生成配音",
    "render_video": "重新合成成片",
    "respond": "组织回复",
}


def tracked(name: str):
    def deco(fn):
        @wraps(fn)
        async def wrapper(state):
            run_id = state.get("run_id") if isinstance(state, dict) else None
            label = NODE_LABELS.get(name, name)
            if run_id:
                async with AsyncSessionLocal() as s:
                    await run_repo.update_run(s, run_id, current_node=name)
                await run_manager.emit(
                    run_id,
                    SSEEvent(type="node_start", data={"node": name, "label": label}),
                )
                await run_manager.emit(
                    run_id,
                    SSEEvent(type="agent_status", data={"label": label, "status": "正在处理"}),
                )
            try:
                result = await fn(state)
            except Exception as e:
                if run_id:
                    await run_manager.emit(
                        run_id,
                        SSEEvent(
                            type="node_error",
                            data={"node": name, "label": label, "error": str(e)},
                        ),
                    )
                raise
            if run_id:
                await run_manager.emit(
                    run_id,
                    SSEEvent(type="node_end", data={"node": name, "label": label}),
                )
            return result

        return wrapper

    return deco
