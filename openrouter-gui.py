import sys
import os
import json
import base64
import mimetypes
import re
from typing import List, Optional, Dict, Any
from pathlib import Path

import requests
import keyring
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLineEdit, QPushButton, QScrollArea, QLabel, 
    QFrame, QSplitter, QComboBox, QDialog, QFormLayout, 
    QDialogButtonBox, QMessageBox, QFileDialog, QProgressBar,
    QListWidget, QListWidgetItem, QMenu, QToolButton, QTextBrowser
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QMimeData, QUrl, pyqtSlot,
    QPropertyAnimation, QEasingCurve, QRect, QTimer
)
from PyQt6.QtGui import (
    QFont, QPixmap, QDragEnterEvent, QDropEvent, QAction,
    QIcon, QPalette, QColor, QLinearGradient, QPainter
)

# 設定ファイルのパス（APIキー以外の設定用）
CONFIG_FILE = "openrouter_config.json"
# keyringサービス名
KEYRING_SERVICE = "OpenRouter-GUI"
KEYRING_USERNAME = "api_key"
# モデル情報キャッシュファイル
MODEL_CACHE_FILE = "model_cache.json"

class MarkdownRenderer:
    """マークダウンレンダラー"""
    
    def __init__(self):
        self.formatter = HtmlFormatter(
            style='default',
            noclasses=True,
            cssclass='highlight'
        )
        
    def render_markdown(self, text: str) -> str:
        """マークダウンテキストをHTMLに変換"""
        if not text.strip():
            return ""
            
        # コードブロックを事前処理してシンタックスハイライトを適用
        text = self._process_code_blocks(text)
        
        # Markdownを HTMLに変換
        md = markdown.Markdown(extensions=[
            'codehilite',
            'fenced_code', 
            'tables',
            'toc'
        ])
        
        html = md.convert(text)
        
        # CSSスタイルを追加
        styled_html = f"""
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            h1, h2, h3, h4, h5, h6 {{
                margin-top: 1.5em;
                margin-bottom: 0.5em;
                font-weight: 600;
            }}
            h1 {{ border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
            h2 {{ border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
            p {{
                margin-bottom: 1em;
            }}
            code {{
                background-color: #f8f8f8;
                color: #e83e8c;
                padding: 0.2em 0.5em;
                border-radius: 4px;
                font-size: 88%;
                font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                border: 1px solid #e1e4e8;
            }}
            pre {{
                background-color: #f8f9fa;
                color: #333;
                padding: 16px 20px;
                border-radius: 8px;
                overflow-x: auto;
                border: 1px solid #e1e4e8;
                margin: 12px 0;
                font-size: 14px;
                line-height: 1.45;
            }}
            pre code {{
                background-color: transparent;
                color: inherit;
                padding: 0;
                border: none;
                border-radius: 0;
                font-size: inherit;
                box-shadow: none;
            }}
            blockquote {{
                border-left: 4px solid #dfe2e5;
                padding-left: 1em;
                margin-left: 0;
                color: #6a737d;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }}
            table, th, td {{
                border: 1px solid #dfe2e5;
            }}
            th, td {{
                padding: 0.5em;
                text-align: left;
            }}
            th {{
                background-color: #f6f8fa;
                font-weight: 600;
            }}
            ul, ol {{
                padding-left: 2em;
            }}
            li {{
                margin-bottom: 0.5em;
            }}
            .highlight {{
                background: #f8f9fa !important;
                border-radius: 8px;
                padding: 16px 20px;
                border: 1px solid #e1e4e8;
                margin: 12px 0;
                overflow-x: auto;
            }}
            .highlight pre {{
                background: transparent !important;
                border: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            /* シンタックスハイライトの色調整 */
            .highlight .k {{ color: #d73a49; font-weight: 600; }}  /* キーワード */
            .highlight .s {{ color: #032f62; }}  /* 文字列 */
            .highlight .c {{ color: #6a737d; font-style: italic; }}  /* コメント */
            .highlight .n {{ color: #24292e; }}  /* 名前 */
            .highlight .o {{ color: #d73a49; }}  /* オペレータ */
            .highlight .p {{ color: #24292e; }}  /* 句読点 */
        </style>
        <div>{html}</div>
        """
        
        return styled_html
        
    def _process_code_blocks(self, text: str) -> str:
        """コードブロックにシンタックスハイライトを適用"""
        # ``` で囲まれたコードブロックを検出
        pattern = r'```(\w+)?\n(.*?)\n```'
        
        def replace_code_block(match):
            language = match.group(1) or 'text'
            code = match.group(2)
            
            try:
                lexer = get_lexer_by_name(language)
            except:
                lexer = TextLexer()
                
            highlighted = highlight(code, lexer, self.formatter)
            return highlighted
            
        return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)

class ModelInfoManager:
    """モデル情報管理クラス"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.cache = self.load_cache()
        
    def load_cache(self) -> Dict:
        """キャッシュを読み込み"""
        try:
            with open(MODEL_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"モデルキャッシュ読み込みエラー: {e}")
            return {}
    
    def save_cache(self):
        """キャッシュを保存"""
        try:
            with open(MODEL_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"モデルキャッシュ保存エラー: {e}")
    
    def get_model_info(self, model_id: str) -> Dict:
        """モデル情報を取得（キャッシュ優先）"""
        # キャッシュから確認
        if model_id in self.cache:
            cached_info = self.cache[model_id]
            # キャッシュが1週間以内なら使用
            import time
            if time.time() - cached_info.get('cached_at', 0) < 7 * 24 * 3600:
                return cached_info.get('info', {})
        
        # APIから取得
        return self._fetch_model_info(model_id)
    
    def _fetch_model_info(self, model_id: str) -> Dict:
        """OpenRouter APIからモデル情報を取得"""
        try:
            if not self.api_key:
                return self._get_default_model_info(model_id)
                
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models_data = response.json()
                for model in models_data.get('data', []):
                    if model.get('id') == model_id:
                        model_info = self._process_model_info(model)
                        
                        # キャッシュに保存
                        import time
                        self.cache[model_id] = {
                            'info': model_info,
                            'cached_at': time.time()
                        }
                        self.save_cache()
                        
                        return model_info
            
            # モデルが見つからない場合はデフォルト情報を返す
            return self._get_default_model_info(model_id)
            
        except Exception as e:
            print(f"モデル情報取得エラー: {e}")
            return self._get_default_model_info(model_id)
    
    def _process_model_info(self, model_data: Dict) -> Dict:
        """APIレスポンスからモデル情報を処理"""
        pricing = model_data.get('pricing', {})
        
        # 入力タイプを推定
        input_types = ['text']
        model_name = model_data.get('name', '').lower()
        model_id = model_data.get('id', '').lower()
        
        # Vision対応モデルを検出
        vision_keywords = ['vision', 'gpt-4o', 'claude-3', 'gemini', 'qwen-vl', 'pixtral', 'llama-3.2-90b-vision', 'phi-3.5-vision']
        if any(keyword in model_name or keyword in model_id for keyword in vision_keywords):
            input_types.append('image')
        
        return {
            'name': model_data.get('name', model_data.get('id', '')),
            'description': model_data.get('description', ''),
            'input_types': input_types,
            'context_length': model_data.get('context_length', 'Unknown'),
            'pricing_input': pricing.get('prompt', 'Unknown'),
            'pricing_output': pricing.get('completion', 'Unknown'),
            'top_provider': model_data.get('top_provider', {}).get('name', 'Unknown')
        }
    
    def _get_default_model_info(self, model_id: str) -> Dict:
        """デフォルトのモデル情報を返す"""
        # よく知られたモデルのデフォルト情報
        default_info = {
            'name': model_id,
            'description': 'モデル情報を取得中...',
            'input_types': ['text'],
            'context_length': 'Unknown',
            'pricing_input': 'Unknown',
            'pricing_output': 'Unknown',
            'top_provider': 'Unknown'
        }
        
        # Vision対応モデルの判定
        vision_models = [
            'gpt-4o', 'gpt-4-vision', 'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
            'gemini-pro-1.5', 'gemini-flash-1.5', 'qwen-2-vl', 'pixtral', 'llama-3.2-90b-vision', 'phi-3.5-vision'
        ]
        
        for vision_model in vision_models:
            if vision_model in model_id.lower():
                default_info['input_types'].append('image')
                break
                
        return default_info

class CustomModelDialog(QDialog):
    """カスタムモデル追加ダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("カスタムモデルを追加")
        self.setModal(True)
        self.resize(450, 300)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QFormLayout()
        
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setPlaceholderText("例: openai/gpt-4o-mini")
        
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("例: GPT-4o Mini - 高品質、低価格")
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("モデルの詳細説明（オプション）")
        
        layout.addRow("モデルID:", self.model_id_edit)
        layout.addRow("表示名:", self.model_name_edit)
        layout.addRow("説明:", self.description_edit)
        
        # ヘルプテキスト
        help_label = QLabel(
            "モデルIDはOpenRouterのモデル一覧から正確なIDを入力してください。\n"
            "例: openai/gpt-4o, anthropic/claude-3.5-sonnet など"
        )
        help_label.setStyleSheet("color: #666; font-size: 10px;")
        help_label.setWordWrap(True)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(help_label)
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)
        
    def get_model_data(self):
        return {
            'id': self.model_id_edit.text().strip(),
            'name': self.model_name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip()
        }

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
            # keyringからAPIキーを取得
            api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if api_key:
                self.api_key_edit.setText(api_key)
            
            # その他の設定をJSONファイルから取得
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.base_url_edit.setText(config.get('base_url', 'https://openrouter.ai/api/v1'))
        except FileNotFoundError:
            self.base_url_edit.setText('https://openrouter.ai/api/v1')
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
            
    def save_config(self):
        """設定を保存"""
        try:
            # APIキーをkeyringに保存
            api_key = self.api_key_edit.text()
            if api_key:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
            else:
                # APIキーが空の場合は削除
                try:
                    keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
                except keyring.errors.PasswordDeleteError:
                    pass
            
            # その他の設定をJSONファイルに保存（APIキーは除く）
            config = {
                'base_url': self.base_url_edit.text()
            }
            # 既存のカスタムモデルを保持
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
                    config['custom_models'] = existing_config.get('custom_models', [])
            except FileNotFoundError:
                config['custom_models'] = []
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"設定保存エラー: {e}")
            raise

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
        self.markdown_renderer = MarkdownRenderer()
        self.current_message = message
        self.text_browser = None  # ストリーミング用参照を保持
        self.setup_ui(message, images or [])
        
    def update_message(self, new_content: str):
        """メッセージを更新（ストリーミング用）"""
        if not self.is_user and self.text_browser:
            self.current_message += new_content
            try:
                # HTMLを更新してカーソルを最後に移動
                self.text_browser.setHtml(self.markdown_renderer.render_markdown(self.current_message))
                # カーソルを文書の最後に移動
                cursor = self.text_browser.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.text_browser.setTextCursor(cursor)
            except Exception as e:
                print(f"テキストブラウザ更新エラー: {e}")
                # エラー時は安全にプレーンテキストで表示
                self.text_browser.setPlainText(self.current_message)
        
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
        if self.is_user:
            # ユーザーメッセージは通常のテキスト表示
            text_label = QLabel(message)
            text_label.setWordWrap(True)
            text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            
            font = QFont()
            font.setPointSize(11)
            text_label.setFont(font)
            
            layout.addWidget(text_label)
        else:
            # AIメッセージはマークダウンレンダリング
            self.text_browser = QTextBrowser()
            self.text_browser.setHtml(self.markdown_renderer.render_markdown(message))
            self.text_browser.setOpenExternalLinks(True)
            self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            # コンテンツサイズに合わせて高さを自動調整
            self.text_browser.document().documentLayout().documentSizeChanged.connect(
                lambda size: self.text_browser.setFixedHeight(int(size.height()))
            )
            
            # QTextBrowserのスタイルを調整
            self.text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: transparent;
                    border: none;
                    font-size: 11px;
                }
            """)
            
            layout.addWidget(self.text_browser)
        
        self.setLayout(layout)
        
        # スタイル設定
        if self.is_user:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #667eea, stop: 1 #764ba2);
                    border-radius: 18px;
                    margin-left: 60px;
                    margin-right: 15px;
                    margin-top: 8px;
                    margin-bottom: 8px;
                    border: 2px solid rgba(255, 255, 255, 0.3);
                }
                QLabel {
                    color: white;
                    background-color: transparent;
                    font-weight: 500;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ffffff, stop: 1 #f7fafc);
                    border-radius: 18px;
                    margin-left: 15px;
                    margin-right: 60px;
                    margin-top: 8px;
                    margin-bottom: 8px;
                    border: 2px solid #e2e8f0;
                }
                QLabel {
                    color: #2d3748;
                    background-color: transparent;
                    font-weight: 500;
                }
                QTextBrowser {
                    background-color: transparent;
                    border: none;
                    color: #2d3748;
                }
            """)

class OpenRouterAPIThread(QThread):
    """OpenRouter API呼び出しスレッド"""
    message_received = pyqtSignal(str)
    message_chunk_received = pyqtSignal(str)  # ストリーミング用
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_key: str, base_url: str, model: str, messages: List[Dict], attached_files: List[AttachedFile]):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages
        self.attached_files = attached_files
        self._stop_requested = False
        self._response = None
        
    def run(self):
        try:
            if self._stop_requested:
                return
                
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
                "temperature": 0.7,
                "stream": True
            }
            
            if self._stop_requested:
                return
                
            self._response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60,
                stream=True
            )
            response = self._response
            
            if response.status_code == 200:
                full_message = ""
                for line in response.iter_lines():
                    if self._stop_requested:
                        break
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            json_str = line[6:]  # 'data: 'を除去
                            if json_str.strip() == '[DONE]':
                                break
                            try:
                                chunk_data = json.loads(json_str)
                                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        content = delta['content']
                                        full_message += content
                                        self.message_chunk_received.emit(content)
                            except json.JSONDecodeError:
                                continue
                
                if not self._stop_requested:
                    self.message_received.emit(full_message)  # 完了時に全体メッセージを送信
            else:
                if not self._stop_requested:
                    self.error_occurred.emit(f"API エラー: {response.status_code} - {response.text}")
                
        except Exception as e:
            if not self._stop_requested:
                self.error_occurred.emit(f"エラーが発生しました: {str(e)}")
    
    def stop(self):
        """推論を停止"""
        self._stop_requested = True
        if self._response:
            try:
                self._response.close()
            except:
                pass

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
        self.current_ai_bubble = None  # 現在ストリーミング中のAIメッセージバブル
        self.model_info_manager = ModelInfoManager(self.config.get('api_key'))
        
        self.setup_ui()
        self.setup_styles()
        
        # UI セットアップ完了後に初期モデル情報を表示
        current_model = self.get_selected_model()
        if current_model:
            self.update_model_info_display(current_model)
        
    def load_config(self) -> Dict:
        """設定を読み込み"""
        try:
            # keyringからAPIキーを取得
            api_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ''
            
            # その他の設定をJSONファイルから取得
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    config['api_key'] = api_key  # keyringから取得したAPIキーを追加
                    return config
            except FileNotFoundError:
                return {
                    'api_key': api_key, 
                    'base_url': 'https://openrouter.ai/api/v1', 
                    'custom_models': [],
                    'last_selected_model': None
                }
        except Exception as e:
            print(f"設定読み込みエラー: {e}")
            return {
                'api_key': '', 
                'base_url': 'https://openrouter.ai/api/v1', 
                'custom_models': [],
                'last_selected_model': None
            }
    
    def save_custom_model(self, model_data: Dict):
        """カスタムモデルを保存"""
        try:
            # 設定を読み込み
            config = self.load_config()
            if 'custom_models' not in config:
                config['custom_models'] = []
            
            # 同じIDのモデルがあるかチェック
            existing_model = next((m for m in config['custom_models'] if m['id'] == model_data['id']), None)
            if existing_model:
                return False  # 既に存在する
            
            # 新しいモデルを追加
            config['custom_models'].append(model_data)
            
            # APIキーを除いて保存
            save_config = {k: v for k, v in config.items() if k != 'api_key'}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"カスタムモデル保存エラー: {e}")
            return False
    
    def remove_custom_model(self, model_id: str):
        """カスタムモデルを削除"""
        try:
            config = self.load_config()
            if 'custom_models' not in config:
                return False
            
            original_count = len(config['custom_models'])
            config['custom_models'] = [m for m in config['custom_models'] if m['id'] != model_id]
            
            if len(config['custom_models']) < original_count:
                # APIキーを除いて保存
                save_config = {k: v for k, v in config.items() if k != 'api_key'}
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(save_config, f, ensure_ascii=False, indent=2)
                return True
            return False
        except Exception as e:
            print(f"カスタムモデル削除エラー: {e}")
            return False
    
    def save_last_selected_model(self, model_id: str):
        """最後に選択したモデルを保存"""
        try:
            config = self.load_config()
            config['last_selected_model'] = model_id
            
            # APIキーを除いて保存
            save_config = {k: v for k, v in config.items() if k != 'api_key'}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"最後に選択したモデル保存エラー: {e}")
            
    def setup_model_list(self):
        """モデルリストを設定"""
        self.model_combo.clear()
        
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
        
        # カスタムモデルがあればそれを最初に追加
        custom_models = self.config.get('custom_models', [])
        if custom_models:
            self.model_combo.addItem("────── 🔧 カスタムモデル ──────")
            separator_index = self.model_combo.count() - 1
            self.model_combo.model().item(separator_index).setEnabled(False)
            
            for model in custom_models:
                display_name = f"  {model['name']}"
                self.model_combo.addItem(display_name, f"custom:{model['id']}")
        
        for category, model_list in models.items():
            self.model_combo.addItem(f"────── {category} ──────")
            # セパレータアイテムは選択不可に
            separator_index = self.model_combo.count() - 1
            self.model_combo.model().item(separator_index).setEnabled(False)
            
            for model_id, description in model_list:
                self.model_combo.addItem(f"  {description}", model_id)
        
        # 最後に選択したモデルを復元、なければデフォルト選択
        last_selected_model = self.config.get('last_selected_model')
        if last_selected_model:
            # モデルIDに対応する表示テキストを検索
            for i in range(self.model_combo.count()):
                item_data = self.model_combo.itemData(i)
                if item_data:
                    # カスタムモデルの場合
                    if item_data.startswith("custom:") and item_data[7:] == last_selected_model:
                        self.model_combo.setCurrentIndex(i)
                        break
                    # 通常のモデルの場合
                    elif item_data == last_selected_model:
                        self.model_combo.setCurrentIndex(i)
                        break
            else:
                # 見つからない場合はデフォルト選択
                self.model_combo.setCurrentText("  GPT-4o - 最新、画像・文書解析")
        else:
            # 設定がない場合はデフォルト選択
            self.model_combo.setCurrentText("  GPT-4o - 最新、画像・文書解析")
        
        # 初期モデル情報を表示（UIがセットアップされた後）
        current_model = self.get_selected_model()
        if current_model and hasattr(self, 'model_info_label'):
            self.update_model_info_display(current_model)
        
    def get_selected_model(self) -> str:
        """選択されたモデルIDを取得"""
        current_data = self.model_combo.currentData()
        if current_data:
            # カスタムモデルの場合はプレフィックスを除去
            if current_data.startswith("custom:"):
                return current_data[7:]  # "custom:"を除去
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
        # カスタムモデルの削除用コンテキストメニュー
        self.model_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.model_combo.customContextMenuRequested.connect(self.show_model_context_menu)
        # モデル変更時の自動保存
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        
        # モデル追加ボタン
        add_model_btn = QPushButton("➕ モデル追加")
        add_model_btn.clicked.connect(self.add_custom_model)
        
        # 設定ボタン
        settings_btn = QPushButton("⚙️ 設定")
        settings_btn.clicked.connect(self.open_settings)
        
        # クリアボタン
        clear_btn = QPushButton("🗑️ クリア")
        clear_btn.clicked.connect(self.clear_chat)
        
        toolbar_layout.addWidget(QLabel("モデル:"))
        toolbar_layout.addWidget(self.model_combo)
        toolbar_layout.addWidget(add_model_btn)
        
        # モデル情報表示ラベル
        self.model_info_label = QLabel("")
        self.model_info_label.setStyleSheet("""
            QLabel {
                color: #667eea;
                font-size: 11px;
                font-weight: 500;
                padding: 4px 8px;
                background-color: rgba(102, 126, 234, 0.1);
                border-radius: 6px;
                margin-left: 8px;
            }
        """)
        toolbar_layout.addWidget(self.model_info_label)
        
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
        
        # 停止ボタン
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.clicked.connect(self.stop_inference)
        self.stop_btn.hide()  # 初期状態では非表示
        
        # ファイル追加ボタン
        file_btn = QPushButton("📎 ファイル")
        file_btn.setMaximumWidth(80)
        file_btn.clicked.connect(self.add_file_dialog)
        
        text_input_layout.addWidget(self.text_input)
        text_input_layout.addWidget(file_btn)
        text_input_layout.addWidget(self.send_btn)
        text_input_layout.addWidget(self.stop_btn)
        
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
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8f9ff, stop: 1 #e6f3ff);
            }
            QTextEdit {
                border: 2px solid #d1d9ff;
                border-radius: 12px;
                padding: 12px;
                font-size: 13px;
                background-color: #ffffff;
                color: #2d3748;
            }
            QTextEdit:focus {
                border-color: #667eea;
            }
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #667eea, stop: 1 #764ba2);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #5a67d8, stop: 1 #6b46c1);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #553c9a, stop: 1 #5b21b6);
            }
            QPushButton[objectName="stop_btn"] {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #e53e3e, stop: 1 #c53030);
            }
            QPushButton[objectName="stop_btn"]:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #fc8181, stop: 1 #e53e3e);
            }
            QPushButton[objectName="stop_btn"]:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #c53030, stop: 1 #9c2a2a);
            }
            QComboBox {
                border: 2px solid #d1d9ff;
                border-radius: 10px;
                padding: 8px 12px;
                background-color: #ffffff;
                color: #2d3748;
                font-size: 13px;
                font-weight: 500;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #667eea;
                background-color: #f7fafc;
            }
            QComboBox:focus {
                border-color: #667eea;
            }
            QComboBox::drop-down {
                border: none;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #667eea, stop: 1 #764ba2);
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 4px solid transparent;
                border-top: 6px solid white;
                margin: 0 8px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #d1d9ff;
                border-radius: 10px;
                background-color: #ffffff;
                selection-background-color: #667eea;
                selection-color: white;
                color: #2d3748;
                font-size: 13px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                border: none;
                padding: 8px 12px;
                margin: 2px;
                border-radius: 6px;
                min-height: 20px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e6f3ff;
                color: #2d3748;
            }
            QComboBox QAbstractItemView::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #667eea, stop: 1 #764ba2);
                color: white;
                font-weight: 600;
            }
            QComboBox QAbstractItemView::item:disabled {
                color: #a0aec0;
                background-color: transparent;
                font-style: italic;
            }
            QScrollArea {
                border: 2px solid #d1d9ff;
                border-radius: 12px;
                background-color: #ffffff;
            }
            QListWidget {
                border: 2px solid #d1d9ff;
                border-radius: 10px;
                background-color: #f7fafc;
                alternate-background-color: #ffffff;
                color: #2d3748;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #e6f3ff;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #667eea, stop: 1 #764ba2);
                color: white;
            }
            QLabel {
                color: #2d3748;
                font-weight: 500;
            }
            QProgressBar {
                border: 2px solid #d1d9ff;
                border-radius: 8px;
                background-color: #f7fafc;
                text-align: center;
                font-weight: 600;
                color: #2d3748;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #667eea, stop: 1 #764ba2);
                border-radius: 6px;
                margin: 2px;
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
            # ModelInfoManagerを更新
            self.model_info_manager = ModelInfoManager(self.config.get('api_key'))
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
        self.send_btn.hide()
        self.stop_btn.show()
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)  # インフィニットプログレス
        
        # ファイルをクリア（API呼び出し前に）
        self.file_list.clear_files()
        
        # デバッグ情報
        print(f"送信するファイル数: {len(current_files)}")
        for f in current_files:
            print(f"ファイル: {f.file_name}, タイプ: {f.mime_type}, 画像: {f.is_image()}")
        
        # ストリーミング用のAIメッセージバブルを先に作成
        self.current_ai_bubble = ChatBubble("", False)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.current_ai_bubble)
        
        # API呼び出し（コピーしたファイルを使用）
        self.api_thread = OpenRouterAPIThread(
            self.config['api_key'],
            self.config['base_url'],
            self.get_selected_model(),  # 正しいモデルIDを取得
            self.messages,
            current_files
        )
        self.api_thread.message_received.connect(self.on_message_received)
        self.api_thread.message_chunk_received.connect(self.on_message_chunk_received)
        self.api_thread.error_occurred.connect(self.on_error_occurred)
        self.api_thread.start()
        
    def on_message_chunk_received(self, chunk: str):
        """ストリーミングチャンク受信時の処理"""
        if self.current_ai_bubble:
            self.current_ai_bubble.update_message(chunk)
            # スクロールを最下部に
            QTimer.singleShot(10, lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            ))
    
    def on_message_received(self, message: str):
        """メッセージ受信完了時の処理"""
        self.messages.append({
            'role': 'assistant',
            'content': message
        })
        
        self.current_ai_bubble = None  # ストリーミング完了
        self.stop_btn.hide()
        self.send_btn.show()
        self.progress_bar.hide()
        
    def on_error_occurred(self, error: str):
        """エラー発生時の処理"""
        # エラー時は作成したAIバブルを削除
        if self.current_ai_bubble:
            self.current_ai_bubble.deleteLater()
            self.current_ai_bubble = None
        
        QMessageBox.critical(self, "エラー", error)
        self.stop_btn.hide()
        self.send_btn.show()
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
    
    def add_custom_model(self):
        """カスタムモデル追加"""
        dialog = CustomModelDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            model_data = dialog.get_model_data()
            
            # 入力検証
            if not model_data['id'] or not model_data['name']:
                QMessageBox.warning(self, "エラー", "モデルIDと表示名は必須です。")
                return
            
            # モデルを保存
            if self.save_custom_model(model_data):
                # 設定を再読み込み
                self.config = self.load_config()
                # モデルリストを更新
                current_text = self.model_combo.currentText()
                self.setup_model_list()
                # 可能であれば元の選択を復元
                index = self.model_combo.findText(current_text)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
                
                QMessageBox.information(self, "成功", f"カスタムモデル '{model_data['name']}' が追加されました。")
            else:
                QMessageBox.warning(self, "エラー", "同じIDのモデルが既に存在するか、保存に失敗しました。")
    
    def show_model_context_menu(self, position):
        """モデル選択のコンテキストメニュー"""
        current_data = self.model_combo.currentData()
        if current_data and current_data.startswith("custom:"):
            menu = QMenu(self)
            delete_action = menu.addAction("削除")
            
            action = menu.exec(self.model_combo.mapToGlobal(position))
            if action == delete_action:
                model_id = current_data[7:]  # "custom:"を除去
                self.delete_custom_model(model_id)
    
    def delete_custom_model(self, model_id: str):
        """カスタムモデルを削除"""
        reply = QMessageBox.question(
            self, "確認", 
            f"カスタムモデル '{model_id}' を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.remove_custom_model(model_id):
                # 設定を再読み込み
                self.config = self.load_config()
                # モデルリストを更新
                self.setup_model_list()
                QMessageBox.information(self, "成功", "カスタムモデルが削除されました。")
            else:
                QMessageBox.warning(self, "エラー", "カスタムモデルの削除に失敗しました。")
    
    def on_model_changed(self):
        """モデル変更時の処理"""
        current_model = self.get_selected_model()
        if current_model:
            self.save_last_selected_model(current_model)
            self.update_model_info_display(current_model)
    
    def update_model_info_display(self, model_id: str):
        """モデル情報表示を更新"""
        # ラベルが存在することを確認
        if not hasattr(self, 'model_info_label'):
            return
            
        try:
            model_info = self.model_info_manager.get_model_info(model_id)
            input_types = model_info.get('input_types', ['text'])
            
            # 入力タイプのアイコンを作成
            type_icons = []
            if 'text' in input_types:
                type_icons.append('📝')
            if 'image' in input_types:
                type_icons.append('🖼️')
            if 'audio' in input_types:
                type_icons.append('🎵')
            if 'video' in input_types:
                type_icons.append('🎥')
            
            # 表示テキストを作成
            if len(type_icons) > 1:
                info_text = f"{''.join(type_icons)} テキスト・画像対応"
            else:
                info_text = f"{''.join(type_icons)} テキストのみ"
            
            self.model_info_label.setText(info_text)
            self.model_info_label.setToolTip(f"モデル: {model_info.get('name', model_id)}\n"
                                            f"対応入力: {', '.join(input_types)}\n"
                                            f"コンテキスト長: {model_info.get('context_length', 'Unknown')}")
            
        except Exception as e:
            print(f"モデル情報表示エラー: {e}")
            self.model_info_label.setText("📝 テキストのみ")
            self.model_info_label.setToolTip("モデル情報を取得できませんでした")
    
    def stop_inference(self):
        """推論を停止"""
        if self.api_thread and self.api_thread.isRunning():
            self.api_thread.stop()
            self.api_thread.wait(1000)  # 1秒待機
            
            # 現在のAIバブルを削除
            if self.current_ai_bubble:
                self.current_ai_bubble.deleteLater()
                self.current_ai_bubble = None
            
            # UIを元に戻す
            self.stop_btn.hide()
            self.send_btn.show()
            self.progress_bar.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # モダンなスタイル
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
