"""加载上下文:从 DB 重建历史消息、当前作品、激活脚本与激活分镜(Phase 3)。

历史消息以 DB 为唯一真源,每轮整体覆盖 state.history(不使用累加 reducer)。
脚本/分镜按 project_id 隔离。
"""

from langchain_core.messages import AIMessage, HumanMessage

from app.db import AsyncSessionLocal
from app.graph.tracking import tracked
from app.repositories import audio_track_repo, message_repo, project_repo, script_repo, storyboard_repo, video_render_repo


@tracked("load_context")
async def load_context(state):
    conv_id = state["conversation_id"]

    async with AsyncSessionLocal() as s:
        msgs = await message_repo.list_messages(s, conv_id)
        history = []
        for m in msgs:
            if m.role == "user":
                history.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                history.append(AIMessage(content=m.content))
        project = await project_repo.get_conversation_project(s, conv_id)
        project_id = project.id if project else None
        active_script = (
            await script_repo.get_active_script(s, project_id)
            if project_id
            else None
        )
        active_storyboard = (
            await storyboard_repo.get_active_storyboard(s, project_id)
            if project_id
            else None
        )
        active_audio = await audio_track_repo.get_active_track(s, project_id) if project_id else None
        active_video = await video_render_repo.get_active_render(s, project_id) if project_id else None

    script = (
        script_repo.to_artifact_dict(active_script) if active_script else None
    )
    storyboard = (
        storyboard_repo.to_artifact_dict(active_storyboard)
        if active_storyboard
        else None
    )
    return {
        "history": history,
        "project_id": project_id,
        "script": script,
        "script_id": script["id"] if script else None,
        "storyboard": storyboard,
        "storyboard_id": storyboard["id"] if storyboard else None,
        "audio": audio_track_repo.to_artifact_dict(active_audio) if active_audio else None,
        "video": video_render_repo.to_artifact_dict(active_video) if active_video else None,
        "active_artifact": storyboard["id"] if storyboard else (script["id"] if script else None),
    }
