import streamlit as st
import requests
import json
import subprocess
import os
from dotenv import load_dotenv

# 加载本地的 .env 隐藏文件
load_dotenv()


def call_cpp_engine(text_data):
    """跨系统调用 C++进行扫描"""
    try:
        #调用analyzer.exe
        process = subprocess.run(
            ["analyzer.exe"],
            input=text_data.encode('utf-8'),
            capture_output=True,
            timeout=5
        )
        return process.stdout.decode('utf-8')
    except FileNotFoundError:
        return "错误：未找到 C++ 引擎，请确认 analyzer.exe 已生成在同一目录！"
    except Exception as e:
        return f"C++ 引擎异常: {e}"


def call_llm(user_input, task_type, mode):
    """双模算力引擎调度器"""
    system_prompts = {
        "解释代码": "你是一个资深的 C++ 专家，请逐行解释下面这段代码。",
        "寻找Bug": "你是一个极其严厉的代码审查员，请找出漏洞并提供修复后的代码。"
    }

    if mode == "本地隐私模式 (Ollama)":
        api_url = "http://localhost:11434/api/chat"
        headers = {}
        data = {
            "model": "qwen2.5:7b",  # 确保你本地用 ollama run 过这个模型
            "messages": [
                {"role": "system", "content": system_prompts.get(task_type)},
                {"role": "user", "content": user_input}
            ],
            "stream": False
        }
    else:
        api_url = "https://api.deepseek.com/v1/chat/completions"
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key or api_key == "换成你申请的真实API_KEY":
            return "错误：请在 .env 文件中填入API Key！ps：如果你不知道什么是api请自行查询"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompts.get(task_type)},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0.3
        }

    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=45)
        response.raise_for_status()
        result = response.json()

        if mode == "本地隐私模式 (Ollama)":
            return result.get('message', {}).get('content', '模型返回为空')
        else:
            return result.get('choices', [{}])[0].get('message', {}).get('content', 'API 返回为空')

    except requests.exceptions.ConnectionError:
        return "网络连接失败！如果是本地模式，请确认 Ollama 软件是否已在后台运行！"
    except Exception as e:
        return f"请求异常: {e}"


def main():
    st.set_page_config(page_title="DevCompanion Pro", layout="wide")

    # 极客风格侧边栏
    with st.sidebar:
        st.header("引擎控制台")
        engine_mode = st.radio(
            "选择大模型算力来源：",
            ["本地隐私模式 (Ollama)", "云端极速模式 (需要API)"],
            help="本地模式完全断网且免费；云端模式需要 API Key。"
        )

    st.title("DevCompanion: 混合架构开发伴侣")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("代码输入区")
        task_type = st.selectbox("请选择扫描任务", ["解释代码", "寻找Bug"])
        user_input = st.text_area("请将 C++ 或 Python 代码粘贴在此处...", height=350)
        submit_button = st.button("启动多核联合解析")

    with col2:
        st.subheader("分析报告")
        if submit_button and user_input.strip():
            with st.spinner(f'双引擎处理中 ({engine_mode})...'):
                # 1. 毫秒级 C++ 扫描
                cpp_result = call_cpp_engine(user_input)
                st.info(f"**【C++预处理】**\n\n{cpp_result}")

                # 2. 大模型深度推理
                llm_answer = call_llm(user_input, task_type, engine_mode)
                st.success(f"**【AI分析结果】**")
                st.markdown(llm_answer)


if __name__ == "__main__":
    main()