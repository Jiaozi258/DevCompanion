import sys
import os
import subprocess
import requests
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QComboBox, QTextEdit, QPushButton, QProgressBar)
# 增加 QMovie 和 QTimer
from PyQt6.QtGui import QMovie
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from datetime import datetime
from dotenv import load_dotenv
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QComboBox, QTextEdit, QPushButton, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# 加载环境变量
load_dotenv()

# 工具函数：处理 PyInstaller 打包后的路径问题
def get_resource_path(relative_path):
    """ 获取资源绝对路径（兼容开发环境和 PyInstaller 环境） """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 1. 核心逻辑层
def call_cpp_engine(text_data):
    exe_path = get_resource_path("analyzer.exe")
    try:
        process = subprocess.run([exe_path], input=text_data.encode('utf-8'), capture_output=True, timeout=5)
        return process.stdout.decode('utf-8')
    except Exception as e:
        return f"C++ 引擎未找到或异常: {e}\n(请确保 analyzer.exe 在正确的路径下)"

def call_llm(user_input, task_type, mode):
    system_prompts = {
        "解释代码": "你是一个资深的 C++ 专家，请逐行详细通俗地解释代码。",
        "寻找Bug": "你是一个严厉的代码审查员，请找出漏洞。"
    }
    
    # 本地模式
    if mode == "本地隐私模式 (Ollama)":
        api_url = "http://localhost:11434/api/chat"
        headers = {}
        data = {
            "model": "qwen2.5:7b", # 确保你 Ollama 里装了这个模型，也可以换成 deepseek-coder
            "messages": [
                {"role": "system", "content": system_prompts.get(task_type)},
                {"role": "user", "content": user_input}
            ],
            "stream": False
        }
    # 云端模式
    else:
        api_url = "https://api.deepseek.com/v1/chat/completions" 
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key: return "请在 .env 文件中配置 DEEPSEEK_API_KEY！"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompts.get(task_type)}, {"role": "user", "content": user_input}]}
    
    try:
        # 本地模型推理较慢，把超时时间设长一点
        response = requests.post(api_url, headers=headers, json=data, timeout=120)
        response.raise_for_status() 
        
        if mode == "本地隐私模式 (Ollama)":
            return response.json().get('message', {}).get('content', '本地模型返回为空')
        else:
            return response.json().get('choices', [{}])[0].get('message', {}).get('content', 'API 返回为空')
    except requests.exceptions.ConnectionError:
        return "网络连接失败喵！如果是本地模式，请确认 Ollama 软件已在后台运行！"
    except Exception as e:
        return f"请求异常: {e}"

# 启动动画
class AnimatedSplashScreen(QWidget):
    def __init__(self, gif_path):
        super().__init__()
        #  1：去掉 Windows 默认的边框和标题栏，并让它保持在最前
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        #  2：背景透明化
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0) # 去掉所有边缘留白
        
        self.label = QLabel()
        self.movie = QMovie(gif_path)
        self.label.setMovie(self.movie)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        # 启动
        self.movie.start()

# 2. 多线程工作区 
class WorkerThread(QThread):
    result_ready = pyqtSignal(str)

    def __init__(self, code, task,engine):
        super().__init__()
        self.code = code
        self.task = task
        self.engine=engine

    def run(self):
        cpp_result = call_cpp_engine(self.code)
        llm_result = call_llm(self.code, self.task,self.engine)
        final_text = f"【C++ 分析】\n{cpp_result}\n\n{'='*40}\n\n【AI 解析】\n{llm_result}"
        self.result_ready.emit(final_text)

# 3. 界面表现层与事件控制
class DevCompanionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DevCompanion - V1.1")
        self.resize(850, 650)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()

        # --- 任务选择 ---
        self.task_combo = QComboBox()
        self.task_combo.addItems(["解释代码", "寻找Bug"])
        layout.addWidget(QLabel("选择任务："))
        layout.addWidget(self.task_combo)

        # --- 引擎算力选择 ---
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["云端模式 (ANY API)", "本地隐私模式 (Ollama)"])
        layout.addWidget(QLabel("算力引擎："))
        layout.addWidget(self.engine_combo)

        # --- 代码输入区 ---
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("在这里粘贴你的代码...")
        layout.addWidget(QLabel("输入区："))
        layout.addWidget(self.input_text)

        # --- 发射按钮 ---
        self.submit_btn = QPushButton("启动解析")
        self.submit_btn.setMinimumHeight(45)
        self.submit_btn.clicked.connect(self.on_submit_clicked)
        layout.addWidget(self.submit_btn)

        # --- 无限循环加载动画 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # 设置为 0-0 开启跑马灯动画效果
        self.progress_bar.hide()         # 初始状态隐藏
        layout.addWidget(self.progress_bar)

        # --- 结果输出区 ---
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(QLabel("智能分析报告："))
        layout.addWidget(self.output_text)

        main_widget.setLayout(layout)

    def on_submit_clicked(self):
        code = self.input_text.toPlainText()
        if not code.strip():
            self.output_text.setText("空代码无法解析喵")
            return

        task = self.task_combo.currentText()
        task = self.task_combo.currentText()
        engine = self.engine_combo.currentText() # 获取选中的引擎

        
        # 1. 改变界面状态：禁用按钮，显示动画
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("引擎高速运转中，请稍候喵...")
        self.progress_bar.show()
        self.output_text.setText("正在后台拉取数据喵...")

        # 2. 启动后台线程
        self.worker = WorkerThread(code, task, engine)
        self.worker.result_ready.connect(self.update_ui_with_result)
        self.worker.start()

    def update_ui_with_result(self, result_text):
        # 1. 恢复界面状态：隐藏动画，启用按钮
        self.progress_bar.hide()
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("启动解析喵")
        
        # 2. 显示结果
        self.output_text.setText(result_text)
        
        # 3. 【新增】：自动保存到本地 JSON
        self.save_to_history(self.task_combo.currentText(), self.input_text.toPlainText(), result_text)

    # --- 【新增】：本地数据持久化保存 ---
    def save_to_history(self, task, code, result):
        # 获取当前运行的真实目录（哪怕打包成exe也能存在exe旁边）
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
            
        history_file = os.path.join(base_dir, "history.json")
        
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "task": task,
            "code_snippet": code[:100] + "..." if len(code) > 100 else code, # 截取前100字预览
            "result": result
        }
        
        history = []
        # 如果文件存在，先读取旧记录
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding='utf-8') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                pass # 如果文件损坏，直接当空文件处理
        
        # 插入新记录到最前面
        history.insert(0, record)
        
        # 写回文件
        with open(history_file, "w", encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)

# 4. 启动

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 

    # 1. 找到启动动画文件
    gif_path = get_resource_path("startup.gif")
    
    # 2. 展开幕布并播放动画
    splash = AnimatedSplashScreen(gif_path)
    splash.show()
    
    # 强制系统立刻把动画画出来，别卡住
    QApplication.processEvents() 

    # 3. 在后台偷偷初始化你的主软件窗口 
    window = DevCompanionWindow()

    # 4. 设定时间差机制
    # 这里设定 3000 毫秒后，自动关闭启动屏，并显示主窗口
    QTimer.singleShot(3000, splash.close)
    QTimer.singleShot(3000, window.show)

    sys.exit(app.exec())