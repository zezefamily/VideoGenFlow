"""Phase 3 端到端验证:生成脚本 -> 生成分镜 -> 单镜修改 -> 取版本 -> 回退。"""

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def consume_stream(client, run_id, label):
    events = []
    tokens = []
    async with client.stream(
        "GET", f"{BASE}/api/runs/{run_id}/stream", timeout=180
    ) as resp:
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            et = data.get("type")
            events.append((et, data))
            if et == "token":
                tokens.append(data.get("data", {}).get("text", ""))
            if et in ("done", "error"):
                break
    print(f"[{label}] events: {[e[0] for e in events]}")
    print(f"[{label}] intro: {''.join(tokens)[:160]!r}")
    return events


def get_artifact(events, key):
    for t, d in events:
        if t == "artifact":
            return d["data"].get(key)
    return None


async def main():
    async with httpx.AsyncClient() as client:
        assert (await client.get(f"{BASE}/api/health")).json()["status"] == "ok"

        conv = (await client.post(f"{BASE}/api/conversations", json={"title": "Phase3 E2E"})).json()
        conv_id = conv["id"]
        print("conversation:", conv_id)

        # 1. 生成脚本
        r = await client.post(
            f"{BASE}/api/conversations/{conv_id}/messages",
            json={"content": "写一个关于「情绪内耗」的爆款心理学短视频脚本"},
        )
        ev = await consume_stream(client, r.json()["run_id"], "script")
        script = get_artifact(ev, "script")
        assert script and script["content"], "脚本未生成"
        print("script v1:", script["version"], script["title"])

        # 2. 生成分镜(竖屏)
        r = await client.post(
            f"{BASE}/api/conversations/{conv_id}/messages",
            json={"content": "生成竖屏分镜"},
        )
        ev = await consume_stream(client, r.json()["run_id"], "storyboard")
        sb = get_artifact(ev, "storyboard")
        assert sb and sb["shots"], "分镜未生成"
        assert sb["aspect_ratio"] == "9:16", f"比例应为9:16, 实际{sb['aspect_ratio']}"
        print(f"storyboard v1: {sb['version']}, {sb['shot_count']} 镜, "
              f"{sb['total_duration_sec']}s, {sb['aspect_ratio']}")
        for sh in sb["shots"]:
            print(f"  镜{sh['index']} [{sh['camera']}] {sh['title']}: {sh['visual'][:40]}")
        v1_id = sb["id"]
        v1_shots = sb["shots"]
        v1_shot3 = v1_shots[2]["visual"] if len(v1_shots) >= 3 else None

        # 3. 取分镜版本
        r = await client.get(f"{BASE}/api/conversations/{conv_id}/storyboard")
        detail = r.json()
        print("storyboard versions:", [(v["version"], v["is_active"]) for v in detail["versions"]])
        assert len(detail["versions"]) == 1

        # 4. 单镜修改:只改第3镜
        r = await client.post(
            f"{BASE}/api/conversations/{conv_id}/messages",
            json={"content": "把第3镜的画面改成女性主角在雨中独行，其他镜头不要动"},
        )
        ev = await consume_stream(client, r.json()["run_id"], "revise-sb")
        sb2 = get_artifact(ev, "storyboard")
        assert sb2 and sb2["shots"], "修改后分镜未返回"
        print(f"storyboard v2: {sb2['version']}, {sb2['shot_count']} 镜")
        v2_shots = sb2["shots"]
        v2_shot3 = v2_shots[2]["visual"] if len(v2_shots) >= 3 else None

        # 5. 校验:第3镜变了,其余镜头 visual 逐字不变
        assert len(v2_shots) == len(v1_shots), "镜头数不应变"
        changed = 0
        for a, b in zip(v1_shots, v2_shots):
            if a["visual"] != b["visual"]:
                changed += 1
        print(f"visual 变更的镜头数: {changed}")
        assert changed == 1, f"应只有1镜变化, 实际{changed}"
        if v1_shot3 and v2_shot3:
            assert v1_shot3 != v2_shot3, "第3镜应已变化"
            assert "女" in v2_shot3 or "雨" in v2_shot3, f"第3镜应含女性/雨, 实际: {v2_shot3}"
        # 其余镜头 visual 完全一致
        for i, (a, b) in enumerate(zip(v1_shots, v2_shots)):
            if i != 2:
                assert a["visual"] == b["visual"], f"镜{i+1}不应变"
        print("✓ 仅第3镜变化,其余逐字保留")

        # 6. 版本数=2, v2 激活
        r = await client.get(f"{BASE}/api/conversations/{conv_id}/storyboard")
        detail2 = r.json()
        print("after revise versions:", [(v["version"], v["is_active"]) for v in detail2["versions"]])
        assert len(detail2["versions"]) == 2
        active = [v for v in detail2["versions"] if v["is_active"]]
        assert active[0]["version"] == 2

        # 7. 回退到 v1
        r = await client.post(f"{BASE}/api/artifacts/{v1_id}/activate")
        rolled = r.json()
        print("rolled back:", rolled["type"], "v?", rolled.get("storyboard", {}).get("version"))
        assert rolled["type"] == "storyboard"
        r = await client.get(f"{BASE}/api/conversations/{conv_id}/storyboard")
        active3 = [v for v in r.json()["versions"] if v["is_active"]]
        assert active3[0]["version"] == 1, "回退后 v1 应激活"
        print("✓ 回退到 v1 生效")

        print("\n=== ALL PHASE 3 E2E CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
