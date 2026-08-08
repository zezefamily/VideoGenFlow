"""Web UI: 爆款心理学短视频制作大师（Chatbot 交互式）

使用 Gradio 构建，对话式引导用户完成脚本 -> 分镜 -> 出图全流程。
启动后访问 http://127.0.0.1:7860
"""

import json
import gradio as gr
import gradio_client.utils as _gc_utils

# Fix: Gradio bug where boolean JSON schemas cause errors in Gallery component
_orig_schema_parse = _gc_utils._json_schema_to_python_type
def _patched_schema_parse(schema, defs=None):
    if isinstance(schema, bool):
        return "Any"
    return _orig_schema_parse(schema, defs)
_gc_utils._json_schema_to_python_type = _patched_schema_parse

from viral_agent import run_streaming
from viral_agent.tools import generate_storyboard
from viral_agent.image_gen import generate_storyboard_images
from viral_agent.storage import init_db, save_record, list_records, update_storyboard, update_storyboard_images
from viral_agent.prompts import STORYBOARD_STYLES, STORYBOARD_ASPECT_RATIOS
from viral_agent.chat_router import route_message

init_db()


# ============================================================
# 辅助函数
# ============================================================

def _format_storyboard(result_json: str) -> str:
    """将分镜 JSON 格式化为 Markdown 表格"""
    try:
        storyboard = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        return f"**分镜解析失败**\n\n{result_json[:500]}"

    if isinstance(storyboard, dict) and "error" in storyboard:
        return f"**分镜生成失败**: {storyboard['error']}"

    if not isinstance(storyboard, list):
        return f"**分镜格式异常**\n\n{result_json[:500]}"

    md = "| 镜号 | 时长 | 戏剧功能 | 文生图提示词 | 图生视频提示词 | 口播片段 | 字幕 | 音效 |\n"
    md += "|------|------|---------|-------------|--------------|----------|------|------|\n"
    total_duration = 0
    for shot in storyboard:
        total_duration += shot.get("duration", 0)
        md += (
            f"| {shot.get('shot_number', '')} "
            f"| {shot.get('duration', 0)}s "
            f"| {shot.get('shot_function', '')} "
            f"| {shot.get('image_prompt', '')} "
            f"| {shot.get('video_prompt', '')} "
            f"| {shot.get('voiceover', '')} "
            f"| {shot.get('text_overlay', '')} "
            f"| {shot.get('sound', '')} |\n"
        )
    md += f"\n**总时长**: {total_duration}秒 | **分镜数**: {len(storyboard)}"
    return md


def _load_history_data():
    """加载历史记录用于 Dataframe 展示"""
    records = list_records(limit=20)
    data = []
    for r in records:
        data.append([
            r["id"],
            r["created_at"],
            r["user_input"][:50] + ("..." if len(r.get("user_input", "")) > 50 else ""),
            r.get("video_title", "") or "-",
            r.get("video_author", "") or "-",
            r.get("extract_method", "") or "-",
            r.get("like_count", 0) or 0,
            r.get("topics", "") or "-",
            r["status"],
        ])
    return data


def refresh_history():
    return _load_history_data()


# ============================================================
# 对话状态常量
# ============================================================

STEP_IDLE = "idle"
STEP_SCRIPT_READY = "script_ready"
STEP_STORYBOARD_READY = "storyboard_ready"
STEP_IMAGE_READY = "image_ready"


def _is_regenerate(msg: str) -> bool:
    """旧版兜底：关键词匹配（LLM 路由失败时用）"""
    msg = msg.strip()
    return msg == "1" or "重新" in msg

def _is_proceed(msg: str) -> bool:
    """旧版兜底：关键词匹配（LLM 路由失败时用）"""
    msg = msg.strip()
    return msg == "2" or "分镜" in msg or "图片" in msg or "继续" in msg


# ============================================================
# 流式处理函数
# ============================================================

def _stream_agent(user_input, history, state):
    """Agent 流式执行，yield (history, state, gallery_items)"""
    state["step"] = "agent_running"
    state["user_input"] = user_input
    state["script"] = ""
    state["storyboard_json"] = ""

    progress_lines = []
    history.append({"role": "assistant", "content": "🚀 正在为你创作..."})
    yield history, state, []

    for event, steps in run_streaming(user_input):
        etype = event["type"]

        if etype == "step_start":
            step_count = len(progress_lines) + 1
            tool_name = event["tool"]
            progress_lines.append(f"⏳ 步骤 {step_count}: `{tool_name}` 执行中...")
            history[-1]["content"] = "🚀 正在为你创作...\n\n" + "\n".join(progress_lines)
            yield history, state, []

        elif etype == "step_end":
            if progress_lines:
                progress_lines[-1] = progress_lines[-1].replace("⏳", "✅").replace("执行中...", "完成")
            history[-1]["content"] = "🚀 正在为你创作...\n\n" + "\n".join(progress_lines)
            yield history, state, []

        elif etype == "step_error":
            if progress_lines:
                progress_lines[-1] = progress_lines[-1].replace("⏳", "❌").replace(
                    "执行中...", f"错误: {event['error'][:80]}"
                )
            history[-1]["content"] = "🚀 正在为你创作...\n\n" + "\n".join(progress_lines)
            yield history, state, []

        elif etype == "finish":
            output = event["output"]
            rid = 0
            try:
                rid = save_record(user_input, output, steps)
            except Exception:
                pass

            state["step"] = STEP_SCRIPT_READY
            state["script"] = output
            state["record_id"] = rid

            # 尝试解析结构化脚本
            script_title = ""
            script_keywords = ""
            script_duration = 0
            script_content = output
            script_golden_sentence = ""
            script_psychology_theory = ""
            script_interaction_guide = ""

            try:
                script_data = json.loads(output)
                script_title = script_data.get("title", "")
                keywords = script_data.get("keywords", [])
                if keywords and isinstance(keywords, list):
                    script_keywords = ",".join(keywords)
                elif keywords and isinstance(keywords, str):
                    script_keywords = keywords
                script_duration = script_data.get("duration_sec", 0)
                script_content = script_data.get("content", output)
                script_golden_sentence = script_data.get("golden_sentence", "")
                script_psychology_theory = script_data.get("psychology_theory", "")
                script_interaction_guide = script_data.get("interaction_guide", "")
            except (json.JSONDecodeError, TypeError):
                script_content = output

            progress_lines.append("🎉 脚本已生成！")
            history[-1]["content"] = "🚀 正在为你创作...\n\n" + "\n".join(progress_lines)

            # 构建结构化展示
            parts = []
            if script_title:
                parts.append(f"### 📺 {script_title}")
            if script_keywords:
                parts.append(f"**关键词**：{script_keywords}")
            if script_psychology_theory:
                parts.append(f"**心理学理论**：{script_psychology_theory}")
            if script_duration:
                parts.append(f"**预估时长**：{script_duration}秒")
            parts.append(f"\n{script_content}")
            if script_golden_sentence:
                parts.append(f"\n---\n\n💎 **金句**：{script_golden_sentence}")
            if script_interaction_guide:
                parts.append(f"🙋 **互动引导**：{script_interaction_guide}")

            parts.append(f"\n---\n\n请问你需要：\n1. 🔄 重新生成脚本\n2. 🎬 生成分镜\n\n请回复 **1** 或 **2**")

            history.append({"role": "assistant", "content": "\n".join(parts)})
            yield history, state, []

        elif etype == "error":
            state["step"] = STEP_IDLE
            progress_lines.append(f"❌ 错误: {event['error'][:200]}")
            history[-1]["content"] = "🚀 正在为你创作...\n\n" + "\n".join(progress_lines)
            yield history, state, []
            return


def _run_storyboard(state, style, aspect_ratio_label, history):
    """分镜生成，yield (history, state, gallery_items)"""
    state["step"] = "storyboard_running"

    aspect_ratio = STORYBOARD_ASPECT_RATIOS.get(aspect_ratio_label, "16:9")
    script = state.get("script", "")
    rid = state.get("record_id", 0)

    # 只传 content 给分镜生成，而不是整个 JSON
    try:
        script_data = json.loads(script)
        script_for_storyboard = script_data.get("content", script)
    except (json.JSONDecodeError, TypeError):
        script_for_storyboard = script

    history.append({"role": "assistant", "content":
        f"🎬 正在生成分镜...\n\n风格：{style} | 比例：{aspect_ratio}"
    })
    yield history, state, []

    result = generate_storyboard(script_for_storyboard, style, aspect_ratio)

    if rid and rid > 0:
        try:
            update_storyboard(rid, result, style, aspect_ratio)
        except Exception:
            pass

    state["step"] = STEP_STORYBOARD_READY
    state["storyboard_json"] = result

    formatted = _format_storyboard(result)

    history[-1]["content"] = (
        f"🎬 分镜生成完成！\n\n**风格**：{style} | **比例**：{aspect_ratio}\n\n"
        f"{formatted}\n\n---\n\n"
        f"请问你需要：\n1. 🔄 重新生成分镜\n2. 🎨 批量生成分镜图\n\n请回复 **1** 或 **2**"
    )
    yield history, state, []


def _stream_images(state, aspect_ratio_label, history):
    """图片批量生成，yield (history, state, gallery_items)"""
    state["step"] = "image_running"

    aspect_ratio = STORYBOARD_ASPECT_RATIOS.get(aspect_ratio_label, "16:9")
    storyboard_json = state.get("storyboard_json", "")
    rid = state.get("record_id", 0)

    gallery_items = []
    progress_lines = []

    history.append({"role": "assistant", "content": "🎨 正在生成分镜图..."})
    yield history, state, gallery_items

    for event in generate_storyboard_images(storyboard_json, aspect_ratio, rid):
        etype = event["type"]

        if etype == "shot_start":
            method_label = "文生图" if event["method"] == "text2image" else "图生图"
            progress_lines.append(f"⏳ 镜号 {event['shot_number']}/{event['total']} - {method_label}")
            history[-1]["content"] = "🎨 正在生成分镜图...\n\n" + "\n".join(progress_lines)
            yield history, state, gallery_items

        elif etype == "shot_done":
            local_path = event.get("local_path")
            if local_path:
                gallery_items.append((local_path, f"镜号 {event['shot_number']}"))
            if progress_lines:
                progress_lines[-1] = progress_lines[-1].replace("⏳", "✅")
            history[-1]["content"] = "🎨 正在生成分镜图...\n\n" + "\n".join(progress_lines)
            yield history, state, gallery_items

        elif etype == "shot_error":
            if progress_lines:
                progress_lines[-1] = progress_lines[-1].replace("⏳", "❌") + f" - {event['error'][:50]}"
            history[-1]["content"] = "🎨 正在生成分镜图...\n\n" + "\n".join(progress_lines)
            yield history, state, gallery_items

        elif etype == "all_done":
            if rid and rid > 0:
                try:
                    images_json = json.dumps(event.get("images", []), ensure_ascii=False)
                    update_storyboard_images(rid, images_json)
                except Exception:
                    pass

            success = event.get("success_count", 0)
            fail = event.get("fail_count", 0)

            if success == 0:
                # 全部失败：留在 STORYBOARD_READY，允许用户重试
                state["step"] = STEP_STORYBOARD_READY
                history[-1]["content"] = (
                    "🎨 正在生成分镜图...\n\n" + "\n".join(progress_lines) +
                    f"\n\n❌ 全部失败！成功 0 张，失败 {fail} 张\n\n"
                    "可能原因：API 参数错误或网络问题。\n\n"
                    "请回复 **1** 重新生成分镜，或 **2** 再次尝试生成分镜图。"
                )
            else:
                # 至少有部分成功
                state["step"] = STEP_IMAGE_READY
                history[-1]["content"] = (
                    "🎨 正在生成分镜图...\n\n" + "\n".join(progress_lines) +
                    f"\n\n🎉 全部完成！成功 {success} 张，失败 {fail} 张\n\n"
                    "全部流程已完成！输入新的话题可以重新开始。"
                )
            yield history, state, gallery_items
            return


# ============================================================
# 主对话处理器
# ============================================================

def chat_handler(message, history, state, style, aspect_ratio_label):
    """主对话处理器 - LLM 意图路由 + 状态机分支"""
    if history is None:
        history = []
    if state is None:
        state = {"step": STEP_IDLE, "user_input": "", "script": "", "storyboard_json": "", "record_id": 0}

    step = state.get("step", STEP_IDLE)

    # 将用户消息加入历史
    history = list(history) + [{"role": "user", "content": message}]

    # Agent 执行中，直接拦截
    if step in ("agent_running", "storyboard_running", "image_running"):
        history.append({"role": "assistant", "content": "⏳ 正在处理中，请稍候..."})
        yield history, state, []
        return

    # LLM 意图路由（一次调用，判断意图 + 生成闲聊回复）
    try:
        route = route_message(message, step)
        is_task = route.is_task
        task_type = route.task_type
    except Exception:
        # LLM 路由失败，降级为关键词匹配
        is_task = not (len(message.strip()) <= 2 and not message.startswith("http"))
        task_type = "new_task"
        if step == STEP_SCRIPT_READY:
            if _is_regenerate(message):
                task_type = "regenerate"
            elif _is_proceed(message):
                task_type = "proceed"
            else:
                is_task = False
        elif step == STEP_STORYBOARD_READY:
            if _is_regenerate(message):
                task_type = "regenerate"
            elif _is_proceed(message):
                task_type = "proceed"
            else:
                is_task = False

    # 闲聊：返回 LLM 生成的引导回复
    if not is_task:
        reply = route.reply if "route" in dir() else "请告诉我你想创作什么方向的心理学短视频，或者直接粘贴抖音分享链接。"
        history.append({"role": "assistant", "content": reply})
        yield history, state, []
        return

    # 任务：根据阶段 + task_type 分发
    if step in (STEP_IDLE, STEP_IMAGE_READY):
        # 新一轮创作
        yield from _stream_agent(message, history, state)

    elif step == STEP_SCRIPT_READY:
        if task_type == "regenerate":
            yield from _stream_agent(state.get("user_input", ""), history, state)
        elif task_type == "proceed":
            yield from _run_storyboard(state, style, aspect_ratio_label, history)
        else:
            # task_type=new_task 但当前阶段有未完成的流程，默认进入分镜
            yield from _run_storyboard(state, style, aspect_ratio_label, history)

    elif step == STEP_STORYBOARD_READY:
        if task_type == "regenerate":
            yield from _run_storyboard(state, style, aspect_ratio_label, history)
        elif task_type == "proceed":
            yield from _stream_images(state, aspect_ratio_label, history)
        else:
            yield from _stream_images(state, aspect_ratio_label, history)


# ============================================================
# UI 布局
# ============================================================

with gr.Blocks(
    title="爆款心理学短视频制作大师",
    theme=gr.themes.Soft(),
    css="""
    .footer { text-align: center; color: #999; font-size: 12px; margin-top: 20px; }
    """,
) as app:

    # 对话状态
    conv_state = gr.State({"step": STEP_IDLE, "user_input": "", "script": "", "storyboard_json": "", "record_id": 0})

    # 标题
    gr.Markdown("# 🎬 爆款心理学短视频制作大师\n输入话题或抖音分享链接，AI 引导你一步步完成脚本 + 分镜 + 出图")

    # 画面设置
    with gr.Row():
        style_dropdown = gr.Dropdown(
            choices=list(STORYBOARD_STYLES.keys()),
            value="黑板粉笔手绘风",
            label="画面风格",
            scale=1,
        )
        aspect_ratio_dropdown = gr.Dropdown(
            choices=list(STORYBOARD_ASPECT_RATIOS.keys()),
            value="16:9 横屏",
            label="画面比例",
            scale=1,
        )

    # 对话区
    chatbot = gr.Chatbot(
        type="messages",
        value=[{"role": "assistant", "content":
            "👋 你好！我是爆款心理学短视频制作大师。\n\n"
            "请告诉我你想创作什么方向的心理学短视频，或者直接粘贴抖音分享链接作为参考。\n\n"
            "例如：\n"
            "- 帮我写一个关于讨好型人格的脚本\n"
            "- 做一个关于情绪内耗的口播文案\n"
            "- [抖音分享链接]"
        }],
        height=500,
    )

    # 输入框 + 发送按钮
    with gr.Row():
        msg_input = gr.Textbox(
            placeholder="输入你的需求，按 Enter 或点击发送...",
            lines=2,
            show_label=False,
            scale=9,
        )
        send_btn = gr.Button("发送", variant="primary", scale=1)

    # 分镜图预览
    images_gallery = gr.Gallery(
        label="分镜图预览",
        show_label=True,
        columns=4,
        height="auto",
    )

    # 历史记录
    with gr.Accordion("📚 历史记录", open=False):
        history_df = gr.Dataframe(
            headers=["ID", "时间", "用户输入", "视频标题", "作者", "提取方式", "点赞数", "话题", "状态"],
            datatype=["number", "str", "str", "str", "str", "str", "number", "str", "str"],
            value=_load_history_data(),
            interactive=False,
            wrap=True,
        )
        refresh_btn = gr.Button("🔄 刷新历史记录", size="sm")

    # 页脚
    gr.Markdown(
        "<p class='footer'>Powered by LangChain + DeepSeek | 爆款心理学短视频制作大师 v2.0</p>",
        elem_classes=["footer"],
    )

    # ============================================================
    # 事件绑定
    # ============================================================

    # 发送事件：回车 + 按钮点击都触发
    send_events = [msg_input.submit, send_btn.click]
    for event in send_events:
        event(
            fn=chat_handler,
            inputs=[msg_input, chatbot, conv_state, style_dropdown, aspect_ratio_dropdown],
            outputs=[chatbot, conv_state, images_gallery],
        ).then(
            fn=lambda: "",
            outputs=[msg_input],
        ).then(
            fn=refresh_history,
            outputs=[history_df],
        )

    refresh_btn.click(fn=refresh_history, outputs=[history_df])


if __name__ == "__main__":
    app.launch(show_api=False)
