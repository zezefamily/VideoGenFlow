"""SQLite 存储模块：保存和查询生成记录"""

import os
import json
import sqlite3
from typing import Optional

# 项目根目录：viral_agent/ 的父目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_DIR = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH = os.path.join(_DB_DIR, "viral_agent.db")


def _get_connection() -> sqlite3.Connection:
    """返回 SQLite 连接（自动创建 DB 文件）"""
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """创建 generation_records 表（如不存在），兼容已有数据库追加列"""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT NOT NULL,
                final_script TEXT,
                steps_json TEXT,
                video_title TEXT,
                video_author TEXT,
                video_url TEXT,
                extract_method TEXT,
                video_duration INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                topics TEXT,
                extracted_script TEXT,
                trending_insights TEXT,
                structure_analysis TEXT,
                storyboard_json TEXT,
                storyboard_style TEXT,
                storyboard_aspect_ratio TEXT,
                storyboard_created_at TIMESTAMP,
                storyboard_images_json TEXT,
                status TEXT DEFAULT 'success',
                script_title TEXT,
                script_keywords TEXT,
                script_duration INTEGER DEFAULT 0,
                script_content TEXT,
                script_golden_sentence TEXT,
                script_psychology_theory TEXT,
                script_interaction_guide TEXT
            )
        """)
        # 兼容已有数据库：逐个追加新列
        new_columns = [
            "storyboard_json", "storyboard_style", "storyboard_aspect_ratio", "storyboard_created_at", "storyboard_images_json",
            "script_title", "script_keywords", "script_duration", "script_content", "script_golden_sentence",
            "script_psychology_theory", "script_interaction_guide"
        ]
        for col in new_columns:
            try:
                conn.execute(f"SELECT {col} FROM generation_records LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE generation_records ADD COLUMN {col} TEXT")
        conn.commit()
    finally:
        conn.close()


def save_record(
    user_input: str,
    final_script: str,
    steps: list,
) -> int:
    """插入一条生成记录，返回记录 ID

    从 steps 中自动提取视频元信息、热门研究、结构分析等字段。
    从 final_script 中解析结构化脚本内容。
    """
    video_title = ""
    video_author = ""
    video_url = ""
    extract_method = ""
    video_duration = 0
    like_count = 0
    comment_count = 0
    topics = ""
    extracted_script = ""
    trending_insights = ""
    structure_analysis = ""

    for step in steps:
        tool = step.get("tool", "")
        output = step.get("output", "")

        if tool == "extract_douyin_script":
            try:
                data = json.loads(output)
                if data.get("success"):
                    video_title = data.get("title", "")
                    video_author = data.get("author", "")
                    video_url = data.get("webpage_url", data.get("share_link", ""))
                    extract_method = data.get("extract_method", "")
                    video_duration = data.get("duration", 0)
                    like_count = data.get("like_count", 0)
                    comment_count = data.get("comment_count", 0)
                    topic_list = data.get("topics", [])
                    # 去重
                    seen = set()
                    unique_topics = []
                    for t in topic_list:
                        if t not in seen:
                            seen.add(t)
                            unique_topics.append(t)
                    topics = ",".join(unique_topics)
                    extracted_script = data.get("script", "")
            except (json.JSONDecodeError, TypeError):
                pass

        elif tool == "research_trending_topics":
            trending_insights = output

        elif tool == "analyze_viral_structure":
            structure_analysis = output

    steps_json = json.dumps(steps, ensure_ascii=False)

    # 解析 final_script 为结构化字段
    script_title = ""
    script_keywords = ""
    script_duration = 0
    script_content = ""
    script_golden_sentence = ""
    script_psychology_theory = ""
    script_interaction_guide = ""

    try:
        script_data = json.loads(final_script)
        script_title = script_data.get("title", "")
        keywords = script_data.get("keywords", [])
        if keywords and isinstance(keywords, list):
            script_keywords = ",".join(keywords)
        elif keywords and isinstance(keywords, str):
            script_keywords = keywords
        script_duration = script_data.get("duration_sec", 0)
        script_content = script_data.get("content", final_script)
        script_golden_sentence = script_data.get("golden_sentence", "")
        script_psychology_theory = script_data.get("psychology_theory", "")
        script_interaction_guide = script_data.get("interaction_guide", "")
    except (json.JSONDecodeError, TypeError):
        # 旧数据不是 JSON，直接用 final_script 作为 content
        script_content = final_script

    conn = _get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO generation_records
               (user_input, final_script, steps_json,
                video_title, video_author, video_url, extract_method,
                video_duration, like_count, comment_count, topics,
                extracted_script, trending_insights, structure_analysis, status,
                script_title, script_keywords, script_duration, script_content,
                script_golden_sentence, script_psychology_theory, script_interaction_guide)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_input, final_script, steps_json,
             video_title, video_author, video_url, extract_method,
             video_duration, like_count, comment_count, topics,
             extracted_script, trending_insights, structure_analysis, "success",
             script_title, script_keywords, script_duration, script_content,
             script_golden_sentence, script_psychology_theory, script_interaction_guide),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_records(limit: int = 20) -> list:
    """返回最近的记录列表（不含 steps_json 等大字段）"""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT id, created_at, user_input, video_title, video_author,
                      video_url, extract_method, video_duration, like_count,
                      comment_count, topics, status
               FROM generation_records
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_record(record_id: int) -> Optional[dict]:
    """获取单条完整记录（含所有字段）"""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM generation_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_storyboard(record_id: int, storyboard_json: str, style: str = "", aspect_ratio: str = ""):
    """更新指定记录的分镜数据"""
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE generation_records
               SET storyboard_json = ?, storyboard_style = ?,
                   storyboard_aspect_ratio = ?, storyboard_created_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (storyboard_json, style, aspect_ratio, record_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_storyboard_images(record_id: int, images_json: str):
    """更新指定记录的分镜图片数据"""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE generation_records SET storyboard_images_json = ? WHERE id = ?",
            (images_json, record_id),
        )
        conn.commit()
    finally:
        conn.close()
