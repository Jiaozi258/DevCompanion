DevCompanion: 一款用于对代码进行分析和debug的开源项目


DevCompanion 是一个采用Python + C+++ LLM混合架构的极简代码审查工具。

（同样也是新手的第一次开发试验，本项目AI发挥了至关重要的辅助作用）
（启动动画用的小黑盒上保存的杀戮尖塔2角色故障机器人gif，不知道作者，侵删）


特色 

\- 双模算力引擎：支持接入API 获得推理，或一键切换至本地 Ollama 实现本地断网运行。

\- C++ 底层预处理：利用跨进程调用将文本扫描任务下发至 C++ 引擎执行。

\- UI：基于 Streamlit 构建的现代化交互界面。



\## 极速安装与运行指南



\### 环境准备

确保您的电脑已安装 Python 3.8+ 和 GCC 编译器（g++）。
如需要本地运行请安装ollama。


```bash

\# 克隆仓库

git clone \[https://github.com/您的用户名/DevCompanion.git](https://github.com/您的用户名/DevCompanion.git)

cd DevCompanion



\# 安装 Python 依赖

pip install streamlit requests python-dotenv

