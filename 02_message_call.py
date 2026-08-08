"""示例 2：使用 System + Human 消息列表调用"""

from langchain_core.messages import HumanMessage, SystemMessage
from common import get_llm


def main():
    llm = get_llm()
    messages = [
        SystemMessage(content="你是一个资深 Python 开发者，回答简洁明了。"),
        HumanMessage(content="列出 3 个使用 LangChain 的优势。"),
    ]
    response = llm.invoke(messages)
    print(response.content)


if __name__ == "__main__":
    main()
