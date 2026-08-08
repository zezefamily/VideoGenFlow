"""工具模块：4 个自定义工具

- extract_douyin_script: 从抖音分享链接提取视频文案
- research_trending_topics: 研究热门心理学话题
- analyze_viral_structure: 分析参考文案的爆款结构
- generate_voiceover_script: 生成原创口播脚本
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm
from viral_agent.media import extract_script_from_video
from viral_agent.prompts import (
    TRENDING_RESEARCH_PROMPT,
    VIRAL_ANALYSIS_PROMPT,
    SCRIPT_GENERATION_PROMPT,
    SCRIPT_EXPAND_PROMPT,
    SCRIPT_SHORTEN_PROMPT,
    STORYBOARD_PROMPT,
    STORYBOARD_STYLES,
    STORYBOARD_ASPECT_RATIOS,
)


# ============================================================
# Tool 1: extract_douyin_script
# ============================================================

def _parse_douyin_page(html: str) -> Optional[str]:
    """从抖音页面 HTML 中提取视频描述文案"""
    soup = BeautifulSoup(html, "lxml")

    # 方法 1: meta og:description
    meta = soup.find("meta", property="og:description")
    if meta and meta.get("content"):
        return meta["content"].strip()

    # 方法 2: meta name=description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    # 方法 3: 从 script 标签中的 JSON 数据提取
    for script_tag in soup.find_all("script"):
        text = script_tag.string or ""
        # 尝试找 RENDER_DATA 或 _ROUTER_DATA
        if "RENDER_DATA" in text or "_ROUTER_DATA" in text:
            # 尝试提取 desc 字段
            desc_match = re.search(r'"desc"\s*:\s*"([^"]+)"', text)
            if desc_match:
                return desc_match.group(1).strip()

    # 方法 4: 正则搜索 desc 字段
    desc_match = re.search(r'"desc"\s*:\s*"([^"]{10,})"', html)
    if desc_match:
        return desc_match.group(1).strip()

    return None


@tool
def extract_douyin_script(share_link: str) -> str:
    """从抖音分享链接中提取视频口播文案及元信息。
    支持三种提取方式（自动降级）：
    1. 下载字幕文件（最快最准）
    2. 下载视频 -> 提取音频 -> 语音识别转文字
    3. 抓取页面描述（兜底）
    输入抖音分享链接（如 https://v.douyin.com/xxxxx/），
    返回 JSON 字符串，包含 title, author, duration, like_count,
    video_url, description, tags, topics, extract_method, script 等字段。
    """
    # 验证 URL
    if "douyin.com" not in share_link and "iesdouyin.com" not in share_link:
        return json.dumps({
            "success": False,
            "error": "不是有效的抖音链接",
            "share_link": share_link,
            "suggestion": "请提供抖音分享链接，或直接粘贴参考视频的脚本文本。",
        }, ensure_ascii=False, indent=2)

    # ============================================================
    # Tier 1 + Tier 2: 视频管线（字幕下载 -> 视频下载+ASR）
    # ============================================================
    script_text, method, video_info = extract_script_from_video(share_link)
    if script_text:
        method_label = "字幕提取" if method == "subtitle" else "语音识别"
        result = {
            "success": True,
            "share_link": share_link,
            "title": video_info.get("title", ""),
            "author": video_info.get("author", ""),
            "duration": video_info.get("duration", 0),
            "like_count": video_info.get("like_count", 0),
            "view_count": video_info.get("view_count", 0),
            "comment_count": video_info.get("comment_count", 0),
            "video_url": video_info.get("video_url", ""),
            "webpage_url": video_info.get("webpage_url", ""),
            "description": video_info.get("description", ""),
            "tags": video_info.get("tags", []),
            "topics": video_info.get("topics", []),
            "extract_method": method,
            "extract_method_label": method_label,
            "script": script_text,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ============================================================
    # Tier 3: 降级到 HTML 页面抓取
    # ============================================================
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.0 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        response = requests.get(
            share_link,
            headers=headers,
            allow_redirects=True,
            timeout=10,
        )
        response.encoding = "utf-8"

        page_desc = _parse_douyin_page(response.text)
        # 从页面描述中提取 #话题标签
        topics = re.findall(r'#([^\s#]+)', page_desc or "")

        if page_desc:
            result = {
                "success": True,
                "share_link": share_link,
                "title": video_info.get("title", ""),
                "author": video_info.get("author", ""),
                "duration": video_info.get("duration", 0),
                "like_count": video_info.get("like_count", 0),
                "view_count": video_info.get("view_count", 0),
                "comment_count": video_info.get("comment_count", 0),
                "video_url": video_info.get("video_url", ""),
                "webpage_url": video_info.get("webpage_url", ""),
                "description": page_desc,
                "tags": video_info.get("tags", []),
                "topics": topics,
                "extract_method": "page_desc",
                "extract_method_label": "页面描述（可能不完整）",
                "script": page_desc,
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "无法从视频中提取口播文案",
                "share_link": share_link,
                "video_info": video_info,
                "suggestion": "请直接粘贴参考视频的脚本文本。",
            }, ensure_ascii=False, indent=2)

    except requests.exceptions.Timeout:
        return json.dumps({
            "success": False,
            "error": "请求超时：抖音页面加载超时",
            "share_link": share_link,
            "suggestion": "请直接粘贴参考视频的脚本文本。",
        }, ensure_ascii=False, indent=2)
    except requests.exceptions.ConnectionError:
        return json.dumps({
            "success": False,
            "error": "连接失败：无法访问抖音",
            "share_link": share_link,
            "suggestion": "请直接粘贴参考视频的脚本文本。",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"提取失败（{type(e).__name__}）",
            "share_link": share_link,
            "suggestion": "请直接粘贴参考视频的脚本文本。",
        }, ensure_ascii=False, indent=2)


# ============================================================
# Tool 2: research_trending_topics
# ============================================================

# 备用话题列表（LLM 调用失败时使用）
_FALLBACK_TOPICS = """以下是心理学领域的热门话题（备用列表）：

1. 讨好型人格 | 痛点：不敢拒绝别人 | 角度：从童年经历切入 | 金句："你的善良，需要有点锋芒"
2. 情绪内耗 | 痛点：想太多做太少 | 角度：用心理学解释为什么你会内耗 | 金句："内耗的本质，是在用脑子和心打架"
3. 高敏感人群 | 痛点：被说太敏感 | 角度：重新定义敏感是天赋 | 金句："高敏感不是病，是出厂设置不同"
4. 亲密关系中的依恋类型 | 痛点：恋爱中患得患失 | 角度：用依恋理论解释行为模式 | 金句："你不是不爱，是害怕被抛弃"
5. 冒名顶替综合征 | 痛点：总觉得自己不够好 | 角度：成功人士也有的心理现象 | 金句："你不是不配，是大脑在骗你"
6. 边界感 | 痛点：人际关系累 | 角度：教你如何优雅地设边界 | 金句："没有边界感的好人，最后都成了坏人"
7. 原生家庭 | 痛点：重复父母的命运 | 角度：打破代际传递的心理学 | 金句："原生家庭是起点，不是终点"
"""


@tool
def research_trending_topics(psychology_field: str = "") -> str:
    """研究当前抖音心理学领域的热门话题和趋势。
    可选参数：psychology_field 指定心理学细分方向（如"情绪管理"、"人际关系"）。
    返回热门话题列表及其爆款要素分析。
    """
    try:
        llm = get_llm(temperature=0.5)

        field_instruction = ""
        if psychology_field and psychology_field.strip():
            field_instruction = f"请重点关注「{psychology_field}」这个细分方向。"

        prompt = ChatPromptTemplate.from_messages([
            ("system", TRENDING_RESEARCH_PROMPT),
            ("human", "请开始分析。"),
        ])

        chain = prompt | llm
        response = chain.invoke({
            "field_instruction": field_instruction,
        })
        return response.content

    except Exception as e:
        return f"（研究工具异常，使用备用话题库）\n\n{_FALLBACK_TOPICS}"


# ============================================================
# Tool 3: analyze_viral_structure
# ============================================================

@tool
def analyze_viral_structure(script_text: str) -> str:
    """分析参考视频脚本的爆款结构。
    输入参考视频的脚本文本，返回结构化分析结果，
    包括开头钩子、情绪弧线、节奏把控、关键金句、结构模板。
    """
    if not script_text or len(script_text.strip()) < 20:
        return "脚本内容过短，无法进行有效分析。建议提供更完整的参考视频文案。"

    try:
        llm = get_llm(temperature=0.1)

        prompt = ChatPromptTemplate.from_messages([
            ("system", VIRAL_ANALYSIS_PROMPT),
            ("human", "{script_text}"),
        ])

        chain = prompt | llm
        response = chain.invoke({"script_text": script_text})
        return response.content

    except Exception as e:
        return f"分析失败：{type(e).__name__}。请稍后重试或跳过结构分析。"


# ============================================================
# Tool 4: generate_voiceover_script
# ============================================================

def _count_chinese_chars(text: str) -> int:
    """统计中文字符数（粗略估算口播时长）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars if chinese_chars > 0 else len(text)


@tool
def generate_voiceover_script(
    topic: str,
    trending_insights: str,
    structure_analysis: str = "",
) -> str:
    """生成原创心理学短视频口播脚本。
    参数：
    - topic: 视频主题或方向
    - trending_insights: 热门话题研究结果
    - structure_analysis: 参考视频的爆款结构分析（可选）
    返回完整的结构化 JSON 脚本。
    """
    try:
        llm = get_llm(temperature=0.8, response_format={"type": "json_object"})

        structure_ref = structure_analysis if structure_analysis and structure_analysis.strip() else "无参考结构，请根据热门趋势自行设计爆款结构。"

        prompt = ChatPromptTemplate.from_messages([
            ("system", SCRIPT_GENERATION_PROMPT),
            ("human", "请开始创作。"),
        ])

        chain = prompt | llm
        response = chain.invoke({
            "topic": topic if topic else "请根据热门趋势自行选择一个有爆款潜力的心理学话题",
            "trending_insights": trending_insights,
            "structure_analysis": structure_ref,
        })

        result_text = response.content.strip()

        # 尝试提取 JSON
        try:
            data = json.loads(result_text)
        except (json.JSONDecodeError, TypeError):
            # 尝试从 markdown 代码块中提取
            match = re.search(r'```(?:json)?\s*(.+?)\s*```', result_text, re.DOTALL)
            if match:
                data = json.loads(match.group(1).strip())
            else:
                # 提取失败，返回简单结构
                data = {
                    "title": topic[:15] if topic else "心理学脚本",
                    "keywords": ["心理学"],
                    "duration_sec": 60,
                    "content": result_text,
                    "golden_sentence": "",
                    "psychology_theory": "",
                    "interaction_guide": ""
                }

        # 确保 content 存在
        content = data.get("content", "")
        if not content:
            # 找不到 content，用整个结果
            content = result_text
            data["content"] = content

        # 字数校验：200-300 中文字符（只针对 content）
        char_count = _count_chinese_chars(content)

        if char_count < 200:
            # 太短，只扩展 content
            retry_prompt = ChatPromptTemplate.from_messages([
                ("system", SCRIPT_EXPAND_PROMPT),
                ("human", "{script}"),
            ])
            retry_chain = retry_prompt | get_llm(temperature=0.8)
            retry_response = retry_chain.invoke({"script": content})
            data["content"] = retry_response.content.strip()

        elif char_count > 300:
            # 太长，只精简 content
            retry_prompt = ChatPromptTemplate.from_messages([
                ("system", SCRIPT_SHORTEN_PROMPT),
                ("human", "{script}"),
            ])
            retry_chain = retry_prompt | get_llm(temperature=0.8)
            retry_response = retry_chain.invoke({"script": content})
            data["content"] = retry_response.content.strip()

        # 返回完整 JSON
        return json.dumps(data, ensure_ascii=False, indent=2)

    except Exception as e:
        # 出错时返回简单的错误 JSON
        return json.dumps({
            "title": "生成失败",
            "keywords": ["错误"],
            "duration_sec": 0,
            "content": f"脚本生成失败：{type(e).__name__}。请稍后重试。",
            "golden_sentence": "",
            "psychology_theory": "",
            "interaction_guide": ""
        }, ensure_ascii=False, indent=2)


# ============================================================
# 分镜大师：生成 20 个分镜（UI 直接调用，非 Agent 工具）
# ============================================================

def generate_storyboard(script: str, style: str = "黑板粉笔手绘风", aspect_ratio: str = "16:9") -> str:
    """根据口播脚本生成分镜，返回 JSON 字符串

    参数：
    - script: 口播脚本文本
    - style: 画面风格名称（见 STORYBOARD_STYLES）
    - aspect_ratio: 画面比例（如 "16:9"、"9:16"）

    每个分镜包含 image_prompt（文生图）和 video_prompt（图生视频）等字段。
    """
    if not script or len(script.strip()) < 20:
        return json.dumps({"error": "脚本内容过短，无法生成分镜"}, ensure_ascii=False)

    style_desc = STORYBOARD_STYLES.get(style, STORYBOARD_STYLES["黑板粉笔手绘风"])

    try:
        llm = get_llm(temperature=0.3)

        prompt = ChatPromptTemplate.from_messages([
            ("system", STORYBOARD_PROMPT),
            ("human", "{script}"),
        ])

        chain = prompt | llm
        response = chain.invoke({
            "script": script,
            "style": style_desc,
            "aspect_ratio": aspect_ratio,
        })
        raw = response.content.strip()

        # 尝试提取 JSON（LLM 可能包裹在 ```json ... ``` 中）
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        # 验证 JSON 有效性
        storyboard = json.loads(raw)
        if not isinstance(storyboard, list):
            raise ValueError("分镜数据不是数组")

        return json.dumps(storyboard, ensure_ascii=False, indent=2)

    except json.JSONDecodeError:
        return json.dumps({"error": "分镜生成失败：LLM 返回的 JSON 格式无效", "raw": raw[:500]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"分镜生成失败：{type(e).__name__}: {e}"}, ensure_ascii=False)


# ============================================================
# 工具列表导出
# ============================================================
ALL_TOOLS = [
    extract_douyin_script,
    research_trending_topics,
    analyze_viral_structure,
    generate_voiceover_script,
]
