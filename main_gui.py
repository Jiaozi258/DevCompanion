import sys
import requests
import os
import subprocess
import requests
import json
import chromadb
from datetime import datetime
from dotenv import load_dotenv

from PyQt6.QtWidgets import QStackedWidget, QListWidget
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QTextEdit, QPushButton, QProgressBar, QFileDialog, QMessageBox)
from PyQt6.QtGui import QIcon,QMovie
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

load_dotenv()

def fetch_ollama_models():
    """ 动态获取当前电脑 Ollama 已安装的模型列表 """
    try:
        # 向本地 Ollama 发送查询请求
        response = requests.get("http://localhost:11434/api/tags", timeout=0.5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [m['name'] for m in models]
    except Exception:
        # 如果用户没开 Ollama，或者没安装，就静默失败
        pass
    return []

# ==========================================
# 工具函数：处理打包后的路径问题
# ==========================================
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ==========================================
# 1. 核心逻辑层 
# ==========================================
class RAGManager:
    def __init__(self):
        # 知识库必须保存在外面，不能打包进 exe
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
        
        db_path = os.path.join(base_dir, "knowledge_db")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("my_docs")

    def add_document(self, text, doc_id):
        # --- 设定切分参数 ---
        chunk_size = 500    # 每个小块的最大字数
        chunk_overlap = 50  # 相邻小块之间重叠的字数（防止语义在切开处断掉）
        
        chunks = []
        # 循环切分逻辑
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            # 步进距离 = 块大小 - 重叠大小
            start += (chunk_size - chunk_overlap)
        
        # 生成对应的 ID 列表（例如：doc.txt_0, doc.txt_1...）
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        
        # 批量存入数据库
        self.collection.add(documents=chunks, ids=ids)

    def query_context(self, query_text):
        results = self.collection.query(query_texts=[query_text], n_results=1)
        if results['documents'] and results['documents'][0]:
            return results['documents'][0][0]
        return ""

# ==========================================
# 2. 多线程工作区
# ==========================================
class WorkerThread(QThread):
    result_ready = pyqtSignal(str)

    def __init__(self, code, task, engine, rag_manager, api_key,api_url):
        super().__init__()
        self.code = code
        self.task = task
        self.engine = engine
        self.rag_mgr = rag_manager
        self.api_key = api_key 
        self.api_url = api_url

    def run(self):
        # 1. C++ 底层扫描
        cpp_result = self.call_cpp_engine(self.code)

        # 2. 去本地查资料
        context = self.rag_mgr.query_context(self.code)
        
        # 3. 增强提示词
        enhanced_prompt = self.code
        if context:
            enhanced_prompt = f"【参考本地资料】：{context}\n\n【待处理代码/问题】：\n{self.code}"

        # 4. 呼叫大模型 
        llm_result = self.call_llm(enhanced_prompt, self.task, self.engine, self.api_key,self.api_url)

        final_text = f"【C++ 分析】\n{cpp_result}\n\n{'='*40}\n\n【AI 解析】\n{llm_result}"
        if context:
            final_text += f"\n\n(喵喵)"
        
        self.result_ready.emit(final_text)

    def call_cpp_engine(self, text_data):
        import subprocess
        exe_path = get_resource_path("analyzer.exe")
        try:
            process = subprocess.run([exe_path], input=text_data.encode('utf-8'), capture_output=True, timeout=5)
            return process.stdout.decode('utf-8')
        except Exception as e:
            return f"C++ 引擎调用异常: {e}"

    def call_llm(self, user_input, task_type, mode, api_key,api_url):
        import requests
        system_prompts = {
            "解释代码": "你是一个资深的 C++ 专家，请结合参考资料逐行地通俗易懂地严谨认真地解释代码。",
            "寻找Bug": "你是一个严厉的代码审查员，请结合参考资料找出逻辑漏洞和语法漏洞并对其进行改正。",
            "代码思路分析": "你是一个架构师。请不要直接提供修改后的代码，而是帮我梳理这段代码的设计模式、时间复杂度，并用步骤拆解它的核心逻辑。",
            "举一反三": "你是一个资深导师。请指出这段 C++ 代码中不够优雅的地方，提供至少两种不同的重构思路（比如一种追求极致性能，一种追求可读性），并引导我思考。"
        }
        
        request_url = ""
        headers={}
        data={}

        #选了这个走云端
        if mode == "云端模式 ":
            request_url = api_url
            if not api_key: 
                return " 缺少 API Key！请去左侧【基础设置】页面填写您的密钥喵！"
                
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompts.get(task_type)}, {"role": "user", "content": user_input}]}
        else:
            # 只要不是云端，全部给本地 Ollama
            request_url = "http://localhost:11434/api/chat"
            headers = {}
            
            #确保系统提示词绝对不是 None
            sys_prompt = system_prompts.get(task_type, "你是一个严谨的代码分析助手。")
            
            data = {
                "model": mode, 
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input}],
                "stream": False
            }
        
        # 开始尝试发送请求
        try:
            if not request_url:
                return "内部错误：未获取到请求地址！"

            response = requests.post(request_url, headers=headers, json=data, timeout=120)
            
            # 拦截错误
            if response.status_code != 200:
                error_detail = response.text  # 抓取 API 吐出的具体错误原话
                
                if response.status_code == 400:
                    return f"🚨 请求格式错误 (400)。\n {error_detail}\n(排查建议：检查下拉框模型名是否正确，或重启 Ollama)"
                elif response.status_code == 402:
                    return "🚨 云端请求失败：账户余额不足 (402)。请更换 API 或切至本地模型。"
                else:
                    return f"🚨 请求失败 (状态码 {response.status_code}): {error_detail}"
                
            # 如果是 200 正常响应，才往下解析
            if mode == "云端极速模式 (DeepSeek API)":
                return response.json().get('choices', [{}])[0].get('message', {}).get('content', 'API 返回为空')
            else:
                return response.json().get('message', {}).get('content', '本地模型返回为空')
                
        except Exception as e:
            return f"🚨 请求引发异常: {e}"

# ==========================================
# 3. 启动屏类
# ==========================================
class AnimatedSplashScreen(QWidget):
    def __init__(self, gif_path):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel()
        self.movie = QMovie(gif_path)
        self.label.setMovie(self.movie)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.movie.start()

# ==========================================
# 4. 主界面
# ==========================================
class DevCompanionWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DevCompanion V1.4 - Pro")
        self.resize(1100, 750)
        self.rag_mgr = RAGManager()   

    # 核心：总容器是一个水平布局
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
    
    # --- 左侧：侧边栏 (Sidebar) ---
        self.sidebar = QListWidget() # 简单实现：用列表当导航栏
        self.sidebar.setFixedWidth(120)
        self.sidebar.addItems(["AI 分析", "历史记录", "基础设置"])
        self.sidebar.currentRowChanged.connect(self.display_page) # 点击切换信号
    
    # --- 右侧：分页容器 (StackedWidget) ---
        self.pages = QStackedWidget()
    
    # 初始化三个页面（我们稍后创建它们）
        self.page_main = QWidget()     # 分析界面
        self.page_history = QWidget()  # 历史记录界面
        self.page_settings = QWidget() # 设置界面
    
        self.pages.addWidget(self.page_main)
        self.pages.addWidget(self.page_history)
        self.pages.addWidget(self.page_settings)
    
    # 组合
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)
    
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
    
    # 调用初始化页面的函数
        self.setup_main_page()
        self.setup_history_page()
        self.setup_settings_page()

    # 页面切换函数
    def display_page(self, index):
        self.pages.setCurrentIndex(index)	

    def setup_main_page(self):
        layout = QVBoxLayout()
        
        # 任务选择
        self.task_combo = QComboBox()
        self.task_combo.addItems(["解释代码", "寻找Bug","代码思路分析","举一反三"])
        layout.addWidget(QLabel("选择任务："))
        layout.addWidget(self.task_combo)

        # 代码输入
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("在这里粘贴代码，或者直接向 AI 提问喵")
        layout.addWidget(QLabel("输入区："))
        layout.addWidget(self.input_text)

        # 解析按钮
        self.submit_btn = QPushButton("启动解析")
        self.submit_btn.setMinimumHeight(45)
        self.submit_btn.clicked.connect(self.on_submit_clicked)
        layout.addWidget(self.submit_btn)

        # 加载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # 结果输出
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(QLabel("分析报告："))
        layout.addWidget(self.output_text)

        self.page_main.setLayout(layout)	

    def setup_history_page(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("### 历史记录回顾"))
        
        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        layout.addWidget(self.history_display)
        
        refresh_btn = QPushButton("刷新历史记录")
        refresh_btn.clicked.connect(self.load_history_to_ui)
        layout.addWidget(refresh_btn)
        
        # 顺便把之前那个导入文档的按钮也挪到这里，作为“知识管理”的一部分
        self.add_doc_btn = QPushButton(" 导入参考文档 (.txt/.md)")
        self.add_doc_btn.clicked.connect(self.on_add_doc_clicked)
        layout.addWidget(self.add_doc_btn)
        
        self.page_history.setLayout(layout)

    def load_history_to_ui(self):
        """读取本地 history.json 并展示到历史界面的文本框中"""
        # 判断刚才初始化页面时，有没有成功创建用来显示的文本框
        if not hasattr(self, 'history_display'):
            return
            
        import os, json
        
        # 兼容打包后的路径读取
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
            
        history_file = os.path.join(base_dir, "history.json")

        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 把读取到的数据拼装成漂亮的格式
                text = ""
                for item in data:
                    text += f"📅 时间: {item.get('time', '未知')}\n"
                    text += f"🎯 任务: {item.get('task', '未知')}\n"
                    text += f"💻 原始代码: \n{item.get('code_snippet', '')}\n"
                    text += f"✨ 分析结果: \n{item.get('result', '')}\n"
                    text += "-" * 50 + "\n\n"
                    
                self.history_display.setText(text)
            except json.JSONDecodeError:
                self.history_display.setText("🚨 历史记录文件损坏或为空。")
        else:
            self.history_display.setText("📭 暂无历史记录。赶紧去分析一段代码喵！")

    def setup_settings_page(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("### ⚙️ 基础设置"))

        # 在设置页面添加
        self.api_url_input = QTextEdit()
        self.api_url_input.setPlaceholderText("例如: https://api.deepseek.com/v1")
        self.api_url_input.setFixedHeight(40)
        layout.addWidget(QLabel("自定义 API Base URL:"))
        layout.addWidget(self.api_url_input)

        # 推理引擎选择
        self.engine_combo = QComboBox()
        ollama_models = fetch_ollama_models()
        self.engine_combo.addItems(["云端模式"])
        # 扫描当前用户的电脑
        local_models = fetch_ollama_models()
        
        if local_models:
            # 如果扫描到了，把电脑里的模型全塞进下拉框
            self.engine_combo.addItems(local_models)
        else:
            # 如果没扫描到，给个不可选提示
            self.engine_combo.addItem("未检测到本地模型 (请先开启 Ollama)")
        layout.addWidget(QLabel("选择算力引擎："))
        layout.addWidget(self.engine_combo)

        # API KEY 设置
        self.api_key_display = QTextEdit()
        self.api_key_display.setPlaceholderText("检测到 .env 文件中的 KEY...")
        self.api_key_display.setFixedHeight(50)
        layout.addWidget(QLabel("LLM API Key (当前状态)："))
        layout.addWidget(self.api_key_display)
        
        # 装饰性的状态栏
        self.know_status = QLabel("系统状态：神经元连接正常")
        self.know_status.setStyleSheet("color: #00ff00;")
        layout.addWidget(self.know_status)

        layout.addStretch() # 弹簧，把内容顶上去
        self.page_settings.setLayout(layout)

    def on_add_doc_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择参考文档", "", "Text Files (*.txt);;Markdown Files (*.md)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                doc_id = os.path.basename(file_path)
                self.rag_mgr.add_document(content, doc_id)
                QMessageBox.information(self, "成功", f"数据《{doc_id}》已注入本地神经元")
                self.know_status.setText(f"知识库：已注入 {doc_id}")

    def on_submit_clicked(self):
        code = self.input_text.toPlainText()
        task = self.task_combo.currentText()
        # 去设置页面抓取数据
        engine = self.engine_combo.currentText()
        # 获取用户填写的自定义 URL，没填就默认用 DeepSeek
        base_url = self.api_url_input.toPlainText().strip() or "https://api.deepseek.com/v1/chat/completions"
        # 补全 OpenAI 协议的后缀路径
        if not base_url.endswith("/chat/completions"):
            base_url = base_url.rstrip("/") + "/chat/completions"
        # 优先读取界面上填的，如果没填，再去读 .env 文件里的 LLM_API_KEY
        api_key = self.api_key_display.toPlainText().strip() or os.getenv("LLM_API_KEY", "")

        if not code.strip():
            self.output_text.setText("老板，空代码无法解析喵。")
            return
        
        self.submit_btn.setEnabled(False)
        self.progress_bar.show()
        self.output_text.setText("正在后台拉取数据喵...")
        
        # 把 api_key 当作参数，塞给后台
        self.worker = WorkerThread(code, task, engine, self.rag_mgr, api_key,base_url)
        self.worker.result_ready.connect(self.update_ui)
        self.worker.start()

    def update_ui(self, text):
        self.output_text.setText(text)
        self.progress_bar.hide()
        self.submit_btn.setEnabled(True)
        self.save_to_history(self.task_combo.currentText(), self.input_text.toPlainText(), text)

# --- 本地数据持久化保存 ---
    def save_to_history(self, task, code, result):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
            
        history_file = os.path.join(base_dir, "history.json")
        
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "task": task,
            "code_snippet": code[:100] + "..." if len(code) > 100 else code,
            "result": result
        }
        
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding='utf-8') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                pass
        
        history.insert(0, record)
        
        with open(history_file, "w", encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)

# ==========================================
# 5. 启动
# ==========================================
if __name__ == "__main__":
    # 告诉 Windows 这是一个独立的软件，不要用 Python 的默认图标
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("my_unique_dev_companion_v1")
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # 给整个应用程序设置图标
    icon_path = get_resource_path("app.ico")
    app.setWindowIcon(QIcon(icon_path))


    app.setStyleSheet("""
        QListWidget {
            background-color: #2b2b2b;
            color: white;
            border: none;
            outline: none;
            font-size: 14px;
        }
        QListWidget::item {
            padding: 15px;
        }
        QListWidget::item:selected {
            background-color: #3d3d3d;
            border-left: 4px solid #0078d4;
        }
        QMainWindow {
            background-color: #1e1e1e;
        }
        QLabel {
            color: #cccccc;
        }
    """)

    gif_path = get_resource_path("startup.gif")
    
    splash = AnimatedSplashScreen(gif_path)
    splash.show()
    QApplication.processEvents() 

    window = DevCompanionWindow()

    QTimer.singleShot(3000, splash.close)
    QTimer.singleShot(3000, window.show)

    sys.exit(app.exec())