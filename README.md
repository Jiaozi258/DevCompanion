DevCompanion: 一款用于对代码进行分析和找bug的开源项目，是一个采用Python+C++分析 + 本地RAG知识库 + 大模型双引擎混合架构的极简代码审查工具。

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![ChromaDB](https://img.shields.io/badge/VectorDB-Chroma-orange.svg)](https://trychroma.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

##核心特性 

**RAG 本地知识库增强**
**双引擎自由切换**
**兼容 DeepSeek 及任何支持 OpenAI 协议的 API**
**本地ollama模式**
**C++ 底层分析**
** UI**：基于 PyQt6 构建的无边框侧边栏架构
**记忆持久化**

（新手的第一次开发试验，本项目AI发挥了至关重要的辅助作用）
（启动动画用的小黑盒上保存的杀戮尖塔2角色故障机器人gif，不知道作者，侵删）

\### 环境准备

确保您的电脑已安装 Python 3.8+ 和 GCC 编译器（g++）。
如需要本地运行请安装ollama。

本项目已提供配置完善的 .spec 文件

如果你想将其打包为独立的 .exe 发给朋友：

```bash
\#输入下面一行指令
pyinstaller DevCompanion.spec
编译完成后，请将 dist/DevCompanion.exe、.env 文件以及空文件夹 knowledge_db/ 打包放在同一个目录下运行。

\# 克隆仓库

git clone \[https://github.com/JiaoZi258/DevCompanion.git](https://github.com/JiaoZi258/DevCompanion.git)

cd DevCompanion

\#建议使用虚拟环境（由于包含 ChromaDB 等核心组件，首次安装可能需要几分钟）
pip install -r requirements.txt


\# 安装 Python 依赖

pip install streamlit requests python-dotenv

\#启动
python main_gui.py

