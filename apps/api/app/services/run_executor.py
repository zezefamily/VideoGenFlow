"""运行执行器:后台跑图,把图事件(token/节点/产物)推入 RunManager 队列。

POST 发消息后由后台任务调用;真正的 SSE 流由 GET /api/runs/{id}/stream 消费队列。
"""

import asyncio
import json
import traceback

from langchain_core.messages import AIMessageChunk

from app.db import AsyncSessionLocal
from app.repositories import message_repo, run_repo, script_repo, storyboard_repo
from app.schemas.events import SSEEvent
from app.services.run_manager import run_manager

# 后台任务引用,防止被 GC 回收
_bg_tasks: set = set()

# 完成后队列保留时长,供晚到的 SSE 客户端拉取
_GRACE_SECONDS = 60


async def execute_run(
    graph,
    conversation_id: str,
    run_id: str,
    user_message_id: str,
    thread_id: str,
    user_input: str,
    owner_id: str = "",
) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    input_state = {
        "user_id": owner_id,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "user_input": user_input,
        "run_status": "running",
    }

    try:
        # 1. 流式跑图,只转发 respond 节点的 LLM token
        async for chunk, metadata in graph.astream(
            input_state, config, stream_mode="messages"
        ):
            if (
                isinstance(chunk, AIMessageChunk)
                and isinstance(metadata, dict)
                and metadata.get("langgraph_node") == "respond"
            ):
                text = chunk.content or ""
                if text:
                    await run_manager.emit(
                        run_id, SSEEvent(type="token", data={"text": text})
                    )

        # 2. 取最终状态
        snapshot = await graph.aget_state(config)
        v = snapshot.values
        final_text = v.get("final_text", "") or ""
        message_type = v.get("message_type", "text")
        artifact_id = v.get("artifact_id")
        script = v.get("script")
        storyboard = v.get("storyboard")
        images = v.get("images")
        video_analysis = v.get("video_analysis")

        # 3. 若已被取消,不再落库
        async with AsyncSessionLocal() as s:
            run = await run_repo.get_run(s, run_id)
        if run is not None and run.status == "cancelled":
            return

        # 4. 持久化助手消息 + 更新 run
        async with AsyncSessionLocal() as s:
            msg = await message_repo.create_message(
                s,
                conversation_id,
                "assistant",
                final_text,
                message_type=message_type,
                artifact_id=artifact_id,
                status="complete",
            )
            await run_repo.update_run(s, run_id, status="completed")
            artifact = None
            artifact_sb = None
            if message_type == "script_card" and artifact_id:
                sv = await script_repo.get_script(s, artifact_id)
                if sv is not None:
                    artifact = script_repo.to_artifact_dict(sv)
            elif message_type == "storyboard_card" and artifact_id:
                sb = await storyboard_repo.get_storyboard(s, artifact_id)
                if sb is not None:
                    artifact_sb = storyboard_repo.to_artifact_dict(sb)

        # 5. 推送产物与最终消息事件
        if message_type == "script_card" and script:
            await run_manager.emit(
                run_id, SSEEvent(type="artifact", data={"script": script})
            )
            await run_manager.emit(
                run_id, SSEEvent(type="token", data={"text": final_text})
            )
        elif message_type == "storyboard_card" and storyboard:
            await run_manager.emit(
                run_id, SSEEvent(type="artifact", data={"storyboard": storyboard})
            )
            await run_manager.emit(
                run_id, SSEEvent(type="token", data={"text": final_text})
            )
        elif message_type == "image_gallery":
            # 图片画廊:推送初始 pending 列表 + 简介;后续进度由前端轮询
            await run_manager.emit(
                run_id, SSEEvent(type="artifact", data={"images": images or []})
            )
            await run_manager.emit(
                run_id, SSEEvent(type="token", data={"text": final_text})
            )
        elif message_type == "video_analysis_card":
            # 视频分析卡片:推送 pending 分析 + 简介;后续进度由前端轮询
            await run_manager.emit(
                run_id,
                SSEEvent(type="artifact", data={"video_analysis": video_analysis or {}}),
            )
            await run_manager.emit(
                run_id, SSEEvent(type="token", data={"text": final_text})
            )

        # 配音/成片由后台任务继续执行。创建记录后立即把 pending 产物推给前端，
        # 避免对话 run 结束与首次轮询之间出现“没有任何状态”的空窗。
        if v.get("intent") == "generate_tts" and v.get("audio"):
            await run_manager.emit(
                run_id, SSEEvent(type="artifact", data={"audio": v["audio"]})
            )
        elif v.get("intent") == "render_video" and v.get("video"):
            await run_manager.emit(
                run_id, SSEEvent(type="artifact", data={"video": v["video"]})
            )

        await run_manager.emit(
            run_id,
            SSEEvent(
                type="message_saved",
                data={
                    "message": {
                        "id": msg.id,
                        "role": "assistant",
                        "content": final_text,
                        "message_type": message_type,
                        "artifact_id": artifact_id,
                        "artifact": artifact,
                        "storyboard": artifact_sb,
                    }
                },
            ),
        )
        await run_manager.emit(run_id, SSEEvent(type="done", data={}))

    except Exception as e:
        tb = traceback.format_exc()
        try:
            async with AsyncSessionLocal() as s:
                await message_repo.create_message(
                    s,
                    conversation_id,
                    "assistant",
                    f"出错了：{type(e).__name__}",
                    message_type="error",
                    status="error",
                )
                await run_repo.update_run(
                    s,
                    run_id,
                    status="error",
                    error_json=json.dumps(
                        {"error": str(e), "trace": tb[:2000]},
                        ensure_ascii=False,
                    ),
                )
        except Exception:
            pass
        await run_manager.emit(
            run_id, SSEEvent(type="error", data={"error": str(e)})
        )
        await run_manager.emit(run_id, SSEEvent(type="done", data={}))

    finally:
        # 保留队列一段时间,供晚到的客户端拉取终态
        await asyncio.sleep(_GRACE_SECONDS)
        run_manager.unregister(run_id)


def launch_run(
    graph,
    conversation_id: str,
    run_id: str,
    user_message_id: str,
    thread_id: str,
    user_input: str,
    owner_id: str = "",
) -> asyncio.Task:
    """在后台启动一次运行,返回任务对象。"""
    task = asyncio.create_task(
        execute_run(
            graph,
            conversation_id,
            run_id,
            user_message_id,
            thread_id,
            user_input,
            owner_id=owner_id,
        )
    )
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task
