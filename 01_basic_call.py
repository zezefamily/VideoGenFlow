"""示例 1：最简单的直接调用"""

from common import get_llm


def main():
    llm = get_llm()
    response = llm.invoke("用一句话解释什么是 LangChain？")
    print(response.content)


if __name__ == "__main__":
    main()
