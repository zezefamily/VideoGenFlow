"""示例 8：多轮对话记忆（Memory）

使用 RunnableWithMessageHistory 管理对话历史，
让大模型"记住"之前说过的话，实现真正的多轮对话。
"""

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from common import get_llm


def main():
    llm = get_llm(temperature=0.3)

    # 会话存储（按 session_id 隔离不同用户的对话）
    store = {}

    def get_history(session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        return store[session_id]

    # 带历史消息占位符的 Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个友好的助手，请根据对话上下文回答问题。"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    chain = prompt | llm

    # 包装为带记忆的链
    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_history,
        input_messages_key="input",
        history_messages_key="history",
    )

    # 模拟多轮对话
    config = {"configurable": {"session_id": "user_001"}}

    round1 = chain_with_history.invoke({"input": "我叫小明，今年25岁"}, config=config)
    print(f"用户: 我叫小明，今年25岁")
    print(f"助手: {round1.content}\n")

    round2 = chain_with_history.invoke({"input": "我叫什么名字？"}, config=config)
    print(f"用户: 我叫什么名字？")
    print(f"助手: {round2.content}\n")

    round3 = chain_with_history.invoke({"input": "我多大了？"}, config=config)
    print(f"用户: 我多大了？")
    print(f"助手: {round3.content}\n")

    # 换一个 session_id，验证记忆是隔离的
    config2 = {"configurable": {"session_id": "user_002"}}
    round4 = chain_with_history.invoke({"input": "我叫什么名字？"}, config=config2)
    print(f"[新用户 user_002] 用户: 我叫什么名字？")
    print(f"助手: {round4.content}")


if __name__ == "__main__":
    main()
