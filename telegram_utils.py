"""
Telegram & Universal Share Utilities for VIP Receipt System.
Supports Universal Share Sheet, Direct Telegram Desktop Launch, Clipboard Image Copying, and Bot sendPhoto API.
"""

import os
import json
import uuid
import subprocess
import urllib.request
import urllib.parse
import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QFrame, QApplication, QFileDialog
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, QUrl, QMimeData
from receipt_generator import ReceiptGenerator


CONFIG_FILE = "telegram_config.json"


def get_telegram_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"bot_token": "", "chat_id": ""}


def save_telegram_config(bot_token, chat_id):
    cfg = {"bot_token": bot_token.strip(), "chat_id": chat_id.strip()}
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving telegram config: {e}")


def get_telegram_exe_path():
    candidates = [
        os.path.join(os.path.expanduser("~"), r"AppData\Roaming\Telegram Desktop\Telegram.exe"),
        os.path.join(os.path.expanduser("~"), r"AppData\Local\Telegram Desktop\Telegram.exe"),
        r"C:\Program Files\Telegram Desktop\Telegram.exe",
        r"C:\Program Files (x86)\Telegram Desktop\Telegram.exe"
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def launch_telegram_desktop():
    exe_path = get_telegram_exe_path()
    if exe_path:
        try:
            subprocess.Popen([exe_path])
            return True
        except Exception as e:
            print(f"Error launching Telegram.exe: {e}")

    try:
        os.system("start telegram:")
        return True
    except Exception:
        pass
    return False


def copy_receipt_image_to_clipboard(png_path):
    if os.path.exists(png_path):
        q_img = QImage(png_path)
        if not q_img.isNull():
            cb = QApplication.clipboard()
            if cb:
                mime_data = QMimeData()
                mime_data.setImageData(q_img)
                mime_data.setUrls([QUrl.fromLocalFile(png_path)])
                cb.setMimeData(mime_data)
                return True
    return False


def send_telegram_photo_bot(bot_token, chat_id, photo_path, caption=""):
    """
    Sends PNG photo directly to Telegram Chat / Channel via Bot API sendPhoto.
    """
    if not bot_token or not chat_id:
        return {"ok": False, "description": "Missing Bot Token or Chat ID"}

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

    body = bytearray()

    # chat_id parameter
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode('utf-8'))

    # caption parameter
    if caption:
        body.extend(f"--{boundary}\r\n".encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode('utf-8'))

    # photo file
    file_name = os.path.basename(photo_path)
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="photo"; filename="{file_name}"\r\n'.encode('utf-8'))
    body.extend(f'Content-Type: image/png\r\n\r\n'.encode('utf-8'))

    with open(photo_path, 'rb') as f:
        body.extend(f.read())
    body.extend(f"\r\n--{boundary}--\r\n".encode('utf-8'))

    req = urllib.request.Request(url, data=bytes(body))
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            return res_data
    except Exception as e:
        return {"ok": False, "description": str(e)}


class UniversalShareDialog(QDialog):
    """
    Universal Share & Quick Action Sheet styled after modern mobile/desktop system share sheets.
    Supports Telegram Bot, Telegram App, Clipboard Copy (Image & Text for WhatsApp/Messenger/Zalo),
    PNG Export, PDF Export, and File Explorer.
    """
    def __init__(self, receipt_data, parent=None):
        super().__init__(parent)
        self.receipt_data = receipt_data
        self.setWindowTitle("🔗 Universal Share & Export Center")
        self.setMinimumWidth(500)

        self.inv_no = receipt_data.get("receipt_no", "INV_0001")
        self.cust_name = receipt_data.get("customer_name", "N/A")
        items = receipt_data.get("items", [])
        totals = receipt_data.get("totals", {})
        self.tot_usd = totals.get("usd", 0.0)
        self.tot_baht = totals.get("baht", 0.0)
        self.rate = receipt_data.get("exchange_rate", 33.9)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Info Card
        info_card = QFrame()
        info_card.setStyleSheet("QFrame { background-color: #0f172a; border: 1.5px solid #38bdf8; border-radius: 10px; padding: 12px; }")
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setSpacing(4)

        lbl_title = QLabel(f"🧾 INVOICE: {self.inv_no}")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")

        lbl_details = QLabel(
            f"👤 អ្នកបញ្ជូន / ភ្ញៀវ: {self.cust_name}  ({len(items)} Pax)\n"
            f"💵 សរុបដុល្លារ: ${self.tot_usd:.2f}  |  ฿ {self.tot_baht:,.0f} (Rate {self.rate:.1f})"
        )
        lbl_details.setStyleSheet("font-size: 12px; color: #f8fafc;")

        ic_layout.addWidget(lbl_title)
        ic_layout.addWidget(lbl_details)
        layout.addWidget(info_card)

        # Action Sheet Items Container
        sheet_container = QFrame()
        sheet_container.setStyleSheet("QFrame { background-color: #1e293b; border-radius: 10px; padding: 8px; }")
        sc_layout = QVBoxLayout(sheet_container)
        sc_layout.setSpacing(8)

        # 1. Share to Telegram App / Desktop
        btn_tg_app = self._create_action_btn("✈️ Share to Telegram Desktop / App", "#0088cc", "បើក Telegram App & Copy រូបភាពវិក័យប័ត្រចូល Clipboard (Ctrl+V)")
        btn_tg_app.clicked.connect(self._action_telegram_app)
        sc_layout.addWidget(btn_tg_app)

        # 2. Copy Image to Clipboard (WhatsApp, Messenger, Zalo, Viber)
        btn_clip_img = self._create_action_btn("📋 Copy Image to Clipboard (WhatsApp / Messenger / Zalo)", "#8b5cf6", "Copy រូបភាពវិក័យប័ត្រ សម្រាប់ Ctrl+V ផ្ញើក្នុង WhatsApp, Messenger, Viber, Zalo, Email")
        btn_clip_img.clicked.connect(self._action_copy_image)
        sc_layout.addWidget(btn_clip_img)

        # 3. 1-Click Telegram Bot Delivery
        btn_tg_bot = self._create_action_btn("⚡ ផ្ញើអូតូទៅ Telegram Bot (1-Click Bot Delivery)", "#0284c7", "ផ្ញើរូបភាពវិក័យប័ត្រទៅ Telegram Channel / Group តាមរយៈ Telegram Bot")
        btn_tg_bot.clicked.connect(self._action_telegram_bot)
        sc_layout.addWidget(btn_tg_bot)

        # 4. Save PNG Image
        btn_save_png = self._create_action_btn("🖼️ Save to Gallery / Save PNG Image", "#10b981", "រក្សាទុករូបភាពវិក័យប័ត្រជាឯកសារ PNG លើកុំព្យូទ័រ")
        btn_save_png.clicked.connect(self._action_save_png)
        sc_layout.addWidget(btn_save_png)

        # 5. Save PDF Document
        btn_save_pdf = self._create_action_btn("📄 Save PDF Document", "#f59e0b", "រក្សាទុកវិក័យប័ត្រជាឯកសារ PDF")
        btn_save_pdf.clicked.connect(self._action_save_pdf)
        sc_layout.addWidget(btn_save_pdf)

        layout.addWidget(sheet_container)

    def _create_action_btn(self, title, color, tooltip):
        btn = QPushButton(title)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: white; font-weight: bold; font-size: 13px; padding: 10px 14px; text-align: left; border-radius: 6px; }}"
            f"QPushButton:hover {{ opacity: 0.9; border: 1px solid white; }}"
        )
        btn.setToolTip(tooltip)
        return btn

    def _render_temp_png(self):
        temp_dir = os.path.join(os.path.expanduser("~"), ".gemini")
        if not os.path.exists(temp_dir):
            temp_dir = os.getcwd()
        
        # Format filename using strictly the travel date (e.g. 30-07-2026.png)
        travel_date = (self.receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip()
        if not clean_date:
            clean_date = datetime.datetime.now().strftime("%d-%m-%Y")

        out_png = os.path.join(temp_dir, f"{clean_date}.png")
        ReceiptGenerator.export_group_image(self.receipt_data, out_png)
        return out_png

    def _action_telegram_app(self):
        png_path = self._render_temp_png()
        copy_receipt_image_to_clipboard(png_path)
        launched = launch_telegram_desktop()

        if launched:
            QMessageBox.information(
                self, "Telegram Ready",
                "🚀 **បានបើក Telegram Desktop និង Copy រូបភាពវិក័យប័ត្រចូល Clipboard រួចរាល់!**\n\n"
                "លោកអ្នកអាចចុច **Ctrl + V** ក្នុង Telegram Chat ដើម្បី Paste ផ្ញើរូបភាពវិក័យប័ត្របានភ្លាមៗ!"
            )
        else:
            QMessageBox.information(
                self, "Clipboard Ready",
                "📋 **បាន Copy រូបភាពវិក័យប័ត្រចូល Clipboard រួចរាល់!**\n\n"
                "សូមបើក Telegram រួចចុច **Ctrl + V** ដើម្បី Paste ផ្ញើរូបភាព!"
            )
        self.accept()

    def _action_copy_image(self):
        png_path = self._render_temp_png()
        copied = copy_receipt_image_to_clipboard(png_path)
        if copied:
            QMessageBox.information(
                self, "Copied to Clipboard",
                "📋 **បាន Copy រូបភាពវិក័យប័ត្រចូល Clipboard រួចរាល់!**\n\n"
                "លោកអ្នកអាចបើក **WhatsApp, Messenger, Viber, Zalo, Telegram, ឬ Email** រួចចុច **Ctrl + V** ដើម្បី Paste ផ្ញើរូបភាពវិក័យប័ត្របានភ្លាមៗ!"
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "មិនអាច Copy រូបភាពទៅ Clipboard បានទេ!")

    def _action_telegram_bot(self):
        cfg = get_telegram_config()
        token = cfg.get("bot_token", "")
        chat_id = cfg.get("chat_id", "")

        if not token or not chat_id:
            # Small dialog to prompt for Token & Chat ID
            token, ok1 = QLineEdit.getText(self, "Telegram Bot Config", "សូមបញ្ចូល Telegram Bot Token:")
            if not ok1 or not token:
                return
            chat_id, ok2 = QLineEdit.getText(self, "Telegram Bot Config", "សូមបញ្ចូល Chat ID / Group ID / Channel (@channel_id):")
            if not ok2 or not chat_id:
                return
            save_telegram_config(token, chat_id)

        png_path = self._render_temp_png()
        caption = (
            f"🧾 INVOICE RECEIPT SUMMARY\n"
            f"• Invoice No: {self.inv_no}\n"
            f"• Customer: {self.cust_name}\n"
            f"• Total USD: ${self.tot_usd:.2f}\n"
            f"• Total Baht: ฿{self.tot_baht:,.0f} (Rate {self.rate:.1f})\n"
            f"📌 Golden Mekong VIP Service"

        )
        res = send_telegram_photo_bot(token, chat_id, png_path, caption)
        if res.get("ok"):
            QMessageBox.information(self, "Success", f"🎉 បានផ្ញើវិក័យប័ត្ររូបភាព PNG ទៅកាន់ Telegram [{chat_id}] រួចរាល់ដោយជោគជ័យ!")
            self.accept()
        else:
            err = res.get("description", "Unknown error")
            QMessageBox.critical(self, "Telegram API Error", f"មិនអាចផ្ញើទៅ Telegram Bot បានទេ:\n{err}")

    def _action_save_png(self):
        travel_date = (self.receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.png"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Invoice PNG Image", default_filename, "PNG Images (*.png)")
        if file_path:
            out_file = ReceiptGenerator.export_group_image(self.receipt_data, file_path)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PNG រួចរាល់!\n\nSaved to:\n{out_file}")
            self.accept()

    def _action_save_pdf(self):
        travel_date = (self.receipt_data.get("date_str") or datetime.datetime.now().strftime("%d-%m-%Y")).strip()
        clean_date = travel_date.replace("/", "-").replace("\\", "-").strip() or datetime.datetime.now().strftime("%d-%m-%Y")
        default_filename = f"{clean_date}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Invoice PDF Document", default_filename, "PDF Files (*.pdf)")
        if file_path:
            out_file = ReceiptGenerator.export_group_pdf(self.receipt_data, file_path)
            QMessageBox.information(self, "Success", f"🎉 បានទាញយកវិក័យប័ត្រ PDF រួចរាល់!\n\nSaved to:\n{out_file}")
            self.accept()
