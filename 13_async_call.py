"""示例 13：异步并发调用（Async）

使用 ainvoke / abatch 异步调用大模型，
可以并发处理多个请求，适用于高吞吐量场景（Web 服务、批量处理）。
"""

import asyncio
from common import get_llm


async def main():
    llm = get_llm(temperature=0)

    # 测试 1：单个异步调用
    print("=" * 50)
    print("测试 1：异步单次调用")
    print("=" * 50)
    result = await llm.ainvoke("用一句话解释什么是异步编程")
    print(result.content)
    print()

    # 测试 2：并发多个请求（比循环 invoke 快很多）
    print("=" * 50)
    print("测试 2：并发 3 个请求")
    print("=" * 50)
    questions = [
        "1+1等于几？只回答数字",
        "中国的首都是哪里？只回答城市名",
        "太阳从哪个方向升起？只回答方向",
    ]

    # asyncio.gather 并发执行
    import time
    start = time.time()
    results = await asyncio.gather(*[llm.ainvoke(q) for q in questions])
    elapsed = time.time() - start

    for q, r in zip(questions, results):
        print(f"Q: {q}")
        print(f"A: {r.content}")
    print(f"\n3 个请求并发完成，耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
