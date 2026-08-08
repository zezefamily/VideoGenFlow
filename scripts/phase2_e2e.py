"""Phase 2 端到端验证:建会话 -> 生成脚本 -> 局部修改 -> 取版本 -> 回退。"""

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def consume_stream(client, run_id, label):
    """消费 SSE 流,返回收集到的事件列表(artifacts/tokens/done)。

    服务端用 sse-starlette 的 {"data": json} 形式,event type 在 JSON 的 type 字段里。
    """
    events = []
    tokens = []
    async with client.stream(
        "GET", f"{BASE}/api/runs/{run_id}/stream", timeout=120
    ) as resp:
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            event_type = data.get("type")
            events.append((event_type, data))
            if event_type == "token":
                tokens.append(data.get("data", {}).get("text", ""))
            if event_type in ("done", "error"):
                break
    print(f"[{label}] events: {[e[0] for e in events]}")
    print(f"[{label}] tokens joined: {''.join(tokens)[:200]!r}")
    return events


async def main():
    async with httpx.AsyncClient() as client:
        # 0. health
        h = await client.get(f"{BASE}/api/health")
        print("health:", h.json())

        # 1. 建会话
        r = await client.post(f"{BASE}/api/conversations", json={"title": "Phase2 E2E"})
        conv = r.json()
        conv_id = conv["id"]
        print("conversation:", conv_id)

        # 2. 生成脚本
        r = await client.post(
            f"{BASE}/api/conversations/{conv_id}/messages",
            json={"content": "帮我写一个关于「讨好型人格」的爆款心理学短视频脚本"},
        )
        send = r.json()
        run_id = send["run_id"]
        print("create run:", run_id)
        events = await consume_stream(client, run_id, "create")

        artifact = None
        for t, d in events:
            if t == "artifact":
                artifact = d["data"]["script"]
        if not artifact:
            print("FAIL: 无 artifact"); sys.exit(1)
        print("v1 content:\n", artifact["content"])
        print("v1 version:", artifact["version"], "id:", artifact["id"])
        v1_id = artifact["id"]
        v1_content = artifact["content"]

        # 3. 取作品详情
        r = await client.get(f"{BASE}/api/conversations/{conv_id}/project")
        detail = r.json()
        print("project detail versions:", [v["version"] for v in detail["versions"]])
        assert len(detail["versions"]) == 1, "应有 1 个版本"

        # 4. 局部修改:只改开头
        r = await client.post(
            f"{BASE}/api/conversations/{conv_id}/messages",
            json={"content": "把开头钩子改得更扎心一点，用反问句"},
        )
        send = r.json()
        run_id2 = send["run_id"]
        events2 = await consume_stream(client, run_id2, "revise")
        artifact2 = None
        for t, d in events2:
            if t == "artifact":
                artifact2 = d["data"]["script"]
        if not artifact2:
            print("FAIL: 修改后无 artifact"); sys.exit(1)
        print("v2 content:\n", artifact2["content"])
        print("v2 version:", artifact2["version"], "id:", artifact2["id"])
        v2_content = artifact2["content"]

        # 5. 再次取版本
        r = await client.get(f"{BASE}/api/conversations/{conv_id}/project")
        detail2 = r.json()
        print("after revise versions:", [(v["version"], v["is_active"]) for v in detail2["versions"]])
        assert len(detail2["versions"]) == 2, "应有 2 个版本"
        active = [v for v in detail2["versions"] if v["is_active"]]
        assert len(active) == 1 and active[0]["version"] == 2, "v2 应为激活"

        # 6. 回退到 v1
        r = await client.post(f"{BASE}/api/artifacts/{v1_id}/activate")
        rolled = r.json()
        print("rolled back to version:", rolled["version"], "is_active:", rolled["is_active"])

        r = await client.get(f"{BASE}/api/conversations/{conv_id}/project")
        detail3 = r.json()
        active3 = [v for v in detail3["versions"] if v["is_active"]]
        print("after rollback active version:", active3[0]["version"])
        assert active3[0]["version"] == 1, "回退后 v1 应激活"

        print("\n=== ALL PHASE 2 E2E CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
