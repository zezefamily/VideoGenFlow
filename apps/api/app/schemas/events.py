"""SSE 事件 schema(方案第八节)。

事件 type 取值:
- token:LLM 文本 token(增量)
- node_start / node_end:图节点开始/完成
- artifact:结构化卡片(script_card 等)生成
- message_saved:助手消息已落库(携带最终 message)
- error:出错
- done:本次 run 结束
"""

from typing import Any, Optional

from pydantic import BaseModel


class SSEEvent(BaseModel):
    type: str
    data: dict[str, Any] = {}

    def to_sse(self) -> str:
        """序列化为 SSE 数据帧。"""
        import json

        payload = json.dumps(
            {"type": self.type, "data": self.data}, ensure_ascii=False
        )
        return f"data: {payload}\n\n"
