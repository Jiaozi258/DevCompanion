import chromadb
import requests
import os
from dotenv import load_dotenv

# 加载环境变量里的 API KEY
load_dotenv()

def run_mini_rag():
    print("【1. 初始化本地知识库...】")
    # 建立一个运行在内存里的微型 Chroma 数据库（关掉程序就清空）
    client = chromadb.Client() 
    
    # 建一个名为 "dev_knowledge" 的书架
    # 如果报错说集合已存在，先删掉它，防止重复运行报错
    try:
        client.delete_collection("dev_knowledge")
    except:
        pass
    collection = client.create_collection("dev_knowledge")

    print("【2. 正在将机密文档写入数据库 (自动向量化)...】")
    # 这里我们模拟一份llm不知道的文档
    secret_doc = (
        "DevCompanion隐藏条件：连续点击发射按钮 5 次，"
        "软件界面会自动切换为绿色主题。并且，该软件的首席架构师"
        "目前正在马来西亚攻读理工科学位。"
    )
    
    # 存入数据库
    # 第一次运行这一步时，Chroma 会在后台下载一个约 80MB 的模型来做向量化
    # 屏幕上可能会卡顿一会儿或出现下载进度条，属于正常现象，以后运行就是秒开了
    collection.add(
        documents=[secret_doc],
        ids=["doc_1"]
    )

    print("【3. 开始检索与回答】\n" + "-"*40)
    user_question = "请问 DevCompanion 的架构师在哪上学？怎么触发绿色主题？"
    print(f"用户提问: {user_question}")

    # 核心 RAG 步骤 1：去数据库里翻书
    results = collection.query(
        query_texts=[user_question],
        n_results=1 # 只拿最相关的 1 段话
    )
    
    retrieved_text = results['documents'][0][0]
    print(f"数据库检索到的参考资料: {retrieved_text}\n" + "-"*40)

    # 核心 RAG 步骤 2：拿着书本资料去问llm
    print("正在把资料交给大模型思考...\n")
    
    # 构建包含参考资料的 Prompt
    system_prompt = f"""
    你是一个智能问答助手。请严格根据以下参考资料回答用户的问题。
    如果参考资料中没有相关信息，请直接回答“资料库中未记载”。
    
    【参考资料】：{retrieved_text}
    """

    api_url = "https://api.deepseek.com/v1/chat/completions" 
    api_key = os.getenv("DEEPSEEK_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=30)
        answer = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f" AI 回答：\n{answer}")
    except Exception as e:
        print(f"请求报错: {e}")

if __name__ == "__main__":
    run_mini_rag()