"""示例 7：流式输出（Streaming）

逐字返回模型输出，适用于聊天界面、实时回复等场景，
大幅提升用户体验（无需等待完整回复生成）。
"""

from common import get_llm


def main():
    llm = get_llm()

    print("流式输出演示：写一首关于编程的短诗\n")
    print("-" * 50)
    for chunk in llm.stream("写一首关于编程的短诗，4行以内"):
        print(chunk.content, end="", flush=True)
    print("\n" + "-" * 50)
    print("流式输出完成！")


if __name__ == "__main__":
    main()
