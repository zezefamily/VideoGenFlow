"""示例 3：使用 PromptTemplate + LCEL Chain 链式调用"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from common import get_llm


def main():
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个{role}，请用通俗易懂的语言回答。"),
        ("human", "{question}"),
    ])

    # LCEL 语法：prompt | llm | parser
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({
        "role": "技术老师",
        "question": "什么是大语言模型（LLM）？",
    })
    print(result)


if __name__ == "__main__":
    main()
