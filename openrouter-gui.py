import sys
import os
import json
import base64
import mimetypes
from typing import List, Optional, Dict, Any
from pathlib import Path

import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QScrollArea, QLabel, 
    QFrame, QSplitter, QComboBox, QDialog, QFormLayout, 
    QDialogButtonBox, QMessageBox, QFileDialog, QProgressBar,
    QListWidget, QListWidgetItem, QMenu, QToolButton
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QMimeData, QUrl, pyqtSlot,
    QPropertyAnimation, QEasingCurve, QRect, QTimer
)
from PyQt6.QtGui import (
    QFont, QPixmap, QDragEnterEvent, QDropEvent, QAction,
    QIcon, QPalette, QColor, QLinearGradient, QPainter
)

# 設定ファイルのパス
CONFIG_FILE = "openrouter_config.json"

class ConfigDialog(QDialog):
    """API設定ダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenRouter API 設定")
        self.setModal(True)
        self.resize(400, 200)
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        layout = QFormLayout()
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("OpenRouter APIキーを入力")
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setText("https://openrouter.ai/api/v1")
        self.base_url_edit.setPlaceholderText("ベースURL")
        
        layout.addRow("APIキー:", self.api_key_edit)
        layout.addRow("ベースURL:", self.base_url_edit)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)
        
    def load_config(self):
        """設定を読み込み"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.api_key_edit.setText(config.get('api_key', ''))
                self.base_url_edit.setText(config.get('base_url', 'https://openrouter.ai/api/v1'))
        except FileNotFoundError:
            pass
            
    def save_config(self):
        """設定を保存"""
        config = {
            'api_key': self.api_key_edit.text(),
            'base_url': self.base_url_edit.text()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

class AttachedFile:
    """添付ファイルクラス"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_size = os.path.getsize(file_path)
        self.mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
    def is_image(self) -> bool:
        return self.mime_type.startswith('image/')
        
    def is_document(self) -> bool:
        return self.mime_type in ['application/pdf', 'application/msword', 
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        
    def is_audio(self) -> bool:
        return self.mime_type.startswith('audio/')
        
    def get_base64_content(self) -> str:
        """Base64エンコードされたファイル内容を取得"""
        try:
            with open(self.file_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
                print(f"Base64エンコード完了: {self.file_name}, 長さ: {len(content)}")
                return content
        except Exception as e:
            print(f"ファイル読み込みエラー ({self.file_name}): {e}")
            return ""

class FileListWidget(QListWidget):
    """ファイルリストウィジェット"""
    files_changed = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setMaximumHeight(120)
        self.attached_files: List[AttachedFile] = []
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                self.add_file(file_path)
        event.acceptProposedAction()
        
    def add_file(self, file_path: str):
        """ファイルを追加"""
        if not os.path.isfile(file_path):
            return
            
        attached_file = AttachedFile(file_path)
        self.attached_files.append(attached_file)
        
        # リストアイテムを作成
        item = QListWidgetItem()
        file_info = f"📎 {attached_file.file_name} ({self.format_file_size(attached_file.file_size)})"
        item.setText(file_info)
        item.setData(Qt.ItemDataRole.UserRole, len(self.attached_files) - 1)
        self.addItem(item)
        
        # コンテキストメニュー
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
        
        self.files_changed.emit(self.attached_files)
        
    def format_file_size(self, size: int) -> str:
        """ファイルサイズをフォーマット"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
        
    def contextMenuEvent(self, event):
        """コンテキストメニュー"""
        item = self.itemAt(event.pos())
        if item is None:
            return
            
        menu = QMenu(self)
        delete_action = menu.addAction("削除")
        action = menu.exec(event.globalPos())
        
        if action == delete_action:
            index = item.data(Qt.ItemDataRole.UserRole)
            self.remove_file(index)
            
    def remove_file(self, index: int):
        """ファイルを削除"""
        if 0 <= index < len(self.attached_files):
            del self.attached_files[index]
            self.clear()
            
            # リストを再構築
            for i, attached_file in enumerate(self.attached_files):
                item = QListWidgetItem()
                file_info = f"📎 {attached_file.file_name} ({self.format_file_size(attached_file.file_size)})"
                item.setText(file_info)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.addItem(item)
                
            self.files_changed.emit(self.attached_files)
            
    def clear_files(self):
        """すべてのファイルをクリア"""
        self.attached_files.clear()
        self.clear()
        self.files_changed.emit(self.attached_files)

class ChatBubble(QFrame):
    """チャット吹き出し"""
    def __init__(self, message: str, is_user: bool = False, images: List[str] = None):
        super().__init__()
        self.is_user = is_user
        self.setup_ui(message, images or [])
        
    def setup_ui(self, message: str, images: List[str]):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 画像表示
        for image_path in images:
            if os.path.exists(image_path):
                image_label = QLabel()
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    # 画像をリサイズ
                    pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, 
                                         Qt.TransformationMode.SmoothTransformation)
                    image_label.setPixmap(pixmap)
                    image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.addWidget(image_label)
        
        # テキスト表示
        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        font = QFont()
        font.setPointSize(11)
        text_label.setFont(font)
        
        layout.addWidget(text_label)
        self.setLayout(layout)
        
        # スタイル設定
        if self.is_user:
            self.setStyleSheet("""
                QFrame {
                    background-color: #007AFF;
                    border-radius: 15px;
                    margin-left: 50px;
                    margin-right: 10px;
                    margin-top: 5px;
                    margin-bottom: 5px;
                }
                QLabel {
                    color: white;
                    background-color: transparent;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #F0F0F0;
                    border-radius: 15px;
                    margin-left: 10px;
                    margin-right: 50px;
                    margin-top: 5px;
                    margin-bottom: 5px;
                }
                QLabel {
                    color: #333333;
                    background-color: transparent;
                }
            """)

class OpenRouterAPIThread(QThread):
    """OpenRouter API呼び出しスレッド"""
    message_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_key: str, base_url: str, model: str, messages: List[Dict], attached_files: List[AttachedFile]):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self.attached_files = attached_files
        
    def run(self):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # メッセージを準備
            api_messages = []
            
            # 最後のユーザーメッセージに添付ファイルを含める
            for i, msg in enumerate(self.messages):
                if msg['role'] == 'user' and i == len(self.messages) - 1:
                    # 最新のユーザーメッセージの場合
                    content = []
                    
                    # テキスト追加
                    if msg.get('content'):
                        content.append({
                            "type": "text",
                            "text": msg['content']
                        })
                    
                    # 画像添付がある場合
                    for attached_file in self.attached_files:
                        if attached_file.is_image():
                            print(f"画像を処理中: {attached_file.file_name}")
                            base64_content = attached_file.get_base64_content()
                            if base64_content:
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{attached_file.mime_type};base64,{base64_content}"
                                    }
                                })
                                print(f"画像を追加しました: {attached_file.file_name}")
                    
                    api_messages.append({
                        "role": msg['role'],
                        "content": content if len(content) > 1 else msg['content']
                    })
                else:
                    # 過去のメッセージはそのまま
                    api_messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            data = {
                "model": self.model,
                "messages": api_messages,
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    message = result['choices'][0]['message']['content']
                    self.message_received.emit(message)
                else:
                    self.error_occurred.emit("レスポンスが無効です")
            else:
                self.error_occurred.emit(f"API エラー: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.error_occurred.emit(f"エラーが発生しました: {str(e)}")

class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenRouter Chat Assistant")
        self.setGeometry(100, 100, 1200, 800)
        
        # 変数初期化
        self.messages = []
        self.api_thread = None
        self.config = self.load_config()
        
        self.setup_ui()
        self.setup_styles()
        
    def load_config(self) -> Dict:
        """設定を読み込み"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'api_key': '', 'base_url': 'https://openrouter.ai/api/v1'}
            
    def setup_model_list(self):
        """モデルリストを設定"""
        models = {
            "🔥 おすすめ (Vision対応)": [
                ("openai/gpt-4o", "GPT-4o - 最新、画像・文書解析"),
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet - 高性能、推論力"),
                ("google/gemini-pro-1.5", "Gemini Pro 1.5 - 大容量コンテキスト")
            ],
            "💰 コスパ重視": [
                ("openai/gpt-4o-mini", "GPT-4o Mini - 高品質、低価格"),
                ("anthropic/claude-3-haiku", "Claude 3 Haiku - 高速、軽量"),
                ("google/gemini-flash-1.5", "Gemini Flash 1.5 - 高速処理")
            ],
            "🆓 無料モデル": [
                ("qwen/qwen-2-vl-72b-instruct", "Qwen2-VL 72B - 無料画像解析"),
                ("microsoft/phi-3.5-vision-instruct", "Phi-3.5 Vision - 小型高性能"),
                ("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B - 軽量無料")
            ],
            "🎨 画像特化": [
                ("openai/gpt-4-vision-preview", "GPT-4 Vision - 画像理解"),
                ("mistralai/pixtral-12b", "Pixtral 12B - 画像生成"),
                ("meta-llama/llama-3.2-90b-vision-instruct", "Llama 3.2 Vision - 大型視覚")
            ],
            "💻 コーディング": [
                ("deepseek/deepseek-v3", "DeepSeek V3 - コーディング特化"),
                ("mistralai/mistral-large", "Mistral Large - 高性能"),
                ("cohere/command-r-plus", "Command R+ - 推論力")
            ],
            "☁️ Amazon": [
                ("amazon/nova-pro-v1", "Nova Pro - バランス型"),
                ("amazon/nova-lite-v1", "Nova Lite - 軽量版")
            ]
        }
        
        for category, model_list in models.items():
            self.model_combo.addItem(f"────── {category} ──────")
            # セパレータアイテムは選択不可に
            separator_index = self.model_combo.count() - 1
            self.model_combo.model().item(separator_index).setEnabled(False)
            
            for model_id, description in model_list:
                self.model_combo.addItem(f"  {description}", model_id)
        
        # デフォルト選択
        self.model_combo.setCurrentText("  GPT-4o - 最新、画像・文書解析")
        
    def get_selected_model(self) -> str:
        """選択されたモデルIDを取得"""
        current_data = self.model_combo.currentData()
        if current_data:
            return current_data
        # フォールバック
        return "openai/gpt-4o"
    def setup_ui(self):
        """UI設定"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # ツールバー
        toolbar_layout = QHBoxLayout()
        
        # モデル選択（カテゴリ付き）
        self.model_combo = QComboBox()
        self.setup_model_list()
        self.model_combo.setMinimumWidth(250)
        
        # 設定ボタン
        settings_btn = QPushButton("⚙️ 設定")
        settings_btn.clicked.connect(self.open_settings)
        
        # クリアボタン
        clear_btn = QPushButton("🗑️ クリア")
        clear_btn.clicked.connect(self.clear_chat)
        
        toolbar_layout.addWidget(QLabel("モデル:"))
        toolbar_layout.addWidget(self.model_combo)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(settings_btn)
        toolbar_layout.addWidget(clear_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        # スプリッター
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # チャットエリア
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setMinimumHeight(400)
        
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout()
        self.chat_layout.addStretch()
        self.chat_widget.setLayout(self.chat_layout)
        self.chat_scroll.setWidget(self.chat_widget)
        
        splitter.addWidget(self.chat_scroll)
        
        # 入力エリア
        input_frame = QFrame()
        input_frame.setAcceptDrops(True)  # 入力エリアでドロップを受け付ける
        input_layout = QVBoxLayout()
        
        # ファイルリスト
        self.file_list = FileListWidget()
        self.file_list.files_changed.connect(self.on_files_changed)
        input_layout.addWidget(self.file_list)
        
        # テキスト入力
        text_input_layout = QHBoxLayout()
        
        self.text_input = QTextEdit()
        self.text_input.setMaximumHeight(120)
        self.text_input.setPlaceholderText("メッセージを入力してください... (ファイルをドラッグ&ドロップで添付)")
        self.text_input.setAcceptDrops(False)  # テキストエリアのドロップを無効化
        
        # 送信ボタン
        self.send_btn = QPushButton("送信")
        self.send_btn.setMinimumHeight(50)
        self.send_btn.clicked.connect(self.send_message)
        
        # ファイル追加ボタン
        file_btn = QPushButton("📎 ファイル")
        file_btn.setMaximumWidth(80)
        file_btn.clicked.connect(self.add_file_dialog)
        
        text_input_layout.addWidget(self.text_input)
        text_input_layout.addWidget(file_btn)
        text_input_layout.addWidget(self.send_btn)
        
        input_layout.addLayout(text_input_layout)
        input_frame.setLayout(input_layout)
        
        splitter.addWidget(input_frame)
        splitter.setSizes([600, 200])
        
        main_layout.addWidget(splitter)
        
        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)
        
        # エンターキーで送信
        self.text_input.installEventFilter(self)
        
        # 入力エリアのドロップイベント
        input_frame.dragEnterEvent = self.input_frame_dragEnterEvent
        input_frame.dropEvent = self.input_frame_dropEvent
        
    def setup_styles(self):
        """スタイル設定"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                padding: 10px;
                font-size: 12px;
                background-color: #FAFAFA;
            }
            QTextEdit:focus {
                border-color: #007AFF;
            }
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QComboBox {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
                background-color: white;
            }
            QScrollArea {
                border: 1px solid #E0E0E0;
                border-radius: 10px;
                background-color: white;
            }
            QListWidget {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                background-color: #F8F8F8;
                alternate-background-color: #FFFFFF;
            }
        """)
        
    def eventFilter(self, obj, event):
        """イベントフィルター"""
        if obj == self.text_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)
        
    def input_frame_dragEnterEvent(self, event: QDragEnterEvent):
        """入力エリアでのドラッグエンターイベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def input_frame_dropEvent(self, event: QDropEvent):
        """入力エリアでのドロップイベント"""
        urls = event.mimeData().urls()
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                self.file_list.add_file(file_path)
        event.acceptProposedAction()
        
    def open_settings(self):
        """設定ダイアログを開く"""
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_config()
            self.config = self.load_config()
            QMessageBox.information(self, "設定", "設定が保存されました。")
            
    def add_file_dialog(self):
        """ファイル選択ダイアログ"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "ファイルを選択", 
            "", 
            "All Files (*);;Images (*.png *.jpg *.jpeg *.gif *.bmp);;Documents (*.pdf *.doc *.docx);;Audio (*.mp3 *.wav *.ogg)"
        )
        for file_path in file_paths:
            self.file_list.add_file(file_path)
            
    def on_files_changed(self, files):
        """ファイル変更時の処理"""
        if files:
            self.file_list.show()
        else:
            self.file_list.hide()
            
    def add_chat_bubble(self, message: str, is_user: bool = False, images: List[str] = None):
        """チャット吹き出しを追加"""
        bubble = ChatBubble(message, is_user, images)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        
        # スクロールを最下部に
        QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
        
    def send_message(self):
        """メッセージ送信"""
        text = self.text_input.toPlainText().strip()
        if not text and not self.file_list.attached_files:
            return
            
        if not self.config.get('api_key'):
            QMessageBox.warning(self, "エラー", "APIキーが設定されていません。設定を確認してください。")
            return
            
        # 現在の添付ファイルをコピー（クリアされる前に）
        current_files = self.file_list.attached_files.copy()
        
        # ユーザーメッセージを追加（画像も表示）
        attached_images = [f.file_path for f in current_files if f.is_image()]
        self.add_chat_bubble(text if text else "画像を送信しました", True, attached_images)
        
        # メッセージを保存
        self.messages.append({
            'role': 'user',
            'content': text if text else "画像について教えてください"
        })
        
        # UI更新
        self.text_input.clear()
        self.send_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)  # インフィニットプログレス
        
        # ファイルをクリア（API呼び出し前に）
        self.file_list.clear_files()
        
        # デバッグ情報
        print(f"送信するファイル数: {len(current_files)}")
        for f in current_files:
            print(f"ファイル: {f.file_name}, タイプ: {f.mime_type}, 画像: {f.is_image()}")
        
        # API呼び出し（コピーしたファイルを使用）
        self.api_thread = OpenRouterAPIThread(
            self.config['api_key'],
            self.config['base_url'],
            self.get_selected_model(),  # 正しいモデルIDを取得
            self.messages,
            current_files
        )
        self.api_thread.message_received.connect(self.on_message_received)
        self.api_thread.error_occurred.connect(self.on_error_occurred)
        self.api_thread.start()
        
    def on_message_received(self, message: str):
        """メッセージ受信時の処理"""
        self.add_chat_bubble(message, False)
        self.messages.append({
            'role': 'assistant',
            'content': message
        })
        
        self.send_btn.setEnabled(True)
        self.progress_bar.hide()
        
    def on_error_occurred(self, error: str):
        """エラー発生時の処理"""
        QMessageBox.critical(self, "エラー", error)
        self.send_btn.setEnabled(True)
        self.progress_bar.hide()
        
    def clear_chat(self):
        """チャットをクリア"""
        # チャット履歴をクリア
        for i in reversed(range(self.chat_layout.count() - 1)):
            child = self.chat_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
                
        self.messages.clear()
        QMessageBox.information(self, "クリア", "チャット履歴がクリアされました。")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # モダンなスタイル
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
