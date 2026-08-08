"""示例 10：批量调用（Batch）

使用 llm.batch() 一次发送多个请求，LangChain 内部并发处理，
比循环调用 invoke() 快得多。适用于批量处理、数据集推理等场景。
"""

from common import get_llm


def main():
    llm = get_llm(temperature=0)

    questions = [
        "1 + 1 等于几？只回答数字。",
        "中国的首都是哪里？只回答城市名。",
        "水的化学式是什么？只回答化学式。",
        "Python 之父是谁？只回答名字。",
        "地球有几颗天然卫星？只回答数字。",
    ]

    print(f"批量发送 {len(questions)} 个请求...\n")

    # batch 一次性并发处理所有请求
    results = llm.batch(questions)

    for i, (q, r) in enumerate(zip(questions, results), 1):
        print(f"Q{i}: {q}")
        print(f"A{i}: {r.content}")
        print()


if __name__ == "__main__":
    main()
