"""构建主图(方案第五节 + Phase 2 局部修改 + Phase 3 分镜 + Phase 4 出图 + 抖音链接解析)。

START -> load_context -> classify_intent
  -> [generate_script | revise_script | generate_storyboard | revise_storyboard | generate_images | analyze_video | respond]
  -> respond -> END
"""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.classify_intent import classify_intent
from app.graph.nodes.analyze_video import analyze_video
from app.graph.nodes.generate_images import generate_images
from app.graph.nodes.generate_script import generate_script
from app.graph.nodes.generate_storyboard import generate_storyboard
from app.graph.nodes.generate_tts import generate_tts
from app.graph.nodes.render_video import render_video
from app.graph.nodes.load_context import load_context
from app.graph.nodes.respond import respond
from app.graph.nodes.revise_script import revise_script
from app.graph.nodes.revise_storyboard import revise_storyboard
from app.graph.state import ChatState


def _route_after_classify(state):
    intent = state.get("intent", "chat")
    mapping = {
        "create_script": "generate_script",
        "revise_script": "revise_script",
        "generate_storyboard": "generate_storyboard",
        "revise_storyboard": "revise_storyboard",
        "generate_images": "generate_images",
        "analyze_video": "analyze_video",
        "generate_tts": "generate_tts",
        "render_video": "render_video",
    }
    return mapping.get(intent, "respond")


def build_graph(checkpointer=None):
    g = StateGraph(ChatState)
    g.add_node("load_context", load_context)
    g.add_node("classify_intent", classify_intent)
    g.add_node("generate_script", generate_script)
    g.add_node("revise_script", revise_script)
    g.add_node("generate_storyboard", generate_storyboard)
    g.add_node("revise_storyboard", revise_storyboard)
    g.add_node("generate_images", generate_images)
    g.add_node("analyze_video", analyze_video)
    g.add_node("generate_tts", generate_tts)
    g.add_node("render_video", render_video)
    g.add_node("respond", respond)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "classify_intent")
    g.add_conditional_edges(
        "classify_intent",
        _route_after_classify,
        {
            "generate_script": "generate_script",
            "revise_script": "revise_script",
            "generate_storyboard": "generate_storyboard",
            "revise_storyboard": "revise_storyboard",
            "generate_images": "generate_images",
            "analyze_video": "analyze_video",
            "generate_tts": "generate_tts",
            "render_video": "render_video",
            "respond": "respond",
        },
    )
    for n in (
        "generate_script",
        "revise_script",
        "generate_storyboard",
        "revise_storyboard",
        "generate_images",
        "analyze_video",
        "generate_tts",
        "render_video",
    ):
        g.add_edge(n, "respond")
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer)
