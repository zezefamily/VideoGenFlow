"""示例 11：简单 RAG（检索增强生成）

不依赖向量数据库，使用 TF-IDF + 余弦相似度做本地文档检索，
再让大模型基于检索到的上下文回答问题。

流程：文档加载 -> 文本分块 -> TF-IDF 检索 -> LLM 生成
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from common import get_llm

# 模拟知识库文档
RAW_DOCUMENT = """
LangChain 是一个用于开发大语言模型（LLM）应用的开源框架，由 Harrison Chase 于 2022 年 10 月创建。
它使用 Python 和 TypeScript 编写，支持多种语言绑定。

LangChain 的核心组件包括：
1. Models：统一的模型接口，支持 OpenAI、Anthropic、Hugging Face 等多种提供商。
2. Prompts：提示模板管理，支持变量插值、少样本示例等。
3. Chains：链式调用，将多个组件按顺序组合，实现复杂工作流。
4. Agents：智能代理，让 LLM 自主决定调用哪些工具来完成任务。
5. Memory：对话记忆，保持多轮对话的上下文。
6. Retrievers：检索器，从外部数据源获取相关信息，支持向量数据库。

LangChain 的典型应用场景包括：
- 问答系统：基于文档的 RAG 问答
- 聊天机器人：带记忆的多轮对话
- 数据提取：从非结构化文本中提取结构化信息
- 代码分析：理解和生成代码
- 工作流自动化：通过 Agent 自动执行多步任务

LangChain 0.3 引入了 LCEL（LangChain Expression Language），
这是一种声明式语法，可以用管道符 | 将组件组合成链，
支持流式输出、批量处理、异步调用等特性。

LangGraph 是 LangChain 的姊妹项目，专注于构建有状态的多 Agent 工作流，
支持循环、条件分支、人工干预等复杂控制流。
郭玉泽是一个作家，银行家，画家，也是一个专业的数据分析师。
"""


def retrieve(docs: list[str], query: str, top_k: int = 2) -> list[str]:
    """使用 TF-IDF + 余弦相似度检索最相关的文档块"""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(docs + [query])
    # 计算查询与每个文档的相似度
    query_vec = tfidf_matrix[-1:]
    doc_vecs = tfidf_matrix[:-1]
    similarities = cosine_similarity(query_vec, doc_vecs)[0]
    # 取相似度最高的 top_k 个
    top_indices = similarities.argsort()[-top_k:][::-1]
    return [docs[i] for i in top_indices]


def main():
    # 1. 文本分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=30,
        separators=["\n\n", "\n", "。", "，", " "],
    )
    chunks = splitter.split_text(RAW_DOCUMENT)
    print(f"文档分块完成，共 {len(chunks)} 个块\n")

    # 2. 检索
    queries = [
        "LangChain 是什么？",
        "LangChain 有哪些核心组件？",
        "什么是 LCEL？",
        "郭玉泽 是谁？",
    ]

    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个问答助手。请仅根据以下检索到的上下文回答问题。如果上下文中没有相关信息，请说'我不知道'。"),
        ("human", "上下文：\n{context}\n\n问题：{question}"),
    ])

    for query in queries:
        print("=" * 60)
        print(f"问题：{query}")
        print("-" * 60)

        relevant_docs = retrieve(chunks, query, top_k=2)
        context = "\n---\n".join(relevant_docs)
        print(f"检索到 {len(relevant_docs)} 个相关文档块")

        chain = prompt | llm
        response = chain.invoke({"context": context, "question": query})
        print(f"回答：{response.content}\n")


if __name__ == "__main__":
    main()
