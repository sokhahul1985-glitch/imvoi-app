"""
Telegram & Universal Share Utilities for VIP Receipt System.
Supports Universal Share Sheet, Direct Telegram Desktop Launch, Clipboard Image Copying, and Bot sendPhoto API.
"""

import os
import re
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


CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")


def get_telegram_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                if cfg.get("bot_token"):
                    if not cfg.get("chat_id"):
                        cfg["chat_id"] = "8985821312"
                    return cfg
        except Exception:
            pass
    return {"bot_token": "8884318593:AAEipEVki9o1YFL0_8IYoUeSn3Xif4dlVOk", "chat_id": "8985821312"}


def save_telegram_config(bot_token, chat_id):
    cfg = {"bot_token": bot_token.strip(), "chat_id": chat_id.strip()}
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving telegram config: {e}")

def format_group_customer_names(members):
    if not members:
        return ""
    clean_names = []
    for m in members:
        if isinstance(m, str):
            name = m
        elif isinstance(m, dict):
            name = m.get('full_english_name') or m.get('english_name') or m.get('name') or m.get('passport_name') or ''
        else:
            name = str(m)
        name = re.sub(r'^\d+[\.\)]\s*', '', name)
        name = re.sub(r'\s*\(\+\d+\s*នាក់\)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\(\+\d+\s*Pax\)', '', name, flags=re.IGNORECASE)
        name = name.strip()
        if name and not re.match(r'^[A-Z]{1,2}\d{6,9}$', name, re.IGNORECASE):
            clean_names.append(name)
    if not clean_names:
        return ""
    if len(clean_names) == 1:
        return clean_names[0]
    return ", ".join([f"{idx + 1}. {n}" for idx, n in enumerate(clean_names)])


def get_next_sequential_invoice_no(data_dir=None):
    counter_file = os.path.join(data_dir or os.getcwd(), "invoice_counter.json")
    counter = {"last_number": 0, "prefix": "INV "}
    if os.path.exists(counter_file):
        try:
            with open(counter_file, 'r', encoding='utf-8') as f:
                counter = json.load(f)
        except Exception:
            pass
    counter["last_number"] = counter.get("last_number", 0) + 1
    prefix = counter.get("prefix", "INV ")
    inv_no = f"{prefix}{counter['last_number']:05d}"
    try:
        with open(counter_file, 'w', encoding='utf-8') as f:
            json.dump(counter, f, indent=2)
    except Exception as e:
        print(f"Error updating invoice counter: {e}")
    return inv_no


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


def send_telegram_text_bot(bot_token, chat_id, text, parse_mode=None):
    """
    Sends text message directly to Telegram Chat / Channel via Bot API sendMessage.
    """
    if not bot_token or not chat_id:
        return {"ok": False, "description": "Missing Bot Token or Chat ID"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = {"chat_id": chat_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    payload = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"ok": False, "description": str(e)}


def get_telegram_bot_info(bot_token):
    """
    Checks if bot_token is valid and returns Bot user info.
    """
    if not bot_token:
        return {"ok": False, "description": "No bot token provided"}
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"ok": False, "description": str(e)}


import threading
import time
import io
from PIL import Image

try:
    from ocr_engine import DocumentAIEngine, clean_person_name
except Exception:
    DocumentAIEngine = None
    def clean_person_name(s): return s


class TelegramBotListener:
    """
    Background Thread Listener that long-polls Telegram Bot API for incoming passport images,
    runs AI OCR, saves extracted customer data to saved_customers.json, notifies Telegram chat,
    and makes live scan results available for Web UI polling.
    """
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.getcwd()
        self.saved_customers_file = os.path.join(self.data_dir, 'saved_customers.json')
        self.running = False
        self.thread = None
        self.last_update_id = 0
        self.recent_scans = []
        self.bot_info = None
        self.ocr_engine = None
        self.lock = threading.Lock()
        self.auto_issue_invoice = False  # មិនបាច់អោយប៊តចេញវិក្កយបត្រស្វ័យប្រវត្តិទេ

    def start(self, bot_token=None):
        if self.running:
            return
        cfg = get_telegram_config()
        token = bot_token or cfg.get("bot_token", "")
        if not token:
            print("[TelegramBotListener] No bot token configured. Listener not started.")
            return

        # Check bot validity
        info = get_telegram_bot_info(token)
        if not info.get("ok"):
            print(f"[TelegramBotListener] Invalid Bot Token: {info.get('description')}")
            return

        self.bot_info = info.get("result", {})
        print(f"[TelegramBotListener] Starting listener for @{self.bot_info.get('username')}...")

        if DocumentAIEngine and self.ocr_engine is None:
            try:
                self.ocr_engine = DocumentAIEngine()
            except Exception as e:
                print(f"[TelegramBotListener] Could not init OCR engine: {e}")

        self.running = True
        self.thread = threading.Thread(target=self._poll_updates_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def get_status(self):
        cfg = get_telegram_config()
        token = cfg.get("bot_token", "")
        return {
            "running": self.running,
            "bot_username": self.bot_info.get("username", "") if self.bot_info else "",
            "bot_first_name": self.bot_info.get("first_name", "") if self.bot_info else "",
            "has_token": bool(token),
            "total_recent_scans": len(self.recent_scans)
        }

    def get_latest_scans(self, since_id=None):
        with self.lock:
            if since_id:
                return [s for s in self.recent_scans if s["id"] > since_id]
            return list(self.recent_scans[-20:])

    def _is_update_processed(self, uid_key):
        if not uid_key:
            return False
        cache_file = os.path.join(self.data_dir, "processed_tg_updates.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    processed = json.load(f)
                if uid_key in processed:
                    return True
        except Exception:
            pass
        return False

    def _mark_update_processed(self, uid_keys):
        if isinstance(uid_keys, str):
            uid_keys = [uid_keys]
        cache_file = os.path.join(self.data_dir, "processed_tg_updates.json")
        try:
            processed = []
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        processed = json.load(f)
                except Exception:
                    processed = []
            for k in uid_keys:
                if k and k not in processed:
                    processed.append(k)
            if len(processed) > 1000:
                processed = processed[-1000:]
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(processed, f, indent=2)
        except Exception as e:
            print(f"[TelegramBotListener] Error saving processed update cache: {e}")

    def _save_customer_to_file(self, cust_data):
        if not getattr(self, 'auto_issue_invoice', False):
            return
        try:
            customers = []
            if os.path.exists(self.saved_customers_file):
                try:
                    with open(self.saved_customers_file, 'r', encoding='utf-8') as f:
                        customers = json.load(f)
                except Exception:
                    customers = []

            # Check if identical group/customer record was already saved recently (deduplication)
            new_r_no = cust_data.get("receipt_no") or cust_data.get("group_data", {}).get("receipt_no")
            new_members = cust_data.get("members", [])
            new_members_str = json.dumps([m.get("full_english_name") or m.get("name") for m in new_members])
            
            for idx, c in enumerate(customers[:10]):
                existing_r_no = c.get("receipt_no") or c.get("group_data", {}).get("receipt_no")
                if existing_r_no == new_r_no:
                    customers[idx].update(cust_data)
                    with open(self.saved_customers_file, 'w', encoding='utf-8') as f:
                        json.dump(customers, f, ensure_ascii=False, indent=2)
                    return

                if new_members:
                    existing_members_str = json.dumps([m.get("full_english_name") or m.get("name") for m in c.get("members", [])])
                    if existing_members_str == new_members_str and len(new_members) > 0:
                        print(f"[TelegramBotListener] Duplicate group customer record detected. Skipping duplicate insertion.")
                        return

            # Check if single passport already exists
            p_no = cust_data.get("passport_no", "").strip().upper()
            if p_no and p_no != "-":
                for idx, c in enumerate(customers):
                    if c.get("passport_no", "").strip().upper() == p_no and not c.get("members"):
                        customers[idx].update(cust_data)
                        with open(self.saved_customers_file, 'w', encoding='utf-8') as f:
                            json.dump(customers, f, ensure_ascii=False, indent=2)
                        return

            customers.insert(0, cust_data)
            with open(self.saved_customers_file, 'w', encoding='utf-8') as f:
                json.dump(customers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TelegramBotListener] Error saving customer: {e}")

    def _record_incoming_message(self, msg, update_id, token=None):
        try:
            # ONLY record messages from private chat (e.g. Chat ID 8985821312 or private customer chat).
            # Do NOT record messages from driver groups!
            chat = msg.get("chat") or {}
            chat_type = str(chat.get("type", "")).lower()
            chat_id_str = str(chat.get("id", ""))
            if chat_type in ["group", "supergroup", "channel"] or chat_id_str.startswith("-"):
                return

            text = (msg.get("text") or msg.get("caption") or "").strip()
            photos = msg.get("photo")
            doc = msg.get("document")
            has_img = bool(photos) or (doc and (doc.get("mime_type") or "").startswith("image/"))

            if not text and not has_img:
                return
            if text and text.startswith('/'):
                return

            sender = msg.get("from", {})
            sender_name = sender.get("first_name", "") + (" " + sender.get("last_name", "") if sender.get("last_name") else "")
            sender_name = sender_name.strip() or msg.get("chat", {}).get("title", "Telegram User")

            # Category detection
            cat = "ប៉ាស្ព័រ"
            t_low = text.lower()
            if any(k in t_low for k in ['flight', '✈', '✈️', 'dmk', 'bkk', 'sai', 'airasia', 'air', 'fd', 'fd-', 'fd ', 'we', 'sl', 'v9', 'k6', 'pg', 'tg', 'qv', 'ហោះហើរ', 'សំបុត្រ', 'ตั๋วเครื่องบิน', 'ไฟลท์', 'ขาเข้า', 'ขาออก', 'สนามบิน', 'airport', 'pnr', 'boarding']):
                cat = 'សំបុត្រយន្តហោះ'
            elif any(k in t_low for k in ['passport', 'បាសស្ព័រ', 'ប៉ាស្ព័រ', 'លិខិតឆ្លងដែន', 'พาสปอร์ต', 'pass', 'pp']):
                cat = 'ប៉ាស្ព័រ'
            elif any(k in t_low for k in ['alphard', 'hiace', 'staria', 'ឡានជួល']):
                cat = 'រូបឡាន'

            img_list = []
            if has_img and token:
                tg_img_dir = os.path.join(self.data_dir, "telegram_images")
                os.makedirs(tg_img_dir, exist_ok=True)
                file_id = None
                file_name = f"telegram_photo_{update_id}.jpg"
                if photos:
                    file_id = photos[-1].get("file_id")
                elif doc:
                    file_id = doc.get("file_id")
                    file_name = doc.get("file_name") or file_name

                if file_id:
                    try:
                        g_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                        req_f = urllib.request.Request(g_url)
                        with urllib.request.urlopen(req_f, timeout=10) as resp_f:
                            f_info = json.loads(resp_f.read().decode('utf-8'))
                        if f_info.get("ok") and f_info.get("result", {}).get("file_path"):
                            f_path = f_info["result"]["file_path"]
                            dl_url = f"https://api.telegram.org/file/bot{token}/{f_path}"
                            clean_fid = re.sub(r'[^a-zA-Z0-9]', '', str(file_id))[:10]
                            local_name = f"tg_photo_{update_id}_{clean_fid}.jpg"
                            local_dest = os.path.join(tg_img_dir, local_name)
                            with urllib.request.urlopen(dl_url, timeout=15) as r_dl:
                                with open(local_dest, "wb") as f_out:
                                    f_out.write(r_dl.read())
                            
                            # Aspect ratio check for passport vs flight ticket
                            try:
                                from PIL import Image
                                with Image.open(local_dest) as im:
                                    w, h = im.size
                                    aspect = max(w, h) / max(min(w, h), 1)
                                    if h > w and aspect >= 1.62:
                                        if any(k in t_low for k in ['flight', '✈', 'dmk', 'sai', 'bkk', 'airasia', 'ขาเข้า', 'ขาออก', 'pnr']):
                                            cat = 'សំបុត្រយន្តហោះ'
                                    elif 1.20 <= aspect <= 1.58:
                                        cat = 'ប៉ាស្ព័រ'
                            except Exception:
                                pass

                            img_list.append({
                                "id": f"IMG-TG-{update_id}",
                                "name": file_name,
                                "category": cat,
                                "url": f"/telegram_images/{local_name}",
                                "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            })
                    except Exception as e_img:
                        print("[TelegramBotListener] Error caching image:", e_img)

            if not text and img_list:
                cat_label = img_list[0].get('category', cat)
                text = f"📷 រូបភាព ({cat_label}) ពី {sender_name}"

            rec_file = os.path.join(self.data_dir, "received_telegram_messages.json")
            existing = []
            if os.path.exists(rec_file):
                for _ in range(4):
                    try:
                        with open(rec_file, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                        if isinstance(existing, list):
                            break
                    except Exception:
                        time.sleep(0.08)

            now_ts = int(time.time())

            # Check if this exact update or image URL was already processed
            is_dup = any(
                str(x.get("id")) == str(update_id) or
                (img_list and any(
                    any(img.get("url") == ex_img.get("url") for ex_img in x.get("images", []))
                    for img in img_list
                ))
                for x in existing[:40]
            )

            if not is_dup:
                mg_id = msg.get("media_group_id")
                merged_into_recent_album = False
                if img_list:
                    for ex_msg in existing[:10]:
                        same_mg = mg_id and ex_msg.get('media_group_id') == mg_id
                        same_sender_time = (ex_msg.get('sender') == sender_name and abs(now_ts - ex_msg.get('timestamp', now_ts)) < 180)
                        if same_mg or same_sender_time:
                            if 'images' not in ex_msg or not isinstance(ex_msg['images'], list):
                                ex_msg['images'] = []
                            for new_img in img_list:
                                if not any(e_img.get('url') == new_img.get('url') for e_img in ex_msg['images']):
                                    ex_msg['images'].append(new_img)
                            
                            # Preserve real booking text - never overwrite real text with placeholder
                            ex_text = ex_msg.get('text', '').strip()
                            is_placeholder = not ex_text or ex_text.startswith('📷 រូបភាព') or ex_text.startswith('📘 រូបប៉ាស្ព័រ')
                            is_new_placeholder = not text or text.startswith('📷 រូបភាព') or text.startswith('📘 រូបប៉ាស្ព័រ')
                            if is_placeholder and not is_new_placeholder:
                                ex_msg['text'] = text
                            elif not is_placeholder and not is_new_placeholder and text != ex_text:
                                if text not in ex_text:
                                    ex_msg['text'] = f"{ex_text}\n\n{text}"

                            ex_msg['timestamp'] = now_ts
                            ex_msg['date'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            if mg_id:
                                ex_msg['media_group_id'] = mg_id
                            merged_into_recent_album = True
                            break

                if not merged_into_recent_album:
                    new_entry = {
                        "id": update_id or now_ts,
                        "text": text,
                        "sender": sender_name,
                        "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "timestamp": now_ts,
                        "media_group_id": mg_id,
                        "images": img_list
                    }
                    existing.insert(0, new_entry)

                # Also auto-link images to any matching booking text from the same sender within 30 mins
                if img_list:
                    for ex_msg in existing:
                        if ex_msg.get('sender') == sender_name and abs(now_ts - ex_msg.get('timestamp', now_ts)) < 1800:
                            if not ex_msg.get('text', '').startswith('📷 រូបភាព') and not ex_msg.get('text', '').startswith('📘 រូបប៉ាស្ព័រ'):
                                if 'images' not in ex_msg or not isinstance(ex_msg['images'], list):
                                    ex_msg['images'] = []
                                for new_img in img_list:
                                    if not any(e_img.get('url') == new_img.get('url') for e_img in ex_msg['images']):
                                        ex_msg['images'].append(new_img)
                                break

                if len(existing) > 100:
                    existing = existing[:100]

                # Atomic write
                tmp_file = f"{rec_file}.tmp_{os.getpid()}_{int(time.time()*1000)}"
                try:
                    with open(tmp_file, "w", encoding="utf-8") as f:
                        json.dump(existing, f, ensure_ascii=False, indent=2)
                    if os.path.exists(rec_file):
                        try: os.replace(tmp_file, rec_file)
                        except Exception:
                            with open(rec_file, "w", encoding="utf-8") as f:
                                json.dump(existing, f, ensure_ascii=False, indent=2)
                    else:
                        with open(rec_file, "w", encoding="utf-8") as f:
                            json.dump(existing, f, ensure_ascii=False, indent=2)
                except Exception as e_w:
                    with open(rec_file, "w", encoding="utf-8") as f:
                        json.dump(existing, f, ensure_ascii=False, indent=2)
                if os.path.exists(tmp_file):
                    try: os.remove(tmp_file)
                    except Exception: pass
        except Exception as e:
            print("[TelegramBotListener] Error recording incoming message:", e)

    def _poll_updates_loop(self):
        while self.running:
            try:
                cfg = get_telegram_config()
                token = cfg.get("bot_token", "")
                if not token:
                    time.sleep(5)
                    continue

                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=10&offset={self.last_update_id + 1}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                if not data.get("ok"):
                    time.sleep(3)
                    continue

                updates = data.get("result", [])
                
                # Batch collection by media_group_id or rapid multi-photos
                media_groups = {}
                single_photos = []
                text_msgs = []

                for upd in updates:
                    self.last_update_id = max(self.last_update_id, upd["update_id"])

                    # Detect and record any group or supergroup where bot was added or received a message
                    chat = None
                    if upd.get("my_chat_member"):
                        chat = upd["my_chat_member"].get("chat")
                    elif upd.get("message"):
                        chat = upd["message"].get("chat")
                    elif upd.get("channel_post"):
                        chat = upd["channel_post"].get("chat")

                    if chat and str(chat.get("type", "")).lower() in ["group", "supergroup", "channel"]:
                        c_id = str(chat.get("id"))
                        c_title = chat.get("title") or "Telegram Group"
                        try:
                            groups_file = os.path.join(self.data_dir, "known_telegram_groups.json")
                            kg = {}
                            if os.path.exists(groups_file):
                                with open(groups_file, "r", encoding="utf-8") as gf:
                                    kg = json.load(gf)

                            # If this group was upgraded to supergroup (-100...), remove the old basic group ID
                            to_remove = [k for k, v in kg.items() if k != "latest_group_id" and isinstance(v, dict) and v.get("title") == c_title and k != c_id and c_id.startswith("-100")]
                            for rk in to_remove:
                                del kg[rk]

                            kg[c_id] = {"id": c_id, "title": c_title, "updated_at": datetime.datetime.now().isoformat()}
                            kg["latest_group_id"] = c_id
                            with open(groups_file, "w", encoding="utf-8") as gf:
                                json.dump(kg, gf, indent=2, ensure_ascii=False)
                            print(f"[TelegramBot] ✅ Detected Group: '{c_title}' (ID: {c_id})")
                        except Exception as eg:
                            pass

                    msg = upd.get("message") or upd.get("channel_post")
                    if not msg:
                        continue

                    # Restrict incoming message processing to Private Chat ONLY.
                    # Groups are ONLY for sending OUT dispatches from AutoRent, NEVER for ingesting customer data.
                    chat_obj = msg.get("chat") or {}
                    c_type = str(chat_obj.get("type", "")).lower()
                    c_id_str = str(chat_obj.get("id", ""))
                    if c_type in ["group", "supergroup", "channel"] or c_id_str.startswith("-"):
                        continue

                    # Record incoming text or caption and photo for AutoRent integration (Private chat only)
                    self._record_incoming_message(msg, upd.get("update_id"), token)

                    mg_id = msg.get("media_group_id")
                    photos = msg.get("photo")
                    document = msg.get("document")
                    text_content = (msg.get("text") or "").strip()

                    if (photos and len(photos) > 0) or (document and document.get("mime_type", "").startswith("image/")):
                        if mg_id:
                            if mg_id not in media_groups:
                                media_groups[mg_id] = []
                            media_groups[mg_id].append(msg)
                        else:
                            single_photos.append(msg)
                    elif text_content and not text_content.startswith('/'):
                        text_msgs.append(msg)

                # If any media group has only 1 message so far, wait a brief moment and fetch remaining album parts
                if any(len(v) == 1 for v in media_groups.values()):
                    time.sleep(1.2)
                    try:
                        next_url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=2&offset={self.last_update_id + 1}"
                        next_req = urllib.request.Request(next_url)
                        with urllib.request.urlopen(next_req, timeout=5) as next_resp:
                            next_data = json.loads(next_resp.read().decode('utf-8'))
                            if next_data.get("ok"):
                                for next_upd in next_data.get("result", []):
                                    self.last_update_id = max(self.last_update_id, next_upd["update_id"])
                                    n_msg = next_upd.get("message") or next_upd.get("channel_post")
                                    if n_msg:
                                        n_chat = n_msg.get("chat") or {}
                                        if str(n_chat.get("type", "")).lower() in ["group", "supergroup", "channel"] or str(n_chat.get("id", "")).startswith("-"):
                                            continue
                                        # Record incoming message for subsequent album photos!
                                        self._record_incoming_message(n_msg, next_upd.get("update_id"), token)
                                        n_mg_id = n_msg.get("media_group_id")
                                        n_photos = n_msg.get("photo")
                                        n_document = n_msg.get("document")
                                        if (n_photos and len(n_photos) > 0) or (n_document and n_document.get("mime_type", "").startswith("image/")):
                                            if n_mg_id:
                                                if n_mg_id not in media_groups:
                                                    media_groups[n_mg_id] = []
                                                media_groups[n_mg_id].append(n_msg)
                                            else:
                                                single_photos.append(n_msg)
                    except Exception:
                        pass

                # Auto-issuing invoices via Telegram Bot is permanently disabled per user request:
                # ("មិនបាច់អោយប៊តចេញវិក័យ្យប័ត្រទេ")
                if not getattr(self, 'auto_issue_invoice', False):
                    continue

                # Process Media Group Albums (Multiple photos sent together as 1 Group)
                for mg_id, msg_list in media_groups.items():
                    chat_id = msg_list[0]["chat"]["id"]
                    if len(msg_list) > 1:
                        self._process_telegram_photo_group(token, chat_id, msg_list)
                    else:
                        file_id = (msg_list[0].get("photo") or [{}])[-1].get("file_id") or (msg_list[0].get("document") or {}).get("file_id")
                        if file_id:
                            self._process_telegram_photo(token, chat_id, file_id, msg_list[0])

                # Process Single / Consecutive Photos
                if len(single_photos) > 1:
                    # Group multiple single photos sent together into 1 Group Invoice
                    chat_id = single_photos[0]["chat"]["id"]
                    self._process_telegram_photo_group(token, chat_id, single_photos)
                elif len(single_photos) == 1:
                    msg = single_photos[0]
                    chat_id = msg["chat"]["id"]
                    photos = msg.get("photo")
                    document = msg.get("document")
                    file_id = photos[-1]["file_id"] if photos else document.get("file_id")
                    if file_id:
                        self._process_telegram_photo(token, chat_id, file_id, msg)

                # Process Text Messages
                for msg in text_msgs:
                    chat_id = msg["chat"]["id"]
                    text_content = (msg.get("text") or "").strip()
                    self._process_telegram_text(token, chat_id, text_content, msg)

            except Exception as e:
                time.sleep(3)

    def _process_telegram_photo_group(self, token, chat_id, msg_list):
        """
        Processes multiple passport photos sent together (e.g. 5, 10, or more)
        and combines them into 1 Single Group Invoice Record with 1 Group Receipt image.
        """
        if not getattr(self, 'auto_issue_invoice', False) or str(chat_id).startswith("-"):
            return

        if not msg_list:
            return

        # Deduplication check by media_group_id or message_ids
        keys = []
        for m in msg_list:
            if m.get("media_group_id"):
                keys.append(f"mg_{m.get('media_group_id')}")
            if m.get("message_id"):
                keys.append(f"msg_{chat_id}_{m.get('message_id')}")

        if any(self._is_update_processed(k) for k in keys):
            print(f"[TelegramBotListener] Duplicate photo group detected. Skipping.")
            return

        self._mark_update_processed(keys)

        inv_no = get_next_sequential_invoice_no(self.data_dir)
        today_str = datetime.datetime.now().strftime("%d-%m-%Y")
        sender_title = msg_list[0].get("from", {}).get("first_name", "Telegram Booking")

        members = []
        items = []
        total_usd = 0.0

        for idx, msg in enumerate(msg_list, 1):
            try:
                photos = msg.get("photo")
                document = msg.get("document")
                file_id = None
                if photos and len(photos) > 0:
                    file_id = photos[-1]["file_id"]
                elif document and document.get("mime_type", "").startswith("image/"):
                    file_id = document.get("file_id")

                if not file_id:
                    continue

                get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                req = urllib.request.Request(get_file_url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    f_data = json.loads(resp.read().decode('utf-8'))

                if not f_data.get("ok"):
                    continue

                file_path = f_data["result"]["file_path"]
                dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                with urllib.request.urlopen(dl_url, timeout=15) as resp:
                    img_bytes = resp.read()

                pil_img = Image.open(io.BytesIO(img_bytes))

                if self.ocr_engine:
                    extracted, _ = self.ocr_engine.process_image(pil_img)
                else:
                    extracted = {"full_english_name": f"PASSPORT CUSTOMER {idx}", "passport_no": "", "nationality": "THAI"}

                caption_name = (msg.get("caption") or "").strip()
                if caption_name:
                    name = caption_name.upper()
                else:
                    name = clean_person_name(extracted.get("full_english_name", "")).strip() or f"PASSPORT CUSTOMER {idx}"

                if name:
                    name = re.sub(r'\s+', ' ', name).strip()

                passport_no = extracted.get("passport_no", "").strip()
                nationality = extracted.get("nationality", "THAI").strip() or "THAI"
                dob = extracted.get("dob", "").strip()
                sex = extracted.get("sex", "").strip()

                row_usd = 200.0
                total_usd += row_usd

                members.append({
                    "full_english_name": name,
                    "english_name": name,
                    "passport_no": passport_no,
                    "nationality": nationality,
                    "dob": dob,
                    "sex": sex,
                    "vip": 100.0,
                    "clearance_fee": 50.0,
                    "car_fee": 50.0,
                    "work_permit": 0.0,
                    "visa_fee": 0.0,
                    "e_visa": 0.0,
                    "usd": row_usd,
                    "qty": "1"
                })

                items.append({
                    "no": idx,
                    "name": name,
                    "description": name,
                    "passport_no": passport_no,
                    "nationality": nationality,
                    "qty": "1",
                    "vip": "$100",
                    "clearance_fee": "$50",
                    "car_fee": "$50",
                    "usd": row_usd
                })
            except Exception as e_item:
                print(f"[TelegramBotListener] Error processing item #{idx}: {e_item}")

        if not members:
            return

        pax_count = len(members)
        cust_display = format_group_customer_names(members)
        rate = 34.0
        tot_baht = total_usd * rate

        group_record = {
            "id": str(int(time.time() * 1000)),
            "date_saved": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "receipt_no": inv_no,
            "customer_name": f"{sender_title} ({pax_count} Pax)",
            "payment_status": "UNPAID",
            "customer": {
                "full_english_name": f"GROUP: {sender_title} ({pax_count} Pax)",
                "nationality": "GROUP",
                "sex": f"{pax_count} Pax",
                "receipt_no": inv_no
            },
            "group_info": {
                "group_name": sender_title,
                "sender_name": sender_title,
                "customer_name": cust_display,
                "agency_company": "Golden Mekong VIP Service",
                "travel_date": today_str,
                "receipt_no": inv_no
            },
            "members": members,
            "group_data": {
                "customer_name": sender_title,
                "sender_name": sender_title,
                "group_customer_name": cust_display,
                "agency_company": "Golden Mekong VIP Service",
                "date_str": today_str,
                "receipt_no": inv_no,
                "exchange_rate": rate,
                "items": items,
                "totals": {
                    "usd": total_usd,
                    "baht": tot_baht
                }
            },
            "totals": {
                "usd": total_usd,
                "baht": tot_baht
            }
        }

        scan_record = {
            "id": str(int(time.time() * 1000)),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "receipt_no": inv_no,
            "customer_name": cust_display,
            "full_english_name": cust_display,
            "passport_no": f"{pax_count} Passports Scanned",
            "nationality": "GROUP",
            "chat_id": chat_id,
            "sender": sender_title,
            "members": members
        }

        with self.lock:
            self.recent_scans.append(scan_record)

        self._save_customer_to_file(group_record)

        try:
            temp_receipt_png = os.path.join(self.data_dir, f"temp_tg_receipt_{int(time.time())}.png")
            ReceiptGenerator.export_group_image(group_record["group_data"], temp_receipt_png)

            caption_text = (
                f"🧾 <b>វិក្កយបត្រក្រុមផ្លូវការ (OFFICIAL GROUP INVOICE)</b>\n\n"
                f"• <b>លេខវិក្កយបត្រ (Invoice No):</b> {inv_no}\n"
                f"• <b>អ្នកកក់ (Group Sender):</b> {sender_title}\n"
                f"• <b>ចំនួនសមាជិក (Total Pax):</b> {pax_count} នាក់\n"
                f"• <b>តំណាងក្រុម:</b> {cust_display}\n"
                f"💰 <b>សរុបទឹកប្រាក់ ({pax_count} នាក់):</b> ${total_usd:,.2f} (฿ {tot_baht:,.0f})\n\n"
                f"📌 <b>CMP Golden Mekong Commercial Service</b>"
            )

            send_telegram_photo_bot(token, chat_id, temp_receipt_png, caption=caption_text)
            if os.path.exists(temp_receipt_png):
                try: os.remove(temp_receipt_png)
                except Exception: pass
        except Exception as e_gen:
            print(f"[TelegramBotListener] Error generating group receipt: {e_gen}")

    def _process_telegram_text(self, token, chat_id, text_name, msg):
        if not getattr(self, 'auto_issue_invoice', False) or str(chat_id).startswith("-"):
            return

        try:
            raw_text = text_name.strip()
            if not raw_text:
                return

            msg_id = msg.get("message_id")
            key = f"msg_{chat_id}_{msg_id}" if msg_id else None
            if key and self._is_update_processed(key):
                print(f"[TelegramBotListener] Duplicate text update detected. Skipping.")
                return
            if key:
                self._mark_update_processed([key])

            clean_raw = raw_text.strip()
            # Intelligent name splitting by numbered items (1. 2. 3.), newlines, or commas
            if re.search(r'\b\d+[\.\-\)]\s*', clean_raw):
                parts = re.split(r'\b\d+[\.\-\)]\s*', clean_raw)
                extracted_names = [p.strip().upper() for p in parts if p.strip()]
            elif '\n' in clean_raw:
                extracted_names = [line.strip().upper() for line in clean_raw.split('\n') if line.strip()]
            elif ',' in clean_raw or ';' in clean_raw:
                extracted_names = [p.strip().upper() for p in re.split(r'[,;]+', clean_raw) if p.strip()]
            else:
                extracted_names = [clean_raw.upper()]

            names = []
            for n in extracted_names:
                cleaned_n = re.sub(r'^\d+[\.\-\)\:\s]+', '', n).strip()
                if cleaned_n:
                    names.append(cleaned_n)

            if not names:
                return

            inv_no = get_next_sequential_invoice_no(self.data_dir)
            today_str = datetime.datetime.now().strftime("%d-%m-%Y")
            sender_title = msg.get("from", {}).get("first_name", "Telegram Booking")

            if len(names) > 1:
                # Multiple names sent in 1 text message (Group Invoice)
                members = []
                items = []
                total_usd = 0.0

                for idx, n in enumerate(names, 1):
                    row_usd = 200.0
                    total_usd += row_usd
                    members.append({
                        "full_english_name": n,
                        "english_name": n,
                        "passport_no": "",
                        "nationality": "THAI",
                        "vip": 100.0,
                        "clearance_fee": 50.0,
                        "car_fee": 50.0,
                        "usd": row_usd,
                        "qty": "1"
                    })
                    items.append({
                        "no": idx,
                        "name": n,
                        "description": n,
                        "qty": "1",
                        "vip": "$100",
                        "clearance_fee": "$50",
                        "car_fee": "$50",
                        "usd": row_usd
                    })

                pax_count = len(members)
                cust_display = format_group_customer_names(members)
                rate = 34.0
                tot_baht = total_usd * rate

                group_record = {
                    "id": str(int(time.time() * 1000)),
                    "date_saved": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "receipt_no": inv_no,
                    "service_category": "car",
                    "customer_name": f"{sender_title} ({pax_count} Pax)",
                    "payment_status": "UNPAID",
                    "customer": {
                        "full_english_name": f"GROUP: {sender_title} ({pax_count} Pax)",
                        "nationality": "GROUP",
                        "sex": f"{pax_count} Pax",
                        "receipt_no": inv_no
                    },
                    "group_info": {
                        "group_name": sender_title,
                        "sender_name": sender_title,
                        "customer_name": cust_display,
                        "agency_company": "Golden Mekong VIP Service",
                        "travel_date": today_str,
                        "receipt_no": inv_no,
                        "service_category": "car"
                    },
                    "members": members,
                    "group_data": {
                        "customer_name": sender_title,
                        "sender_name": sender_title,
                        "group_customer_name": cust_display,
                        "agency_company": "Golden Mekong VIP Service",
                        "date_str": today_str,
                        "receipt_no": inv_no,
                        "exchange_rate": rate,
                        "service_category": "car",
                        "items": items,
                        "totals": {"usd": total_usd, "baht": tot_baht}
                    },
                    "totals": {"usd": total_usd, "baht": tot_baht}
                }

                scan_record = {
                    "id": str(int(time.time() * 1000)),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "receipt_no": inv_no,
                    "customer_name": cust_display,
                    "full_english_name": cust_display,
                    "passport_no": f"{pax_count} Names Provided",
                    "nationality": "GROUP",
                    "chat_id": chat_id,
                    "sender": sender_title,
                    "members": members
                }

                with self.lock:
                    self.recent_scans.append(scan_record)

                self._save_customer_to_file(group_record)

                temp_receipt_png = os.path.join(self.data_dir, f"temp_tg_receipt_{int(time.time())}.png")
                ReceiptGenerator.export_group_image(group_record["group_data"], temp_receipt_png)

                caption_text = (
                    f"🧾 <b>វិក្កយបត្រក្រុមផ្លូវការ (OFFICIAL GROUP INVOICE)</b>\n\n"
                    f"• <b>លេខវិក្កយបត្រ (Invoice No):</b> {inv_no}\n"
                    f"• <b>អ្នកកក់ (Group Sender):</b> {sender_title}\n"
                    f"• <b>ចំនួនសមាជិក (Total Pax):</b> {pax_count} នាក់\n"
                    f"• <b>តំណាងក្រុម:</b> {cust_display}\n"
                    f"💰 <b>សរុបទឹកប្រាក់ ({pax_count} នាក់):</b> ${total_usd:,.2f} (฿ {tot_baht:,.0f})\n\n"
                    f"📌 <b>CMP Golden Mekong Commercial Service</b>"
                )

                send_telegram_photo_bot(token, chat_id, temp_receipt_png, caption=caption_text)
                if os.path.exists(temp_receipt_png):
                    try: os.remove(temp_receipt_png)
                    except Exception: pass
                return

            name = names[0]
            today_str = datetime.datetime.now().strftime("%d-%m-%Y")
            sender_title = msg.get("from", {}).get("first_name", "Telegram Booking")

            scan_record = {
                "id": str(int(time.time() * 1000)),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "receipt_no": inv_no,
                "customer_name": name,
                "full_english_name": name,
                "passport_no": "",
                "nationality": "THAI",
                "dob": "",
                "sex": "",
                "chat_id": chat_id,
                "sender": sender_title
            }

            with self.lock:
                self.recent_scans.append(scan_record)
                if len(self.recent_scans) > 50:
                    self.recent_scans.pop(0)

            self._save_customer_to_file({
                "receipt_no": inv_no,
                "customer_name": name,
                "full_english_name": name,
                "passport_no": "",
                "nationality": "THAI",
                "updated_at": scan_record["timestamp"]
            })

            receipt_data = {
                "receipt_no": inv_no,
                "customer_name": sender_title,
                "agency_company": "Golden Mekong VIP Service",
                "date_str": today_str,
                "exchange_rate": 34.0,
                "totals": {"usd": 200.0, "baht": 6800.0},
                "items": [
                    {
                        "no": 1,
                        "name": name,
                        "passport_no": "",
                        "nationality": "THAI",
                        "vip_fee": 100.0,
                        "clearance_fee": 50.0,
                        "work_permit": 0,
                        "car_fee": 50.0,
                        "visa_fee": 0,
                        "e_visa": 0,
                        "total_usd": 200.0,
                        "total_baht": 6800.0
                    }
                ]
            }

            temp_receipt_png = os.path.join(self.data_dir, f"temp_tg_receipt_{int(time.time())}.png")
            ReceiptGenerator.export_group_image(receipt_data, temp_receipt_png)

            caption_text = (
                f"🧾 <b>វិក្កយបត្រផ្លូវការ (OFFICIAL INVOICE RECEIPT)</b>\n\n"
                f"• <b>លេខវិក្កយបត្រ (Invoice No):</b> {inv_no}\n"
                f"• <b>ឈ្មោះអតិថិជន:</b> {name}\n"
                f"• <b>សេវាកម្ម:</b> កក់ឡាន ($50) + វីអាយភី ($100) + ថ្លៃក្លៀផ្លូវ ($50)\n"
                f"💰 <b>សរុបទឹកប្រាក់:</b> $200.00 (฿ 6,800)\n\n"
                f"📌 <b>CMP Golden Mekong Commercial Service</b>"
            )

            send_telegram_photo_bot(token, chat_id, temp_receipt_png, caption=caption_text)
            if os.path.exists(temp_receipt_png):
                try: os.remove(temp_receipt_png)
                except Exception: pass
        except Exception as e:
            print(f"[TelegramBotListener] Error processing text name: {e}")

    def _process_telegram_photo(self, token, chat_id, file_id, msg):
        if not getattr(self, 'auto_issue_invoice', False) or str(chat_id).startswith("-"):
            return

        try:
            msg_id = msg.get("message_id")
            key = f"msg_{chat_id}_{msg_id}" if msg_id else f"file_{file_id}"
            if self._is_update_processed(key):
                print(f"[TelegramBotListener] Duplicate single photo update detected. Skipping.")
                return
            self._mark_update_processed([key])

            # 1. Get file path from Telegram
            get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
            req = urllib.request.Request(get_file_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                f_data = json.loads(resp.read().decode('utf-8'))

            if not f_data.get("ok"):
                return

            file_path = f_data["result"]["file_path"]
            dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

            # 2. Download photo bytes
            with urllib.request.urlopen(dl_url, timeout=15) as resp:
                img_bytes = resp.read()

            tg_img_dir = os.path.join(self.data_dir, "telegram_images")
            os.makedirs(tg_img_dir, exist_ok=True)
            clean_fid = re.sub(r'[^a-zA-Z0-9]', '', str(file_id))[:10]
            local_photo_name = f"tg_photo_{int(time.time())}_{clean_fid}.jpg"
            local_photo_path = os.path.join(tg_img_dir, local_photo_name)
            with open(local_photo_path, "wb") as f_out:
                f_out.write(img_bytes)
            saved_photo_url = f"/telegram_images/{local_photo_name}"

            pil_img = Image.open(io.BytesIO(img_bytes))

            # 3. Run OCR
            if self.ocr_engine:
                extracted, _ = self.ocr_engine.process_image(pil_img)
            else:
                extracted = {"full_english_name": "PASSPORT CUSTOMER", "passport_no": "", "nationality": "THAI"}

            # Check if user provided a text caption along with the photo
            caption_name = (msg.get("caption") or "").strip()
            if caption_name:
                name = caption_name.upper()
            else:
                name = clean_person_name(extracted.get("full_english_name", "")).strip()
            passport_no = extracted.get("passport_no", "").strip()
            nationality = extracted.get("nationality", "THAI").strip()
            dob = extracted.get("dob", "").strip()
            sex = extracted.get("sex", "").strip()

            if name or passport_no:
                inv_no = get_next_sequential_invoice_no(self.data_dir)
                from_usr = msg.get("from", {})
                f_name = from_usr.get("first_name", "")
                l_name = from_usr.get("last_name", "")
                u_name = from_usr.get("username", "")
                sender_title = f"{f_name} {l_name}".strip() or u_name or "Telegram User"
                today_str = datetime.datetime.now().strftime("%d-%m-%Y")

                scan_record = {
                    "id": str(int(time.time() * 1000)),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "receipt_no": inv_no,
                    "customer_name": name or "PASSPORT CUSTOMER",
                    "full_english_name": name or "PASSPORT CUSTOMER",
                    "passport_no": passport_no,
                    "nationality": nationality or "THAI",
                    "dob": dob,
                    "sex": sex,
                    "chat_id": chat_id,
                    "sender": sender_title,
                    "sender_name": sender_title
                }

                with self.lock:
                    self.recent_scans.append(scan_record)
                    if len(self.recent_scans) > 50:
                        self.recent_scans.pop(0)

                # Save customer to database
                self._save_customer_to_file({
                    "receipt_no": inv_no,
                    "service_category": "car",
                    "sender": sender_title,
                    "sender_name": sender_title,
                    "customer_name": name,
                    "full_english_name": name,
                    "passport_no": passport_no,
                    "nationality": nationality,
                    "dob": dob,
                    "sex": sex,
                    "photo": saved_photo_url,
                    "photo_data": saved_photo_url,
                    "images": [{
                        "id": f"IMG-TG-{int(time.time()*1000)}",
                        "name": local_photo_name,
                        "category": "ប៉ាស្ព័រ",
                        "url": saved_photo_url,
                        "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    }],
                    "updated_at": scan_record["timestamp"],
                    "group_info": {
                        "group_name": sender_title,
                        "sender_name": sender_title,
                        "customer_name": name,
                        "agency_company": "Golden Mekong VIP Service",
                        "travel_date": today_str,
                        "receipt_no": inv_no,
                        "service_category": "car"
                    },
                    "group_data": {
                        "customer_name": sender_title,
                        "sender_name": sender_title,
                        "group_customer_name": name,
                        "agency_company": "Golden Mekong VIP Service",
                        "date_str": today_str,
                        "receipt_no": inv_no,
                        "exchange_rate": 34.0,
                        "service_category": "car",
                        "items": [
                            {
                                "no": 1,
                                "name": name or "PASSPORT CUSTOMER",
                                "description": name or "PASSPORT CUSTOMER",
                                "passport_no": passport_no,
                                "nationality": nationality or "THAI",
                                "qty": "1",
                                "vip": "$100",
                                "clearance_fee": "$50",
                                "car_fee": "$50",
                                "usd": 200.0
                            }
                        ],
                        "totals": {"usd": 200.0, "baht": 6800.0}
                    }
                })

                # Auto Generate Official Invoice Receipt Image
                try:
                    receipt_data = {
                        "receipt_no": inv_no,
                        "customer_name": sender_title,
                        "agency_company": "Golden Mekong VIP Service",
                        "date_str": today_str,
                        "exchange_rate": 34.0,
                        "totals": {"usd": 200.0, "baht": 6800.0},
                        "items": [
                            {
                                "no": 1,
                                "name": name or "PASSPORT CUSTOMER",
                                "passport_no": passport_no,
                                "nationality": nationality or "THAI",
                                "vip_fee": 100.0,
                                "clearance_fee": 50.0,
                                "total_usd": 200.0,
                                "total_baht": 6800.0
                            }
                        ]
                    }

                    temp_receipt_png = os.path.join(self.data_dir, f"temp_tg_receipt_{int(time.time())}.png")
                    ReceiptGenerator.export_group_image(receipt_data, temp_receipt_png)

                    caption_text = (
                        f"🧾 <b>វិក្កយបត្រផ្លូវការ (OFFICIAL INVOICE RECEIPT)</b>\n\n"
                        f"• <b>លេខវិក្កយបត្រ (Invoice No):</b> {inv_no}\n"
                        f"• <b>ឈ្មោះអតិថិជន:</b> {name}\n"
                        f"• <b>លេខប៉ាស្ព័រ:</b> {passport_no or 'N/A'}\n"
                        f"• <b>សញ្ជាតិ:</b> {nationality}\n"
                        f"• <b>សេវាកម្ម:</b> កក់ឡាន ($50) + វីអាយភី ($100) + ថ្លៃក្លៀផ្លូវ ($50)\n"
                        f"💰 <b>សរុបទឹកប្រាក់:</b> $200.00 (฿ 6,800)\n\n"
                        f"📌 <b>CMP Golden Mekong Commercial Service</b>"
                    )

                    res_photo = send_telegram_photo_bot(token, chat_id, temp_receipt_png, caption=caption_text)
                    if os.path.exists(temp_receipt_png):
                        try: os.remove(temp_receipt_png)
                        except Exception: pass
                except Exception as e_gen:
                    print(f"[TelegramBotListener] Error generating auto-receipt image: {e_gen}")
                    reply_text = (
                        f"✅ <b>AI OCR ស្កេនប៉ាស្ព័រជោគជ័យ!</b>\n\n"
                        f"👤 <b>ឈ្មោះ:</b> {name}\n"
                        f"🛂 <b>លេខប៉ាស្ព័រ:</b> {passport_no or 'N/A'}\n"
                        f"🏳️ <b>សញ្ជាតិ:</b> {nationality}\n"
                        f"🎂 <b>ថ្ងៃខែឆ្នាំកំណើត:</b> {dob or 'N/A'}\n\n"
                        f"🚀 <i>ទិន្នន័យត្រូវបច្ចុប្បន្នភាពលើ Web App Imvoi រួចរាល់!</i>"
                    )
                    send_telegram_text_bot(token, chat_id, reply_text)
            else:
                send_telegram_text_bot(token, chat_id, "⚠️ មិនអាចអានឈ្មោះពីប៉ាស្ព័របានទេ! សូមផ្ញើរូបភាពច្បាស់ជាងនេះ។")

        except Exception as e:
            print(f"[TelegramBotListener] Error processing photo: {e}")


# Global listener instance
telegram_bot_listener = TelegramBotListener()



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
