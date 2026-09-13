"""
CMP Golden Mekong Commercial Service - Instant Web Application Server
Runs zero-config Web Server on http://localhost:8000 with Multipart & Base64 AI OCR Engine.
"""

import socket
import http.server
import socketserver
import json
import urllib.parse
import urllib.request
import os
import sys
import webbrowser
import base64
import io
import re
import datetime
import uuid
import threading
import time
import traceback
from PIL import Image

try:
    import supabase_db
except Exception:
    supabase_db = None

class SafeThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except Exception:
                pass
        super().server_bind()

# Ensure UTF-8 output on Windows consoles
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Redirect stdout/stderr if running in windowless mode (pythonw)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    from ocr_engine import DocumentAIEngine, clean_person_name
    ocr_engine = DocumentAIEngine()
    print("[OK] AI OCR Engine loaded successfully!")
except Exception as e:
    ocr_engine = None
    def clean_person_name(s): return s
    print("Notice: OCR Engine fallback:", e)

def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace('$', '').replace(',', '')
        return float(s) if s else default
    except Exception:
        return default

def safe_int(val, default=0):
    if val is None:
        return default
    try:
        if isinstance(val, int):
            return val
        s = re.sub(r'[^0-9]', '', str(val))
        return int(s) if s else default
    except Exception:
        return default


try:
    from telegram_utils import (
        get_telegram_config, save_telegram_config, send_telegram_photo_bot,
        send_telegram_text_bot, get_telegram_bot_info, telegram_bot_listener,
        launch_telegram_desktop, get_telegram_exe_path, _handle_chat_migration
    )
except Exception as e:
    def get_telegram_config(): return {"bot_token": "8884318593:AAEipEVki9o1YFL0_8IYoUeSn3Xif4dlVOk", "chat_id": "8985821312"}
    def save_telegram_config(b, c): pass
    def _handle_chat_migration(old_c, new_c): pass
    def send_telegram_photo_bot(b, c, p, caption=""): return {"ok": False, "description": "telegram_utils unavailable"}
    def send_telegram_text_bot(b, c, text, parse_mode=None): return {"ok": False, "description": "telegram_utils unavailable"}
    def get_telegram_bot_info(t): return {"ok": False}
    def launch_telegram_desktop(): return False
    def get_telegram_exe_path(): return None
    telegram_bot_listener = None


PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', '/var/data' if os.path.exists('/var/data') else BASE_DIR)
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        DATA_DIR = BASE_DIR

SAVED_CUSTOMERS_FILE = os.path.join(DATA_DIR, 'saved_customers.json')
INVOICE_COUNTER_FILE = os.path.join(DATA_DIR, 'invoice_counter.json')
SAVED_BOOKINGS_FILE = os.path.join(DATA_DIR, 'saved_bookings.json')
AUTORENT_CUSTOMERS_FILE = os.path.join(DATA_DIR, 'autorent_customers.json')
WEB_DIR = BASE_DIR

# ===========================================================================
# STARTUP AUTO-RESTORE: Restore Invoices & Bookings from Supabase Cloud / Backups
# ===========================================================================
def _startup_restore_invoices():
    """Auto-restore customer invoice data from local files, backups, or Supabase Cloud."""
    try:
        # 1. Check if main local data file is intact first (Fastest!)
        main_ok = False
        if os.path.exists(SAVED_CUSTOMERS_FILE):
            try:
                with open(SAVED_CUSTOMERS_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if isinstance(existing, list) and len(existing) > 0:
                    main_ok = True
                    print(f"[DataRestore] Main invoice file OK: {len(existing)} records found.")
            except Exception:
                pass

        if main_ok:
            if supabase_db and supabase_db.is_configured():
                try:
                    threading.Thread(target=supabase_db.upsert_invoices, args=(existing,), daemon=True).start()
                except Exception:
                    pass
            return  # Data is intact, nothing to do

        print("[DataRestore] Main invoice data file missing or empty. Searching backups...")

        # 2. Candidate backup paths in priority order
        backup_candidates = [
            os.path.join(DATA_DIR, 'backups', 'saved_customers_latest_vault.json'),
            os.path.join(BASE_DIR, 'backups', 'saved_customers_latest_vault.json'),
            os.path.join(BASE_DIR, 'saved_customers_live_backup.json'),
            os.path.join(BASE_DIR, 'saved_customers.json'),
        ]

        # Also scan backups/ folder for any timestamped auto-backup files
        for scan_dir in [os.path.join(DATA_DIR, 'backups'), os.path.join(BASE_DIR, 'backups')]:
            if os.path.isdir(scan_dir):
                try:
                    bak_files = sorted(
                        [os.path.join(scan_dir, f) for f in os.listdir(scan_dir)
                         if f.endswith('.json') and 'customers' in f.lower()],
                        key=os.path.getmtime, reverse=True
                    )
                    backup_candidates.extend(bak_files)
                except Exception:
                    pass

        best_data = None
        best_path = None
        best_count = 0

        for bak_path in backup_candidates:
            if not os.path.exists(bak_path):
                continue
            try:
                if os.path.abspath(bak_path) == os.path.abspath(SAVED_CUSTOMERS_FILE):
                    continue
            except Exception:
                pass
            try:
                with open(bak_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) > best_count:
                    best_data = data
                    best_count = len(data)
                    best_path = bak_path
            except Exception as e:
                print(f"[DataRestore] Could not read backup {bak_path}: {e}")

        if best_data and best_count > 0:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SAVED_CUSTOMERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(best_data, f, ensure_ascii=False, indent=2)
            print(f"[DataRestore] ✅ Restored {best_count} invoice records from: {best_path}")
            
            if supabase_db and supabase_db.is_configured():
                try:
                    threading.Thread(target=supabase_db.upsert_invoices, args=(best_data,), daemon=True).start()
                except Exception:
                    pass
            return

        # 3. Fallback to Supabase Cloud DB only if local files and backups are missing
        if supabase_db and supabase_db.is_configured():
            try:
                print("[Supabase] Querying Supabase Cloud Database for invoices on startup...")
                cloud_recs = supabase_db.fetch_all_invoices()
                if cloud_recs and len(cloud_recs) > 0:
                    os.makedirs(DATA_DIR, exist_ok=True)
                    with open(SAVED_CUSTOMERS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(cloud_recs, f, ensure_ascii=False, indent=2)
                    print(f"[Supabase] ✅ Successfully restored {len(cloud_recs)} invoice records from Cloud DB!")
                    
                    cloud_counters = supabase_db.fetch_counters()
                    if cloud_counters and isinstance(cloud_counters, dict):
                        with open(INVOICE_COUNTER_FILE, 'w', encoding='utf-8') as fc:
                            json.dump(cloud_counters, fc, ensure_ascii=False, indent=2)
                    return
                else:
                    print("[Supabase] Cloud database is empty for invoices.")
            except Exception as se:
                print(f"[Supabase] Invoice startup load warning: {se}")

        print("[DataRestore] No invoice backup found. Starting with empty database.")
    except Exception as e:
        print(f"[DataRestore] Invoice restore error (non-fatal): {e}")

def _startup_restore_bookings():
    """Auto-restore car rental bookings from local files, backups, or Supabase Cloud."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        # 1. Local file first (Fastest!)
        bks_ok = False
        if os.path.exists(SAVED_BOOKINGS_FILE):
            try:
                with open(SAVED_BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                    b = json.load(f)
                if isinstance(b, list) and len(b) > 0:
                    bks_ok = True
                    print(f"[DataRestore] Bookings file OK: {len(b)} bookings found.")
            except Exception:
                pass

        # 2. Local backup fallback
        if not bks_ok:
            for cand in [
                os.path.join(BASE_DIR, 'saved_bookings.json'),
                os.path.join(DATA_DIR, 'backups', 'latest_data', 'saved_bookings.json'),
                os.path.join(BASE_DIR, 'backups', 'latest_data', 'saved_bookings.json'),
            ]:
                if os.path.exists(cand):
                    try:
                        with open(cand, 'r', encoding='utf-8') as f:
                            cand_bks = json.load(f)
                        if isinstance(cand_bks, list) and len(cand_bks) > 0:
                            with open(SAVED_BOOKINGS_FILE, 'w', encoding='utf-8') as f:
                                json.dump(cand_bks, f, ensure_ascii=False, indent=2)
                            print(f"[DataRestore] ✅ Restored {len(cand_bks)} bookings from backup: {cand}")
                            bks_ok = True
                            break
                    except Exception:
                        pass

        # 3. Supabase Cloud DB fallback if neither local nor backup found
        if not bks_ok and supabase_db and supabase_db.is_configured():
            try:
                print("[Supabase] Querying Supabase Cloud for Bookings on startup...")
                cloud_bks = supabase_db.fetch_bookings()
                if cloud_bks and isinstance(cloud_bks, list) and len(cloud_bks) > 0:
                    with open(SAVED_BOOKINGS_FILE, 'w', encoding='utf-8') as fb:
                        json.dump(cloud_bks, fb, ensure_ascii=False, indent=2)
                    print(f"[Supabase] ✅ Successfully restored {len(cloud_bks)} bookings from Cloud DB!")
                    bks_ok = True
            except Exception as se:
                print(f"[Supabase] Booking startup load warning: {se}")

        # 4. Seed Supabase Cloud DB in background if local has bookings
        if bks_ok and supabase_db and supabase_db.is_configured():
            try:
                with open(SAVED_BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                    to_seed = json.load(f)
                if to_seed:
                    threading.Thread(target=supabase_db.save_bookings, args=(to_seed,), daemon=True).start()
            except Exception:
                pass
    except Exception as ex:
        print(f"[DataRestore] Booking restore non-fatal error: {ex}")

def _startup_restore_if_needed():
    """Auto-restore customer invoices, counters, and car bookings on server startup."""
    _startup_restore_invoices()
    _startup_restore_bookings()

_startup_restore_if_needed()

def load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    for attempt in range(4):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            time.sleep(0.08)
    return default

def cluster_telegram_messages_by_time(msgs, time_window_seconds=240):
    """Groups telegram messages sent around the same time (same conversation/batch) by the same sender into a single message card."""
    if not msgs or not isinstance(msgs, list):
        return msgs
    
    clustered = []
    for m in msgs:
        sender = (m.get('sender') or 'Telegram User').strip()
        ts = m.get('timestamp') or 0
        mg_id = m.get('media_group_id')
        m_imgs = m.get('images') or []
        m_text = (m.get('text') or '').strip()

        # Try to find an existing cluster within the time window for the same sender
        matched = None
        for c in clustered:
            c_sender = (c.get('sender') or 'Telegram User').strip()
            c_ts = c.get('timestamp') or 0
            c_mg = c.get('media_group_id')

            same_mg = mg_id and c_mg and mg_id == c_mg
            same_time = (c_sender == sender and abs(ts - c_ts) <= time_window_seconds)

            if same_mg or same_time:
                matched = c
                break

        if matched:
            # 1. Merge images
            if m_imgs:
                if 'images' not in matched or not isinstance(matched['images'], list):
                    matched['images'] = []
                for img in m_imgs:
                    if not any(ex.get('url') == img.get('url') for ex in matched['images']):
                        matched['images'].append(img)

            # 2. Merge texts
            c_text = (matched.get('text') or '').strip()
            is_c_placeholder = not c_text or c_text.startswith('📷 រូបភាព') or c_text.startswith('📘 រូបប៉ាស្ព័រ')
            is_m_placeholder = not m_text or m_text.startswith('📷 រូបភាព') or m_text.startswith('📘 រូបប៉ាស្ព័រ')

            if is_c_placeholder and not is_m_placeholder:
                matched['text'] = m_text
            elif not is_c_placeholder and not is_m_placeholder and m_text != c_text:
                if m_text not in c_text and c_text not in m_text:
                    matched['text'] = f"{c_text}\n\n{m_text}"

            # Keep latest timestamp
            matched['timestamp'] = max(ts, matched.get('timestamp', ts))
            if ts >= matched.get('timestamp', ts):
                matched['date'] = m.get('date', matched.get('date'))
        else:
            # Create a clone so original remains untouched
            clustered.append(dict(m))

    return clustered

def save_json(filepath, data):
    try:
        # Auto-sort bookings: future/upcoming dates at the top, time 00:00 -> 24:00
        if 'saved_bookings' in filepath and isinstance(data, list):
            def _parse_bk_min(t_str):
                if not t_str: return 9999
                parts = re.split(r'[:.]', str(t_str).strip())
                try:
                    return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
                except Exception:
                    return 9999

            def _date_sort_key(d_str):
                if not d_str: return 0
                d = str(d_str).strip()
                m_dmy = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$', d)
                if m_dmy:
                    norm = f"{m_dmy.group(3)}-{int(m_dmy.group(2)):02d}-{int(m_dmy.group(1)):02d}"
                else:
                    norm = d
                digits = re.sub(r'[^0-9]', '', norm)
                # Negative value for descending sort (future/upcoming dates at top)
                return -int(digits) if digits else 0

            data = sorted(data, key=lambda b: (_date_sort_key(b.get('date')), _parse_bk_min(b.get('time')), str(b.get('id', ''))))

        # 1. Thread-safe atomic write using temp file + rename
        tmp_file = f"{filepath}.tmp_{os.getpid()}_{int(time.time()*1000)}"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp_file, filepath)
        except Exception:
            # Fallback for Windows lock contention
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if os.path.exists(tmp_file):
                try: os.remove(tmp_file)
                except Exception: pass
            
        # 2. Supabase Cloud Auto-Sync
        if supabase_db and supabase_db.is_configured():
            if 'saved_customers' in filepath and isinstance(data, list) and len(data) > 0:
                threading.Thread(target=supabase_db.upsert_invoices, args=(data,), daemon=True).start()
            elif 'invoice_counter' in filepath and isinstance(data, dict):
                threading.Thread(target=supabase_db.save_counters, args=(data,), daemon=True).start()
            elif 'saved_bookings' in filepath and isinstance(data, list):
                threading.Thread(target=supabase_db.save_bookings, args=(data,), daemon=True).start()

        # 3. Auto-backup if saving customer database
        if 'saved_customers' in filepath and isinstance(data, list) and len(data) > 0:
            backup_dir = os.path.join(os.path.dirname(filepath), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            # Latest snapshot backup
            latest_bak = os.path.join(backup_dir, 'saved_customers_latest_vault.json')
            with open(latest_bak, 'w', encoding='utf-8') as fb:
                json.dump(data, fb, ensure_ascii=False, indent=2)
            # Hourly/Daily rolling backup
            hour_tag = datetime.datetime.now().strftime('%Y%m%d_%H')
            hourly_bak = os.path.join(backup_dir, f'customers_auto_{hour_tag}.json')
            if not os.path.exists(hourly_bak):
                with open(hourly_bak, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)

            # Cross-backup to BASE_DIR when DATA_DIR differs (e.g. /var/data vs repo dir)
            if os.path.abspath(DATA_DIR) != os.path.abspath(BASE_DIR):
                try:
                    base_live_bak = os.path.join(BASE_DIR, 'saved_customers_live_backup.json')
                    with open(base_live_bak, 'w', encoding='utf-8') as fbase:
                        json.dump(data, fbase, ensure_ascii=False, indent=2)
                    base_bak_dir = os.path.join(BASE_DIR, 'backups')
                    os.makedirs(base_bak_dir, exist_ok=True)
                    base_vault = os.path.join(base_bak_dir, 'saved_customers_latest_vault.json')
                    with open(base_vault, 'w', encoding='utf-8') as fv:
                        json.dump(data, fv, ensure_ascii=False, indent=2)
                except Exception as ce:
                    print(f"[CrossBackup] Warning (non-fatal): {ce}")

        # 4. Auto-backup if saving car bookings database
        if 'saved_bookings' in filepath and isinstance(data, list) and len(data) > 0:
            bk_backup_dir = os.path.join(os.path.dirname(filepath), 'backups')
            os.makedirs(bk_backup_dir, exist_ok=True)
            latest_bk_bak = os.path.join(bk_backup_dir, 'saved_bookings_latest_vault.json')
            with open(latest_bk_bak, 'w', encoding='utf-8') as fb:
                json.dump(data, fb, ensure_ascii=False, indent=2)
            hour_tag = datetime.datetime.now().strftime('%Y%m%d_%H')
            hourly_bk_bak = os.path.join(bk_backup_dir, f'bookings_auto_{hour_tag}.json')
            if not os.path.exists(hourly_bk_bak):
                with open(hourly_bk_bak, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
            if os.path.abspath(DATA_DIR) != os.path.abspath(BASE_DIR):
                try:
                    base_bks_bak = os.path.join(BASE_DIR, 'saved_bookings.json')
                    with open(base_bks_bak, 'w', encoding='utf-8') as fbase:
                        json.dump(data, fbase, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        return True
    except Exception as e:
        print("Save JSON Error:", e)
        return False

def format_display_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return ""
    clean_str = date_str.strip().split(' ')[0]
    parts = re.split(r'[-/.]', clean_str)
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return f"{parts[2].zfill(2)}-{parts[1].zfill(2)}-{parts[0]}"
        elif len(parts[2]) == 4:
            return f"{parts[0].zfill(2)}-{parts[1].zfill(2)}-{parts[2]}"
    return clean_str

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

def get_next_invoice_no(category='car'):
    data = load_json(SAVED_CUSTOMERS_FILE, [])
    counter = load_json(INVOICE_COUNTER_FILE, {
        "last_number": 0, "prefix": "INV ",
        "last_visa_number": 0, "visa_prefix": "VISA ",
        "last_passport_number": 0, "passport_prefix": "INV "
    })
    cat = (category or 'car').lower().strip()
    
    if cat == 'visa':
        prefix = counter.get("visa_prefix", "VISA ")
        nums = []
        for item in data:
            if item.get('service_category') == 'visa' or item.get('group_info', {}).get('service_category') == 'visa':
                r_no = str(item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or '').strip().upper()
                if r_no.startswith('VISA'):
                    num_part = re.sub(r'[^0-9]', '', r_no)
                    if num_part.isdigit():
                        nums.append(int(num_part))
        if nums:
            max_num = max(nums)
        else:
            max_num = int(counter.get("last_visa_number", 0))
        
        # Keep counter file in sync
        if counter.get("last_visa_number") != max_num:
            counter["last_visa_number"] = max_num
            save_json(INVOICE_COUNTER_FILE, counter)
            
        return f"{prefix}{(max_num + 1):05d}"

    elif cat == 'passport':
        prefix = counter.get("passport_prefix", "INV ")
        nums = []
        for item in data:
            if item.get('service_category') == 'passport' or item.get('group_info', {}).get('service_category') == 'passport':
                r_no = str(item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or '').strip().upper()
                num_part = re.sub(r'[^0-9]', '', r_no)
                if num_part.isdigit():
                    nums.append(int(num_part))
        if nums:
            max_num = max(nums)
        else:
            max_num = int(counter.get("last_passport_number", 0))
            
        # Keep counter file in sync
        if counter.get("last_passport_number") != max_num:
            counter["last_passport_number"] = max_num
            save_json(INVOICE_COUNTER_FILE, counter)
            
        return f"{prefix}{(max_num + 1):05d}"

    elif cat in ['quote', 'quotation']:
        prefix = counter.get("quote_prefix", "QT ")
        nums = []
        for item in data:
            if item.get('service_category') in ['quote', 'quotation'] or item.get('group_info', {}).get('service_category') in ['quote', 'quotation']:
                r_no = str(item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or '').strip().upper()
                if r_no.startswith('QT') or r_no.startswith('QUO'):
                    num_part = re.sub(r'[^0-9]', '', r_no)
                    if num_part.isdigit():
                        nums.append(int(num_part))
        if nums:
            max_num = max(nums)
        else:
            max_num = int(counter.get("last_quote_number", 0))
            
        # Keep counter file in sync
        if counter.get("last_quote_number") != max_num:
            counter["last_quote_number"] = max_num
            save_json(INVOICE_COUNTER_FILE, counter)
            
        return f"{prefix}{(max_num + 1):05d}"

    else:
        prefix = counter.get("prefix", "INV ")
        nums = []
        for item in data:
            if item.get('service_category') in ['car', 'line'] or (not item.get('service_category') and not item.get('group_info', {}).get('service_category')):
                r_no = str(item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or '').strip().upper()
                if r_no.startswith('INV'):
                    num_part = re.sub(r'[^0-9]', '', r_no)
                    if num_part.isdigit():
                        nums.append(int(num_part))
        if nums:
            max_num = max(nums)
        else:
            max_num = int(counter.get("last_number", 0))
            
        # Keep counter file in sync
        if counter.get("last_number") != max_num:
            counter["last_number"] = max_num
            save_json(INVOICE_COUNTER_FILE, counter)
            
        return f"{prefix}{(max_num + 1):05d}"

def increment_invoice_no(category='car'):
    next_no = get_next_invoice_no(category)
    cat = (category or 'car').lower().strip()
    counter = load_json(INVOICE_COUNTER_FILE, {
        "last_number": 0, "prefix": "INV ",
        "last_visa_number": 0, "visa_prefix": "VISA ",
        "last_passport_number": 0, "passport_prefix": "INV ",
        "last_quote_number": 0, "quote_prefix": "QT "
    })
    num_part = int(re.sub(r'[^0-9]', '', next_no))
    if cat == 'visa':
        counter["last_visa_number"] = num_part
    elif cat == 'passport':
        counter["last_passport_number"] = num_part
    elif cat in ['quote', 'quotation']:
        counter["last_quote_number"] = num_part
    else:
        counter["last_number"] = num_part
    save_json(INVOICE_COUNTER_FILE, counter)
    return next_no

def decode_b64_image(b64_str):
    if ',' in b64_str:
        b64_str = b64_str.split(',', 1)[1]
    b64_str = b64_str.strip().replace(' ', '+')
    missing_padding = len(b64_str) % 4
    if missing_padding:
        b64_str += '=' * (4 - missing_padding)
    img_bytes = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_bytes))

def parse_multipart_files(handler):
    content_type = handler.headers.get('Content-Type', '')
    if 'boundary=' not in content_type:
        return []
    boundary_str = content_type.split('boundary=')[1].strip()
    if boundary_str.startswith('"') and boundary_str.endswith('"'):
        boundary_str = boundary_str[1:-1]
    boundary = boundary_str.encode('utf-8')
    length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(length)
    
    parts = body.split(b'--' + boundary)
    images = []
    for part in parts:
        if b'Content-Type: image' in part or b'filename=' in part:
            header_end = part.find(b'\r\n\r\n')
            if header_end != -1:
                file_bytes = part[header_end+4:].rstrip(b'\r\n--')
                if len(file_bytes) > 100:
                    try:
                        pil_img = Image.open(io.BytesIO(file_bytes))
                        images.append(pil_img)
                    except Exception as e:
                        print("Multipart PIL load note:", e)
    return images

def extract_best_name(data):
    given = (data.get('english_given_names') or '').strip()
    sur = (data.get('english_surname') or '').strip()
    
    if sur and given:
        cand = f"{sur} {given}".strip()
        cleaned = clean_person_name(cand)
        if cleaned:
            return cleaned

    full_name = (data.get('full_english_name') or '').strip()
    if full_name:
        cleaned = clean_person_name(full_name)
        if cleaned:
            return cleaned

    if given:
        cleaned = clean_person_name(given)
        if cleaned:
            return cleaned

    if sur:
        cleaned = clean_person_name(sur)
        if cleaned:
            return cleaned

    for cand in [data.get('thai_name'), data.get('khmer_name')]:
        if cand and cand.strip():
            return cand.strip()

    return ""

    # Fallback raw_text scan
    if data.get('raw_text'):
        raw_lines = [l.strip() for l in data['raw_text'].split('\n') if l.strip()]
        for line in raw_lines:
            cleaned = clean_person_name(line)
            if cleaned:
                tokens = cleaned.split()
                if len(tokens) >= 2 and all(len(t) >= 3 for t in tokens):
                    return cleaned

    return ""

MONTH_NAME_MAP = {
    'jan': '01', 'january': '01',
    'feb': '02', 'february': '02',
    'mar': '03', 'march': '03',
    'apr': '04', 'april': '04',
    'may': '05',
    'jun': '06', 'june': '06',
    'jul': '07', 'july': '07',
    'aug': '08', 'august': '08',
    'sep': '09', 'september': '09',
    'oct': '10', 'october': '10',
    'nov': '11', 'november': '11',
    'dec': '12', 'december': '12',
}

def parse_flight_ticket_ocr(img_source):
    if not img_source:
        return None
    try:
        engine = None
        if ocr_engine and hasattr(ocr_engine, 'rapid_ocr') and ocr_engine.rapid_ocr:
            engine = ocr_engine.rapid_ocr
        else:
            try:
                from rapidocr_onnxruntime import RapidOCR
                engine = RapidOCR()
            except Exception:
                pass

        if not engine:
            return None

        if isinstance(img_source, str):
            res, _ = engine(img_source)
        else:
            import numpy as np
            arr = np.array(img_source)
            res, _ = engine(arr)

        if not res:
            return None

        lines = [r[1].strip() for r in res if r and len(r) > 1 and r[1] and r[1].strip()]
        full_text = " ".join(lines)

        dep_time = None
        arr_time = None
        times = []
        for tm in re.finditer(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)(?:\s*(AM|PM))?\b', full_text, re.IGNORECASE):
            h = int(tm.group(1))
            mn = tm.group(2)
            ap = tm.group(3)
            if ap and ap.upper() == 'PM' and h < 12: h += 12
            if ap and ap.upper() == 'AM' and h == 12: h = 0
            times.append(f"{h:02d}:{mn}")

        for i, line in enumerate(lines):
            if re.search(r'\b(?:departure|depart|ออก|출발)\b', line, re.IGNORECASE):
                sub = " ".join(lines[i:i+3])
                m = re.search(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)(?:\s*(AM|PM))?\b', sub, re.IGNORECASE)
                if m:
                    h = int(m.group(1))
                    mn = m.group(2)
                    ap = m.group(3)
                    if ap and ap.upper() == 'PM' and h < 12: h += 12
                    if ap and ap.upper() == 'AM' and h == 12: h = 0
                    dep_time = f"{h:02d}:{mn}"
            if re.search(r'\b(?:arrival|arrive|ถึง|도착)\b', line, re.IGNORECASE):
                sub = " ".join(lines[i:i+3])
                m = re.search(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)(?:\s*(AM|PM))?\b', sub, re.IGNORECASE)
                if m:
                    h = int(m.group(1))
                    mn = m.group(2)
                    ap = m.group(3)
                    if ap and ap.upper() == 'PM' and h < 12: h += 12
                    if ap and ap.upper() == 'AM' and h == 12: h = 0
                    arr_time = f"{h:02d}:{mn}"

        if not arr_time and len(times) >= 2:
            dep_time = times[0]
            arr_time = times[1]
        elif not arr_time and len(times) == 1:
            arr_time = times[0]

        # 2. Date
        parsed_date = None
        m_month_word = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]*(\d{1,2})[^\d]*(202\d)\b', full_text, re.IGNORECASE)
        if m_month_word:
            m_str = m_month_word.group(1).lower()[:3]
            d_str = m_month_word.group(2).zfill(2)
            y_str = m_month_word.group(3)
            if m_str in MONTH_NAME_MAP:
                parsed_date = f"{y_str}-{MONTH_NAME_MAP[m_str]}-{d_str}"

        if not parsed_date:
            m_day_word = re.search(r'\b(\d{1,2})[\s\-_]*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_]*(202\d)\b', full_text, re.IGNORECASE)
            if m_day_word:
                d_str = m_day_word.group(1).zfill(2)
                m_str = m_day_word.group(2).lower()[:3]
                y_str = m_day_word.group(3)
                if m_str in MONTH_NAME_MAP:
                    parsed_date = f"{y_str}-{MONTH_NAME_MAP[m_str]}-{d_str}"

        if not parsed_date:
            m_num = re.search(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](202\d)\b', full_text)
            if m_num:
                parsed_date = f"{m_num.group(3)}-{m_num.group(2).zfill(2)}-{m_num.group(1).zfill(2)}"
            else:
                m_iso = re.search(r'\b(202\d)[\/\-](\d{1,2})[\/\-](\d{1,2})\b', full_text)
                if m_iso:
                    parsed_date = f"{m_iso.group(1)}-{m_iso.group(2).zfill(2)}-{m_iso.group(3).zfill(2)}"

        # 3. Flight No
        flight_no = None
        m_flight = re.search(r'(KR|FD|K6|PG|TG|V9|SL|DD|QV|AK|WE|VZ|VN|BK|LQ)\s*[-]?\s*(\d{2,4})\b', full_text, re.IGNORECASE)
        if not m_flight:
            m_flight = re.search(r'\b([A-Z]{2}|[A-Z]\d|\d[A-Z])\s*[-]?\s*(\d{3,4})\b', full_text)
        if m_flight:
            flight_no = f"{m_flight.group(1).upper()}-{m_flight.group(2)}"

        # 4. Route & Direction
        is_rep = bool(re.search(r'เสียมเรียบ|siem\s*reap|SAI\b|REP\b', full_text, re.IGNORECASE))
        is_tia = bool(re.search(r'เตโช|techo|TIA\b|KTI\b', full_text, re.IGNORECASE))
        is_pnh = bool(re.search(r'พนมเปญ|phnom\s*penh|PNH\b', full_text, re.IGNORECASE))

        cambodia_airport = ''
        if is_rep: cambodia_airport = 'សៀមរាប'
        elif is_tia: cambodia_airport = 'តេជោ'
        elif is_pnh: cambodia_airport = 'ភ្នំពេញ'

        direction = 'inbound'
        pickup_loc = cambodia_airport or 'សៀមរាប'
        dropoff_loc = 'ប៉ោយប៉ែត'

        if re.search(r'departure[^\n\r]*(?:SAI|REP|TIA|KTI|PNH|siem|techo|phnom)', full_text, re.IGNORECASE):
            direction = 'outbound'
            pickup_loc = 'ប៉ោយប៉ែត'
            dropoff_loc = cambodia_airport or 'សៀមរាប'

        return {
            'dep_time': dep_time,
            'arr_time': arr_time,
            'date': parsed_date,
            'flight_no': flight_no,
            'direction': direction,
            'pickup_loc': pickup_loc,
            'dropoff_loc': dropoff_loc,
            'cambodia_airport': cambodia_airport,
            'full_text': full_text[:400]
        }
    except Exception as e:
        print(f"[parse_flight_ticket_ocr] Error: {e}")
        return None

class ImvoiWebHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        effective_dir = WEB_DIR if (os.path.exists(WEB_DIR) and os.path.exists(os.path.join(WEB_DIR, 'index.html'))) else BASE_DIR
        super().__init__(*args, directory=effective_dir, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def handle_delete_api(self, params):
        receipt_no = urllib.parse.unquote(params.get('no', '')).strip().lower().replace('🛂', '').strip()
        item_id = urllib.parse.unquote(params.get('id', '')).strip()
        idx_str = str(params.get('index', '')).strip()

        data = load_json(SAVED_CUSTOMERS_FILE, [])
        if not data:
            self.send_json_response({'success': True, 'message': 'No records to delete'})
            return

        # 1. Check explicit 0-based index parameter
        if idx_str != '' and idx_str.isdigit():
            idx = int(idx_str)
            if 0 <= idx < len(data):
                popped = data.pop(idx)
                save_json(SAVED_CUSTOMERS_FILE, data)
                if supabase_db and supabase_db.is_configured():
                    del_rno = popped.get('receipt_no') or (popped.get('group_data') or {}).get('receipt_no') or (popped.get('customer') or {}).get('receipt_no')
                    if del_rno:
                        threading.Thread(target=supabase_db.delete_invoice, args=(del_rno,), daemon=True).start()
                self.send_json_response({'success': True})
                return

        # 2. Match by id, receipt_no, passport_no, or customer_name
        filtered = []
        found = False
        matched_item = None
        for item in data:
            if found:
                filtered.append(item)
                continue

            r_no = (item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('passport_no') or item.get('id') or '').strip().lower().replace('🛂', '').strip()
            pass_no = (item.get('passport_no') or '').strip().lower()
            cur_id = str(item.get('id', '')).strip()
            cust_name = (item.get('customer_name') or item.get('full_english_name') or item.get('group_info', {}).get('customer_name') or item.get('customer', {}).get('full_english_name') or '').strip().lower()

            match = False
            if item_id and cur_id and cur_id == item_id:
                match = True
            elif receipt_no and receipt_no != 'n/a' and (r_no == receipt_no or pass_no == receipt_no):
                match = True
            elif receipt_no and receipt_no != 'n/a' and cust_name and cust_name == receipt_no:
                match = True

            if match:
                found = True
                matched_item = item
                continue
            filtered.append(item)

        if found:
            save_json(SAVED_CUSTOMERS_FILE, filtered)
            if supabase_db and supabase_db.is_configured() and matched_item:
                del_rno = matched_item.get('receipt_no') or (matched_item.get('group_data') or {}).get('receipt_no') or (matched_item.get('customer') or {}).get('receipt_no')
                if del_rno:
                    threading.Thread(target=supabase_db.delete_invoice, args=(del_rno,), daemon=True).start()
            self.send_json_response({'success': True})
            return

        # 3. Fallback: numeric receipt_no as index
        if receipt_no.isdigit():
            idx = int(receipt_no)
            if 0 <= idx < len(data):
                popped = data.pop(idx)
                save_json(SAVED_CUSTOMERS_FILE, data)
                if supabase_db and supabase_db.is_configured():
                    del_rno = popped.get('receipt_no') or (popped.get('group_data') or {}).get('receipt_no') or (popped.get('customer') or {}).get('receipt_no')
                    if del_rno:
                        threading.Thread(target=supabase_db.delete_invoice, args=(del_rno,), daemon=True).start()
                self.send_json_response({'success': True})
                return

        self.send_json_response({'success': False, 'error': 'Receipt or record not found'}, status=404)

    def handle_clear_all_api(self):
        save_json(SAVED_CUSTOMERS_FILE, [])
        self.send_json_response({'success': True, 'message': 'All records cleared'})

    def handle_toggle_status_api(self, params):
        receipt_no = urllib.parse.unquote(params.get('no', '')).strip().lower().replace('🛂', '').strip()
        new_status = params.get('status', 'UNPAID').upper()
        idx_str = str(params.get('index', '')).strip()

        data = load_json(SAVED_CUSTOMERS_FILE, [])
        found = False

        if idx_str != '' and idx_str.isdigit():
            idx = int(idx_str)
            if 0 <= idx < len(data):
                data[idx]['payment_status'] = new_status
                if 'group_data' in data[idx]:
                    data[idx]['group_data']['payment_status'] = new_status
                found = True

        if not found:
            for item in data:
                r_no = (item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('passport_no') or item.get('id') or '').strip().lower().replace('🛂', '').strip()
                if r_no == receipt_no or (item.get('passport_no') and item.get('passport_no').strip().lower() == receipt_no):
                    item['payment_status'] = new_status
                    if 'group_data' in item:
                        item['group_data']['payment_status'] = new_status
                    found = True
                    break

        if found:
            save_json(SAVED_CUSTOMERS_FILE, data)
            self.send_json_response({'success': True})
        else:
            self.send_json_response({'success': False, 'error': 'Receipt not found'}, status=404)

    def do_GET(self):
        if 'If-Modified-Since' in self.headers:
            del self.headers['If-Modified-Since']
        if 'if-modified-since' in self.headers:
            del self.headers['if-modified-since']
        if 'If-None-Match' in self.headers:
            del self.headers['If-None-Match']
        if 'if-none-match' in self.headers:
            del self.headers['if-none-match']

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API Routes
        if path in ['/api/invoices', '/api/get_database']:
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            self.send_json_response({'success': True, 'records': data, 'invoices': data})
            return

        elif path == '/api/telegram_messages':
            tg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
            if not os.path.exists(tg_file):
                tg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
            msgs = load_json(tg_file, [])
            clustered_msgs = cluster_telegram_messages_by_time(msgs)
            self.send_json_response({'success': True, 'messages': clustered_msgs})
            return

        elif path == '/api/bookings':
            bk_file = os.path.join(DATA_DIR, 'saved_bookings.json')
            if not os.path.exists(bk_file):
                bk_file = os.path.join(BASE_DIR, 'saved_bookings.json')
            bks = load_json(bk_file, [])

            # Auto-sync with Supabase Cloud if configured (only seed if local is empty)
            if supabase_db and supabase_db.is_configured():
                try:
                    if not bks:
                        cloud_bks = supabase_db.fetch_bookings()
                        if cloud_bks and isinstance(cloud_bks, list):
                            bks = cloud_bks
                            save_json(bk_file, bks)
                except Exception:
                    pass

            self.send_json_response({'success': True, 'bookings': bks})
            return

        elif path == '/api/customers':
            cust_file = os.path.join(DATA_DIR, 'autorent_customers.json')
            if not os.path.exists(cust_file):
                cust_file = os.path.join(BASE_DIR, 'autorent_customers.json')
            custs = load_json(cust_file, [])
            if not custs:
                # auto-extract from bookings
                bk_file = os.path.join(DATA_DIR, 'saved_bookings.json')
                if not os.path.exists(bk_file):
                    bk_file = os.path.join(BASE_DIR, 'saved_bookings.json')
                bks = load_json(bk_file, [])
                cust_map = {}
                for b in bks:
                    nm = (b.get('customerName') or '').strip()
                    ph = (b.get('customerPhone') or '').strip()
                    tg = (b.get('customerTelegram') or '').strip()
                    if nm and len(nm) >= 2 and nm.lower() not in cust_map:
                        cust_map[nm.lower()] = {
                            'id': f'CUST-{len(cust_map)+1:03d}',
                            'name': nm,
                            'phone': ph,
                            'telegram': tg,
                            'idCard': '',
                            'address': (b.get('dropoffLoc') or '').strip(),
                            'notes': f"កក់ឡាន {b.get('date', '')} {b.get('pickupLoc', '')} -> {b.get('dropoffLoc', '')}"
                        }
                if cust_map:
                    custs = list(cust_map.values())
                    save_json(cust_file, custs)
            self.send_json_response({'success': True, 'customers': custs})
            return

        elif path == '/api/cars':
            car_file = os.path.join(DATA_DIR, 'autorent_cars.json')
            if not os.path.exists(car_file):
                car_file = os.path.join(BASE_DIR, 'autorent_cars.json')
            cars = load_json(car_file, [])
            self.send_json_response({'success': True, 'cars': cars})
            return

        elif path == '/api/hidden_senders':
            hf = os.path.join(DATA_DIR, 'hidden_senders.json')
            if not os.path.exists(hf):
                hf = os.path.join(BASE_DIR, 'hidden_senders.json')
            h_list = load_json(hf, [])
            self.send_json_response({'success': True, 'hidden_senders': h_list})
            return

        elif path == '/api/delete_telegram_message':
            msg_id = query.get('id', [None])[0]
            msg_text = query.get('text', [None])[0]
            clear_all = query.get('all', ['false'])[0].lower() in ['true', '1']

            tg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
            if not os.path.exists(tg_file):
                tg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
            msgs = load_json(tg_file, [])
            orig_len = len(msgs)

            if clear_all:
                msgs = []
            elif msg_id:
                msgs = [m for m in msgs if str(m.get('id')) != str(msg_id)]
            elif msg_text:
                msgs = [m for m in msgs if m.get('text', '').strip() != msg_text.strip()]

            save_json(tg_file, msgs)
            self.send_json_response({'success': True, 'deleted': orig_len - len(msgs), 'remaining': len(msgs), 'messages': msgs})
            return

        elif path == '/api/next_no':
            cat = query.get('category', ['car'])[0]
            self.send_json_response({'success': True, 'next_no': get_next_invoice_no(cat)})
            return

        elif path == '/api/set_counter':
            cat = query.get('category', ['car'])[0].lower().strip()
            num_str = query.get('number', ['0'])[0]
            num = int(re.sub(r'[^0-9]', '', str(num_str)) or 0)
            counter = load_json(INVOICE_COUNTER_FILE, {
                "last_number": 0, "prefix": "INV ",
                "last_visa_number": 0, "visa_prefix": "VISA ",
                "last_passport_number": 0, "passport_prefix": "INV "
            })
            if cat == 'visa':
                counter["last_visa_number"] = num
            elif cat == 'passport':
                counter["last_passport_number"] = num
            else:
                counter["last_number"] = num
            save_json(INVOICE_COUNTER_FILE, counter)
            self.send_json_response({'success': True, 'category': cat, 'last_number': num, 'next_no': get_next_invoice_no(cat)})
            return

        elif path in ['/api/invoice', '/api/receipt']:
            raw_no = query.get('no', [''])[0].strip()
            clean_query = raw_no.lower().replace('🛂', '').replace('-', '').replace(' ', '').strip()
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            target = None
            for item in data:
                candidates = [
                    str(item.get('receipt_no') or ''),
                    str((item.get('group_data') or {}).get('receipt_no') or ''),
                    str((item.get('customer') or {}).get('receipt_no') or ''),
                    str((item.get('group_info') or {}).get('receipt_no') or ''),
                    str(item.get('passport_no') or ''),
                    str(item.get('id') or '')
                ]
                for c in candidates:
                    c_clean = c.lower().replace('🛂', '').replace('-', '').replace(' ', '').strip()
                    if c_clean and (c_clean == clean_query or (clean_query.isdigit() and c_clean.endswith(clean_query))):
                        target = item
                        break
                if target:
                    break
            if target:
                self.send_json_response({'success': True, 'invoice': target})
            else:
                self.send_json_response({'success': False, 'error': f'Invoice {raw_no} not found'}, status=404)
            return

        elif path == '/api/toggle_status':
            params = {k: v[0] for k, v in query.items() if v}
            self.handle_toggle_status_api(params)
            return

        elif path == '/api/delete':
            params = {k: v[0] for k, v in query.items() if v}
            self.handle_delete_api(params)
            return

        elif path == '/api/clear_all':
            self.handle_clear_all_api()
            return

        elif path == '/api/delete_member':
            receipt_no = query.get('no', [''])[0].strip().lower().replace('🛂', '').strip()
            try:
                m_idx = int(query.get('index', [-1])[0])
            except Exception:
                m_idx = -1

            data = load_json(SAVED_CUSTOMERS_FILE, [])
            found = False
            for item in data:
                r_no = (item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('passport_no') or item.get('id') or '').strip().lower().replace('🛂', '').strip()
                if r_no == receipt_no or (item.get('passport_no') and item.get('passport_no').strip().lower() == receipt_no):
                    members = item.get('members', [])
                    if 0 <= m_idx < len(members):
                        members.pop(m_idx)
                        exchange_rate = float(item.get('group_data', {}).get('exchange_rate', 33.90))
                        new_items = []
                        grand_usd = 0.0
                        for idx, m in enumerate(members, 1):
                            name = m.get('full_english_name') or m.get('english_name') or m.get('name', '')
                            vip = float(m.get('vip', 0.0))
                            clearance = float(m.get('clearance_fee', 0.0))
                            permit = float(m.get('work_permit', 0.0))
                            car = float(m.get('car_fee', 0.0))
                            visa = float(m.get('visa_fee', 0.0))
                            evisa = float(m.get('e_visa', 0.0))
                            row_usd = float(m.get('usd', 0.0))
                            if row_usd == 0 and (vip or clearance or permit or car or visa or evisa):
                                row_usd = vip + clearance + permit + car + visa + evisa
                                m['usd'] = row_usd

                            grand_usd += row_usd
                            new_items.append({
                                'no': idx,
                                'description': name,
                                'qty': '1',
                                'e_visa': f"${evisa}" if evisa > 0 else '',
                                'vip': f"${vip}" if vip > 0 else '',
                                'overstay': '',
                                'car_fee': f"${car}" if car > 0 else '',
                                'visa': f"${visa}" if visa > 0 else '',
                                'clearance_fee': f"${clearance}" if clearance > 0 else '',
                                'work_permit': f"${permit}" if permit > 0 else '',
                                'usd': row_usd
                            })

                        grand_thb = grand_usd * exchange_rate
                        pax_count = len(members)
                        first_cust_name = members[0].get('full_english_name') if members else 'N/A'

                        if 'group_info' in item:
                            item['group_info']['customer_name'] = first_cust_name
                        if 'customer' in item:
                            item['customer']['sex'] = f"{pax_count} Pax"
                        if 'group_data' in item:
                            item['group_data']['items'] = new_items
                            item['group_data']['totals'] = {'usd': grand_usd, 'baht': grand_thb}
                            item['group_data']['group_customer_name'] = first_cust_name
                        item['totals'] = {'usd': grand_usd, 'baht': grand_thb}

                        found = True
                        break

            if found:
                save_json(SAVED_CUSTOMERS_FILE, data)
                self.send_json_response({'success': True})
            else:
                self.send_json_response({'success': False, 'error': 'Member or Receipt not found'}, status=404)
            return

        elif path == '/api/get_telegram_config':
            cfg = get_telegram_config()
            self.send_json_response({'success': True, 'config': cfg})
            return

        elif path == '/api/telegram_bot_status':
            status = telegram_bot_listener.get_status() if telegram_bot_listener else {"running": False}
            self.send_json_response({'success': True, 'status': status})
            return

        elif path == '/api/telegram_messages':
            msg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
            if not os.path.exists(msg_file):
                msg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
            msgs = load_json(msg_file, [])
            clustered_msgs = cluster_telegram_messages_by_time(msgs)
            self.send_json_response({'success': True, 'messages': clustered_msgs})
            return

        elif path == '/api/latest_telegram_scans':
            query_params = urllib.parse.parse_qs(parsed.query)
            since_id = query_params.get('since', [None])[0]
            scans = telegram_bot_listener.get_latest_scans(since_id) if telegram_bot_listener else []
            self.send_json_response({'success': True, 'scans': scans})
            return

        elif path == '/api/supabase_status':
            configured = supabase_db.is_configured() if supabase_db else False
            url, key = supabase_db.get_supabase_credentials() if supabase_db else ('', '')
            masked_key = (key[:6] + '...' + key[-4:]) if len(key) > 10 else ('***' if key else '')
            self.send_json_response({
                'success': True,
                'configured': configured,
                'url': url,
                'key_preview': masked_key
            })
            return

        if path == '/api/telegram_groups':
            groups_by_title = {}
            for g_dir in [DATA_DIR, BASE_DIR]:
                gf = os.path.join(g_dir, "known_telegram_groups.json")
                if os.path.exists(gf):
                    try:
                        with open(gf, "r", encoding="utf-8") as f_g:
                            kg = json.load(f_g)
                            for cid, gdata in kg.items():
                                if cid != "latest_group_id" and isinstance(gdata, dict):
                                    t = gdata.get('title', 'Telegram Group').strip()
                                    if not t:
                                        continue
                                    existing = groups_by_title.get(t.lower())
                                    # If not seen yet, or if current is supergroup (-100...) and old wasn't, replace
                                    if not existing or (cid.startswith('-100') and not existing['id'].startswith('-100')):
                                        groups_by_title[t.lower()] = {
                                            'id': cid,
                                            'title': t,
                                            'link': gdata.get('link', '') or (existing.get('link', '') if existing else '')
                                        }
                            break
                    except Exception:
                        pass
            groups = list(groups_by_title.values())
            self.send_json_response({'success': True, 'groups': groups})
            return


        # Serve static web assets
        if path.startswith('/assets/'):
            clean_rel = path.lstrip('/').replace('/', os.sep)
            asset_path = os.path.join(BASE_DIR, clean_rel)
            if os.path.exists(asset_path) and os.path.isfile(asset_path):
                ext = os.path.splitext(asset_path)[1].lower()
                mime = 'text/plain'
                if ext == '.css': mime = 'text/css; charset=utf-8'
                elif ext == '.js': mime = 'application/javascript; charset=utf-8'
                elif ext in ['.jpg', '.jpeg']: mime = 'image/jpeg'
                elif ext == '.png': mime = 'image/png'
                elif ext == '.svg': mime = 'image/svg+xml'
                elif ext == '.ico': mime = 'image/x-icon'
                
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.end_headers()
                with open(asset_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        if path == '/' or path == '' or path == '/index.html':
            try:
                with open('index.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                pass

        return super().do_GET()

    def do_POST(self):
        try:
            self.handle_post_request()
        except Exception as e:
            traceback.print_exc()
            try:
                self.send_json_response({'success': False, 'error': f"Internal Server Error: {str(e)}"}, status=500)
            except Exception:
                pass

    def handle_post_request(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_type = self.headers.get('Content-Type', '')

        # AI OCR Processing Endpoint for Batch/Single Images (Supports both Multipart and Base64)
        if path == '/api/ocr_scan':
            pil_images = []

            if 'multipart/form-data' in content_type:
                pil_images = parse_multipart_files(self)
            else:
                length = int(self.headers.get('Content-Length', 0))
                body_bytes = self.rfile.read(length)
                try:
                    req_data = json.loads(body_bytes.decode('utf-8'))
                    images_b64 = req_data.get('images', [])
                    if not images_b64 and req_data.get('image'):
                        images_b64 = [req_data.get('image')]
                    for b64_str in images_b64:
                        try:
                            pil_images.append(decode_b64_image(b64_str))
                        except Exception as e:
                            print("Base64 decode note:", e)
                except Exception:
                    pass

            extracted_results = []
            for idx, pil_img in enumerate(pil_images, 1):
                try:
                    if ocr_engine:
                        data, _ = ocr_engine.process_image(pil_img)
                    else:
                        data = {'full_english_name': f'PASSPORT CUSTOMER {idx}', 'passport_no': '', 'nationality': 'THAI'}

                    extracted_name = extract_best_name(data)
                    if not extracted_name:
                        extracted_name = f"PASSPORT CUSTOMER {idx}"

                    print(f"Scanned Passport #{idx}: Name='{extracted_name}', Pass='{data.get('passport_no','')}'")

                    extracted_results.append({
                        'full_english_name': extracted_name,
                        'passport_no': data.get('passport_no', '') or '',
                        'nationality': data.get('nationality', 'THAI') or 'THAI',
                        'dob': data.get('dob', ''),
                        'sex': data.get('sex', ''),
                        'doc_type': data.get('doc_type', '')
                    })
                except Exception as e:
                    print("OCR Image Process Exception:", e)
                    extracted_results.append({
                        'full_english_name': f"PASSPORT CUSTOMER {idx}",
                        'passport_no': '',
                        'nationality': 'THAI'
                    })

            self.send_json_response({'success': True, 'results': extracted_results})
            return

        length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(length) if length > 0 else b''
        try:
            req_data = json.loads(body_bytes.decode('utf-8')) if body_bytes else {}
        except Exception:
            req_data = {}

        query = urllib.parse.parse_qs(parsed.query)

        if path == '/api/clear_all':
            self.handle_clear_all_api()
            return
        elif path == '/api/delete':
            params = {k: v[0] for k, v in query.items() if v}
            if isinstance(req_data, dict):
                for k, v in req_data.items():
                    if k not in params or not params[k]:
                        params[k] = str(v)
            self.handle_delete_api(params)
            return
        elif path == '/api/toggle_status':
            params = {k: v[0] for k, v in query.items() if v}
            if isinstance(req_data, dict):
                for k, v in req_data.items():
                    if k not in params or not params[k]:
                        params[k] = str(v)
            self.handle_toggle_status_api(params)
            return

        elif path == '/api/parse_flight_ticket':
            img_url = req_data.get('url') or req_data.get('image_url') or ''
            img_b64 = req_data.get('image') or req_data.get('image_b64') or ''
            target_path = None
            if img_url:
                clean_url = img_url.lstrip('/')
                for candidate_dir in [BASE_DIR, DATA_DIR, os.path.join(BASE_DIR, 'telegram_images')]:
                    c_path = os.path.join(candidate_dir, clean_url)
                    if os.path.exists(c_path):
                        target_path = c_path
                        break
                    b_path = os.path.join(candidate_dir, os.path.basename(clean_url))
                    if os.path.exists(b_path):
                        target_path = b_path
                        break
            pil_img = None
            if not target_path and img_b64:
                try:
                    pil_img = decode_b64_image(img_b64)
                except Exception as e:
                    print(f"Error decoding b64 for flight ticket: {e}")
            parsed = parse_flight_ticket_ocr(target_path or pil_img)
            self.send_json_response({'success': bool(parsed), 'data': parsed or {}})
            return

        if path == '/api/save_group':
            group_name = req_data.get('group_name', 'VIP Group').strip()
            customer_name = req_data.get('customer_name', '').strip()
            agency_company = req_data.get('agency_company', '').strip()
            travel_date = req_data.get('travel_date', '').strip()
            exchange_rate = float(req_data.get('exchange_rate', 33.90))
            payment_status = req_data.get('payment_status', 'UNPAID').upper()
            members_raw = req_data.get('members', [])
            edit_receipt_no = req_data.get('receipt_no', '').strip()

            if edit_receipt_no:
                receipt_no = edit_receipt_no
            else:
                receipt_no = increment_invoice_no()

            members = []
            items = []
            grand_usd = 0.0

            for idx, m in enumerate(members_raw, 1):
                name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
                pass_no = (m.get('passport_no') or m.get('passport') or '-').strip()
                nat = (m.get('nationality') or 'THAI').strip()
                vip = float(m.get('vip', 0))
                clearance = float(m.get('clearance_fee', m.get('clearance', 0)))
                permit = float(m.get('work_permit', 0))
                car = float(m.get('car_fee', m.get('car', 0)))
                visa = float(m.get('visa_fee', m.get('visa', 0)))
                evisa = float(m.get('evisa', m.get('e_visa', 0)))
                overstay = float(m.get('overstay', m.get('fine_fee', m.get('fine', 0))))
                passport_fee = float(m.get('passport_fee', 0.0))
                namelist_fee = float(m.get('namelist_fee', 0.0))
                missing_doc_fee = float(m.get('missing_doc_fee', 0.0) or m.get('doc_fee', 0.0))
                visa_stamping_fee = float(m.get('visa_stamping_fee', 0.0) or m.get('stamping_fee', 0.0))
                months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                visa_status = 'issued' if is_issued else 'pending'
                photo_data = str(m.get('photo_data') or m.get('photo') or m.get('image_url') or '')

                row_usd = float(m.get('usd', 0.0))
                if row_usd == 0:
                    row_usd = vip + clearance + permit + car + visa + evisa + overstay + passport_fee + namelist_fee + missing_doc_fee + visa_stamping_fee

                if not name:
                    if row_usd > 0 or photo_data:
                        name = f"Pax {idx}"
                    else:
                        continue

                grand_usd += row_usd

                members.append({
                    'full_english_name': name,
                    'english_name': name,
                    'passport_no': pass_no,
                    'nationality': nat,
                    'photo': photo_data,
                    'photo_data': photo_data,
                    'passport_fee': passport_fee,
                    'namelist_fee': namelist_fee,
                    'missing_doc_fee': missing_doc_fee,
                    'visa_stamping_fee': visa_stamping_fee,
                    'car_fee': car,
                    'visa_fee': visa,
                    'extension_months': months,
                    'months': months,
                    'visa_months': months,
                    'price': 0.0,
                    'e_visa': evisa,
                    'vip': vip,
                    'clearance_fee': clearance,
                    'work_permit': permit,
                    'overstay': overstay,
                    'fine_fee': overstay,
                    'usd': row_usd,
                    'qty': '1',
                    'visa_issued': is_issued,
                    'visa_status': visa_status
                })

                items.append({
                    'no': idx,
                    'description': name,
                    'qty': '1',
                    'passport_fee': f"${passport_fee:.0f}" if passport_fee > 0 else '',
                    'namelist_fee': f"${namelist_fee:.0f}" if namelist_fee > 0 else '',
                    'missing_doc_fee': f"${missing_doc_fee:.0f}" if missing_doc_fee > 0 else '',
                    'visa_stamping_fee': f"${visa_stamping_fee:.0f}" if visa_stamping_fee > 0 else '',
                    'extension_months': months,
                    'months': months,
                    'visa_months': months,
                    'e_visa': f"${evisa:.0f}" if evisa > 0 else '',
                    'vip': f"${vip:.0f}" if vip > 0 else '',
                    'overstay': f"${overstay:.0f}" if overstay > 0 else '',
                    'car_fee': f"${car:.0f}" if car > 0 else '',
                    'visa': f"${visa:.0f}" if visa > 0 else '',
                    'clearance_fee': f"${clearance:.0f}" if clearance > 0 else '',
                    'work_permit': f"${permit:.0f}" if permit > 0 else '',
                    'usd': row_usd,
                    'visa_issued': is_issued,
                    'visa_status': visa_status
                })

            pax_count = len(members)
            service_category = req_data.get('service_category', 'car')
            grand_thb = grand_usd if service_category == 'passport' else (grand_usd * exchange_rate)
            formatted_cust_name = format_group_customer_names(members) or customer_name or (members[0]['full_english_name'] if members else group_name)

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
            date_saved_str = urllib.parse.unquote(req_data.get('date_saved', ''))
            
            # If updating existing invoice, keep existing date_saved if none provided
            if edit_receipt_no:
                for old_inv in all_invoices:
                    old_r_no = old_inv.get('group_data', {}).get('receipt_no') or old_inv.get('customer', {}).get('receipt_no') or ''
                    if old_r_no.strip().lower() == edit_receipt_no.strip().lower():
                        if not date_saved_str:
                            date_saved_str = old_inv.get('date_saved', '')
                        if 'service_category' in old_inv and not req_data.get('service_category'):
                            service_category = old_inv['service_category']
                        break

            new_invoice = {
                'date_saved': date_saved_str,
                'service_category': service_category,
                'customer': {
                    'full_english_name': f"GROUP: {group_name} ({pax_count} Pax)",
                    'nationality': 'GROUP',
                    'sex': f"{pax_count} Pax",
                    'receipt_no': receipt_no,
                    'agency_company': agency_company
                },
                'payment_status': payment_status,
                'sender': group_name,
                'sender_name': group_name,
                'agency_company': agency_company,
                'customer_name': f"{group_name} ({pax_count} Pax)",
                'group_info': {
                    'group_name': group_name,
                    'sender_name': group_name,
                    'customer_name': formatted_cust_name,
                    'agency_company': agency_company,
                    'travel_date': travel_date,
                    'receipt_no': receipt_no
                },
                'members': members,
                'group_data': {
                    'customer_name': group_name,
                    'sender_name': group_name,
                    'group_customer_name': formatted_cust_name,
                    'agency_company': agency_company,
                    'date_str': travel_date,
                    'travel_date': travel_date,
                    'receipt_no': receipt_no,
                    'exchange_rate': exchange_rate,
                    'items': items,
                    'totals': {'usd': grand_usd, 'baht': grand_thb}
                },
                'totals': {'usd': grand_usd, 'baht': grand_thb}
            }

            if edit_receipt_no:
                updated = False
                for i, old_inv in enumerate(all_invoices):
                    old_r_no = old_inv.get('group_data', {}).get('receipt_no') or old_inv.get('customer', {}).get('receipt_no') or ''
                    if old_r_no.strip().lower() == edit_receipt_no.strip().lower():
                        all_invoices[i] = new_invoice
                        updated = True
                        break
                if not updated:
                    all_invoices.insert(0, new_invoice)
            else:
                all_invoices.insert(0, new_invoice)

            save_json(SAVED_CUSTOMERS_FILE, all_invoices)

            self.send_json_response({'success': True, 'receipt_no': receipt_no})
            return

        elif path == '/api/save_single':
            name = req_data.get('full_english_name', 'Guest').strip()
            passport = req_data.get('passport_no', '').strip()
            nationality = req_data.get('nationality', 'THAI').strip()
            dob = req_data.get('dob', '').strip()
            travel_date = req_data.get('travel_date', '').strip()

            vip = float(req_data.get('vip_fee', 0))
            clearance = float(req_data.get('clearance_fee', 0))
            permit = float(req_data.get('work_permit', 0))
            car = float(req_data.get('car_fee', 0))
            visa = float(req_data.get('visa_fee', 0))
            evisa = float(req_data.get('e_visa', 0))
            payment_status = req_data.get('payment_status', 'UNPAID').upper()

            total_usd = vip + clearance + permit + car + visa + evisa
            total_thb = total_usd * 33.90

            receipt_no = increment_invoice_no()

            new_single = {
                'date_saved': urllib.parse.unquote(req_data.get('date_saved', '')),
                'customer': {
                    'full_english_name': name,
                    'passport_number': passport,
                    'nationality': nationality,
                    'date_of_birth': dob,
                    'receipt_no': receipt_no
                },
                'fees': {
                    'vip_fee': vip,
                    'clearance_fee': clearance,
                    'work_permit': permit,
                    'car_fee': car,
                    'visa_fee': visa,
                    'e_visa': evisa,
                    'exchange_rate': 33.90
                },
                'totals': {'usd': total_usd, 'baht': total_thb},
                'payment_status': payment_status
            }

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
            all_invoices.insert(0, new_single)
            save_json(SAVED_CUSTOMERS_FILE, all_invoices)

            self.send_json_response({'success': True, 'receipt_no': receipt_no})
            return

        elif path == '/api/update_members':
            receipt_no = req_data.get('receipt_no', '').strip().lower()
            members_data = req_data.get('members', [])
            travel_date = req_data.get('travel_date', '').strip()
            sender_name = req_data.get('sender_name', '').strip()
            agency_company = req_data.get('agency_company', '').strip()
            group_name_input = req_data.get('group_name', '').strip()
            req_service_category = str(req_data.get('service_category', '')).strip().lower()

            if not receipt_no:
                self.send_json_response({'success': False, 'error': 'Missing receipt_no'}, status=400)
                return

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
            found = False
            updated_item = None

            for item in all_invoices:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
                    if travel_date:
                        formatted_tdate = format_display_date(travel_date)
                        item['travel_date'] = formatted_tdate
                        if 'group_info' in item:
                            item['group_info']['travel_date'] = formatted_tdate
                        if 'group_data' in item:
                            item['group_data']['travel_date'] = formatted_tdate
                            item['group_data']['date_str'] = formatted_tdate
                        if 'customer' in item:
                            item['customer']['travel_date'] = formatted_tdate

                    if sender_name:
                        item['sender'] = sender_name
                        item['sender_name'] = sender_name
                        if 'group_info' in item:
                            item['group_info']['sender_name'] = sender_name
                            if not group_name_input:
                                item['group_info']['group_name'] = sender_name
                        if 'group_data' in item:
                            item['group_data']['sender_name'] = sender_name
                            if not group_name_input:
                                item['group_data']['customer_name'] = sender_name

                    if group_name_input:
                        if 'group_info' in item:
                            item['group_info']['group_name'] = group_name_input
                        if 'group_data' in item:
                            item['group_data']['customer_name'] = group_name_input

                    if agency_company is not None:
                        item['agency_company'] = agency_company
                        if 'group_info' in item:
                            item['group_info']['agency_company'] = agency_company
                        if 'group_data' in item:
                            item['group_data']['agency_company'] = agency_company
                        if 'customer' in item:
                            item['customer']['agency_company'] = agency_company

                    if req_service_category:
                        item['service_category'] = req_service_category
                        if 'group_info' in item:
                            item['group_info']['service_category'] = req_service_category
                        if 'customer' in item:
                            item['customer']['service_category'] = req_service_category

                    exchange_rate = safe_float(item.get('group_data', {}).get('exchange_rate', 33.90), 33.90)
                    new_members = []
                    new_items = []
                    grand_usd = 0.0

                    for idx, m in enumerate(members_data, 1):
                        name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
                        pass_no = (m.get('passport_no') or m.get('passport') or '-').strip()
                        nat = (m.get('nationality') or 'THAI').strip()
                        usd = safe_float(m.get('usd', 0.0))
                        vip = safe_float(m.get('vip', 0.0))
                        clearance = safe_float(m.get('clearance_fee', 0.0) or m.get('clearance', 0.0))
                        permit = safe_float(m.get('work_permit', 0.0))
                        car = safe_float(m.get('car_fee', 0.0) or m.get('car', 0.0))
                        visa = safe_float(m.get('visa_fee', 0.0) or m.get('visa', 0.0))
                        evisa = safe_float(m.get('e_visa', 0.0) or m.get('evisa', 0.0))
                        overstay = safe_float(m.get('overstay', 0.0) or m.get('fine_fee', 0.0) or m.get('fine', 0.0))
                        passport_fee = safe_float(m.get('passport_fee', 0.0))
                        namelist_fee = safe_float(m.get('namelist_fee', 0.0))
                        missing_doc_fee = safe_float(m.get('missing_doc_fee', 0.0) or m.get('doc_fee', 0.0))
                        visa_stamping_fee = safe_float(m.get('visa_stamping_fee', 0.0) or m.get('stamping_fee', 0.0))
                        months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                        is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                        visa_status = 'issued' if is_issued else 'pending'

                        if usd == 0 and (vip or clearance or permit or car or visa or evisa or overstay or passport_fee or namelist_fee or missing_doc_fee or visa_stamping_fee):
                            usd = vip + clearance + permit + car + visa + evisa + overstay + passport_fee + namelist_fee + missing_doc_fee + visa_stamping_fee

                        photo_data = str(m.get('photo_data') or m.get('photo') or m.get('image_url') or '')

                        if not name:
                            if usd > 0 or photo_data:
                                name = f"Pax {idx}"
                            else:
                                continue

                        grand_usd += usd

                        new_members.append({
                            'full_english_name': name,
                            'english_name': name,
                            'passport_no': pass_no,
                            'nationality': nat,
                            'photo': photo_data,
                            'photo_data': photo_data,
                            'passport_fee': passport_fee,
                            'namelist_fee': namelist_fee,
                            'missing_doc_fee': missing_doc_fee,
                            'visa_stamping_fee': visa_stamping_fee,
                            'car_fee': car,
                            'visa_fee': visa,
                            'extension_months': months,
                            'months': months,
                            'visa_months': months,
                            'price': 0.0,
                            'e_visa': evisa,
                            'vip': vip,
                            'clearance_fee': clearance,
                            'work_permit': permit,
                            'overstay': overstay,
                            'fine_fee': overstay,
                            'usd': usd,
                            'qty': '1',
                            'visa_issued': is_issued,
                            'visa_status': visa_status
                        })

                        new_items.append({
                            'no': idx,
                            'description': name,
                            'qty': '1',
                            'passport_fee': f"${passport_fee:.0f}" if passport_fee > 0 else '',
                            'namelist_fee': f"${namelist_fee:.0f}" if namelist_fee > 0 else '',
                            'missing_doc_fee': f"${missing_doc_fee:.0f}" if missing_doc_fee > 0 else '',
                            'visa_stamping_fee': f"${visa_stamping_fee:.0f}" if visa_stamping_fee > 0 else '',
                            'extension_months': months,
                            'months': months,
                            'visa_months': months,
                            'e_visa': f"${evisa:.0f}" if evisa > 0 else '',
                            'vip': f"${vip:.0f}" if vip > 0 else '',
                            'overstay': f"${overstay:.0f}" if overstay > 0 else '',
                            'car_fee': f"${car:.0f}" if car > 0 else '',
                            'visa': f"${visa:.0f}" if visa > 0 else '',
                            'clearance_fee': f"${clearance:.0f}" if clearance > 0 else '',
                            'work_permit': f"${permit:.0f}" if permit > 0 else '',
                            'usd': usd,
                            'visa_issued': is_issued,
                            'visa_status': visa_status
                        })

                    service_cat = req_service_category or item.get('service_category') or item.get('group_info', {}).get('service_category') or 'car'
                    grand_thb = grand_usd if service_cat == 'passport' else (grand_usd * exchange_rate)
                    pax_count = len(new_members)
                    first_cust_name = new_members[0]['full_english_name'] if new_members else 'N/A'
                    group_name = group_name_input or sender_name or item.get('group_info', {}).get('group_name') or item.get('group_data', {}).get('customer_name') or 'VIP Group'

                    item['members'] = new_members
                    item['customer_name'] = f"{group_name} ({pax_count} Pax)" if pax_count > 0 else group_name
                    if 'customer' in item:
                        item['customer']['full_english_name'] = f"GROUP: {group_name} ({pax_count} Pax)"
                        item['customer']['sex'] = f"{pax_count} Pax"
                    if 'group_info' in item:
                        item['group_info']['customer_name'] = first_cust_name
                        item['group_info']['pax_count'] = pax_count
                    if 'group_data' in item:
                        item['group_data']['items'] = new_items
                        item['group_data']['totals'] = {'usd': grand_usd, 'baht': grand_thb}
                        item['group_data']['group_customer_name'] = first_cust_name
                    item['totals'] = {'usd': grand_usd, 'baht': grand_thb}

                    found = True
                    updated_item = item
                    break

            if not found:
                # Create brand new group record
                formatted_tdate = format_display_date(travel_date) if travel_date else datetime.datetime.now().strftime("%d-%m-%Y")
                exchange_rate = safe_float(req_data.get('exchange_rate', 33.90), 33.90)
                service_category = req_service_category or 'passport'
                new_members = []
                new_items = []
                grand_usd = 0.0

                for idx_m, m in enumerate(members_data, 1):
                    m_name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
                    pass_no = (m.get('passport_no') or m.get('passport') or '-').strip()
                    nat = (m.get('nationality') or 'THAI').strip()
                    photo_data = str(m.get('photo_data') or m.get('photo') or m.get('image_url') or '')
                    passport_fee = safe_float(m.get('passport_fee', 0.0))
                    namelist_fee = safe_float(m.get('namelist_fee', 0.0))
                    missing_doc_fee = safe_float(m.get('missing_doc_fee', 0.0) or m.get('doc_fee', 0.0))
                    visa_stamping_fee = safe_float(m.get('visa_stamping_fee', 0.0) or m.get('stamping_fee', 0.0))
                    evisa = safe_float(m.get('e_visa') or m.get('evisa') or 0)
                    vip = safe_float(m.get('vip') or 0)
                    clearance = safe_float(m.get('clearance_fee') or m.get('clearance') or 0)
                    permit = safe_float(m.get('work_permit') or m.get('permit') or 0)
                    car = safe_float(m.get('car_fee') or m.get('car') or 0)
                    visa = safe_float(m.get('visa_fee') or m.get('visa') or 0)
                    overstay = safe_float(m.get('overstay') or m.get('fine_fee') or m.get('fine') or 0)
                    months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                    is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                    visa_status = 'issued' if is_issued else 'pending'
                    usd = safe_float(m.get('usd') or 0)
                    if usd == 0 and (evisa or vip or clearance or permit or car or visa or overstay or passport_fee or namelist_fee or missing_doc_fee or visa_stamping_fee):
                        usd = evisa + vip + clearance + permit + car + visa + overstay + passport_fee + namelist_fee + missing_doc_fee + visa_stamping_fee

                    if not m_name:
                        if usd > 0 or photo_data:
                            m_name = f"Pax {idx_m}"
                        else:
                            continue

                    grand_usd += usd
                    new_members.append({
                        'full_english_name': m_name,
                        'name': m_name,
                        'passport_no': pass_no,
                        'nationality': nat,
                        'photo': photo_data,
                        'photo_data': photo_data,
                        'passport_fee': passport_fee,
                        'namelist_fee': namelist_fee,
                        'missing_doc_fee': missing_doc_fee,
                        'visa_stamping_fee': visa_stamping_fee,
                        'car_fee': car,
                        'visa_fee': visa,
                        'extension_months': months,
                        'months': months,
                        'visa_months': months,
                        'price': 0.0,
                        'e_visa': evisa,
                        'vip': vip,
                        'clearance_fee': clearance,
                        'work_permit': permit,
                        'overstay': overstay,
                        'fine_fee': overstay,
                        'usd': usd,
                        'qty': '1',
                        'visa_issued': is_issued,
                        'visa_status': visa_status
                    })
                    new_items.append({
                        'no': idx_m,
                        'description': m_name,
                        'qty': '1',
                        'passport_fee': f"${passport_fee:.0f}" if passport_fee > 0 else '',
                        'namelist_fee': f"${namelist_fee:.0f}" if namelist_fee > 0 else '',
                        'missing_doc_fee': f"${missing_doc_fee:.0f}" if missing_doc_fee > 0 else '',
                        'visa_stamping_fee': f"${visa_stamping_fee:.0f}" if visa_stamping_fee > 0 else '',
                        'extension_months': months,
                        'months': months,
                        'visa_months': months,
                        'e_visa': f"${evisa:.0f}" if evisa > 0 else '',
                        'vip': f"${vip:.0f}" if vip > 0 else '',
                        'overstay': f"${overstay:.0f}" if overstay > 0 else '',
                        'car_fee': f"${car:.0f}" if car > 0 else '',
                        'visa': f"${visa:.0f}" if visa > 0 else '',
                        'clearance_fee': f"${clearance:.0f}" if clearance > 0 else '',
                        'work_permit': f"${permit:.0f}" if permit > 0 else '',
                        'usd': usd,
                        'visa_issued': is_issued,
                        'visa_status': visa_status
                    })

                grand_thb = grand_usd if service_category == 'passport' else (grand_usd * exchange_rate)
                pax_count = len(new_members)
                first_cust_name = new_members[0]['full_english_name'] if new_members else 'N/A'
                group_name = group_name_input or sender_name or 'VIP Group'

                clean_r_no = req_data.get('receipt_no', '').strip()
                if not clean_r_no:
                    clean_r_no = increment_invoice_no(service_category)
                else:
                    if service_category == 'visa' and not (clean_r_no.upper().startswith('VISA') or clean_r_no.upper().startswith('INV')):
                        clean_r_no = f"VISA {clean_r_no.lstrip('#').strip()}"
                    elif service_category in ['quote', 'quotation'] and not (clean_r_no.upper().startswith('QT') or clean_r_no.upper().startswith('QUO')):
                        clean_r_no = f"QT {clean_r_no.lstrip('#').strip()}"
                    elif service_category not in ['visa', 'quote', 'quotation'] and not (clean_r_no.upper().startswith('INV') or clean_r_no.upper().startswith('CAR')):
                        clean_r_no = f"INV {clean_r_no.lstrip('#').strip()}"

                new_record = {
                    'id': str(uuid.uuid4()),
                    'receipt_no': clean_r_no,
                    'service_category': service_category,
                    'date_saved': datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'travel_date': formatted_tdate,
                    'sender': sender_name,
                    'sender_name': sender_name,
                    'agency_company': agency_company,
                    'customer_name': f"{group_name} ({pax_count} នាក់)" if pax_count > 0 else group_name,
                    'payment_status': 'UNPAID',
                    'customer': {
                        'receipt_no': clean_r_no,
                        'full_english_name': f"GROUP: {group_name} ({pax_count} នាក់)",
                        'agency_company': agency_company,
                        'travel_date': formatted_tdate,
                        'sex': f"{pax_count} Pax",
                        'service_category': service_category
                    },
                    'group_info': {
                        'receipt_no': clean_r_no,
                        'group_name': group_name,
                        'sender_name': sender_name,
                        'customer_name': first_cust_name,
                        'travel_date': formatted_tdate,
                        'agency_company': agency_company,
                        'service_category': service_category,
                        'pax_count': pax_count
                    },
                    'group_data': {
                        'receipt_no': clean_r_no,
                        'customer_name': group_name,
                        'sender_name': sender_name,
                        'date_str': formatted_tdate,
                        'travel_date': formatted_tdate,
                        'agency_company': agency_company,
                        'exchange_rate': exchange_rate,
                        'items': new_items,
                        'totals': {'usd': grand_usd, 'baht': grand_thb},
                        'group_customer_name': first_cust_name
                    },
                    'members': new_members,
                    'totals': {'usd': grand_usd, 'baht': grand_thb}
                }
                all_invoices.insert(0, new_record)
                found = True
                updated_item = new_record

                # Synchronize invoice counter
                num_part = re.sub(r'[^0-9]', '', clean_r_no)
                if num_part.isdigit():
                    num_val = int(num_part)
                    counter = load_json(INVOICE_COUNTER_FILE, {
                        "last_number": 0, "prefix": "INV ",
                        "last_visa_number": 0, "visa_prefix": "VISA ",
                        "last_passport_number": 0, "passport_prefix": "INV ",
                        "last_quote_number": 0, "quote_prefix": "QT "
                    })
                    if not isinstance(counter, dict):
                        counter = {}
                    if service_category == 'visa':
                        if num_val > safe_int(counter.get("last_visa_number", 0)):
                            counter["last_visa_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)
                    elif service_category == 'passport':
                        if num_val > safe_int(counter.get("last_passport_number", 0)):
                            counter["last_passport_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)
                    elif service_category in ['quote', 'quotation']:
                        if num_val > safe_int(counter.get("last_quote_number", 0)):
                            counter["last_quote_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)
                    else:
                        if num_val > safe_int(counter.get("last_number", 0)):
                            counter["last_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)

            save_json(SAVED_CUSTOMERS_FILE, all_invoices)
            self.send_json_response({'success': True, 'invoice': updated_item})
            return

        elif path == '/api/split_group':
            source_receipt_no = req_data.get('source_receipt_no', '').strip()
            split_members_data = req_data.get('split_members', [])
            new_receipt_no = req_data.get('new_receipt_no', '').strip()
            new_sender_name = req_data.get('new_sender_name', '').strip()
            new_travel_date = req_data.get('new_travel_date', '').strip()
            new_agency_company = req_data.get('new_agency_company', '').strip()
            service_category = req_data.get('service_category', 'visa').strip().lower()
            exchange_rate = safe_float(req_data.get('exchange_rate', 33.90), 33.90)

            if not source_receipt_no or not split_members_data:
                self.send_json_response({'success': False, 'error': 'Missing source_receipt_no or split_members'}, status=400)
                return

            if not new_receipt_no:
                new_receipt_no = increment_invoice_no(service_category)
            else:
                # Synchronize invoice counter if necessary
                num_part = re.sub(r'[^0-9]', '', new_receipt_no)
                if num_part.isdigit():
                    num_val = int(num_part)
                    counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV ", "last_visa_number": 0, "visa_prefix": "VISA "})
                    if not isinstance(counter, dict):
                        counter = {}
                    if service_category == 'visa':
                        if num_val > safe_int(counter.get("last_visa_number", 0)):
                            counter["last_visa_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)
                    else:
                        if num_val > safe_int(counter.get("last_number", 0)):
                            counter["last_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
            source_idx = -1
            source_item = None

            for i, item in enumerate(all_invoices):
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('receipt_no') or ''
                if r_no.strip().lower() == source_receipt_no.strip().lower():
                    source_idx = i
                    source_item = item
                    break

            if source_idx == -1 or not source_item:
                self.send_json_response({'success': False, 'error': f'Source group {source_receipt_no} not found'}, status=404)
                return

            split_names = [
                (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip().lower()
                for m in split_members_data
                if (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
            ]

            original_members = source_item.get('members', [])
            remaining_members = []
            moved_members = []

            for m in original_members:
                m_name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip().lower()
                if m_name in split_names:
                    matching_split = next((sm for sm in split_members_data if (sm.get('full_english_name') or sm.get('name') or sm.get('english_name') or '').strip().lower() == m_name), m)
                    moved_members.append(matching_split)
                    split_names.remove(m_name)
                else:
                    remaining_members.append(m)

            for sm in split_members_data:
                sm_name = (sm.get('full_english_name') or sm.get('name') or sm.get('english_name') or '').strip().lower()
                if sm_name in split_names:
                    moved_members.append(sm)
                    split_names.remove(sm_name)

            if not moved_members:
                self.send_json_response({'success': False, 'error': 'No valid members selected to split'}, status=400)
                return

            def process_members_and_items(members_list, rate):
                new_m_list = []
                new_i_list = []
                grand_u = 0.0
                for idx, m in enumerate(members_list, 1):
                    name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
                    if not name: continue
                    pass_no = (m.get('passport_no') or m.get('passport') or '-').strip()
                    nat = (m.get('nationality') or 'THAI').strip()
                    usd = float(m.get('usd', 0.0))
                    vip = float(m.get('vip', 0.0))
                    clearance = float(m.get('clearance_fee', 0.0) or m.get('clearance', 0.0))
                    permit = float(m.get('work_permit', 0.0))
                    car = float(m.get('car_fee', 0.0) or m.get('car', 0.0))
                    visa = float(m.get('visa_fee', 0.0) or m.get('visa', 0.0))
                    evisa = float(m.get('e_visa', 0.0) or m.get('evisa', 0.0))
                    overstay = float(m.get('overstay', 0.0) or m.get('fine_fee', 0.0) or m.get('fine', 0.0))
                    months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                    is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                    visa_status = 'issued' if is_issued else 'pending'

                    if usd == 0 and (vip or clearance or permit or car or visa or evisa or overstay):
                        usd = vip + clearance + permit + car + visa + evisa + overstay

                    grand_u += usd
                    new_m_list.append({
                        'full_english_name': name,
                        'english_name': name,
                        'name': name,
                        'passport_no': pass_no,
                        'nationality': nat,
                        'car_fee': car,
                        'visa_fee': visa,
                        'extension_months': months,
                        'months': months,
                        'visa_months': months,
                        'price': 0.0,
                        'e_visa': evisa,
                        'vip': vip,
                        'clearance_fee': clearance,
                        'work_permit': permit,
                        'overstay': overstay,
                        'fine_fee': overstay,
                        'usd': usd,
                        'qty': '1',
                        'visa_issued': is_issued,
                        'visa_status': visa_status
                    })
                    new_i_list.append({
                        'no': idx,
                        'description': name,
                        'qty': '1',
                        'extension_months': months,
                        'months': months,
                        'visa_months': months,
                        'e_visa': f"${evisa:.0f}" if evisa > 0 else '',
                        'vip': f"${vip:.0f}" if vip > 0 else '',
                        'overstay': f"${overstay:.0f}" if overstay > 0 else '',
                        'car_fee': f"${car:.0f}" if car > 0 else '',
                        'visa': f"${visa:.0f}" if visa > 0 else '',
                        'clearance_fee': f"${clearance:.0f}" if clearance > 0 else '',
                        'work_permit': f"${permit:.0f}" if permit > 0 else '',
                        'usd': usd,
                        'visa_issued': is_issued,
                        'visa_status': visa_status
                    })
                grand_t = grand_u * rate
                return new_m_list, new_i_list, grand_u, grand_t

            # Process remaining members for source group
            src_rate = float(source_item.get('group_data', {}).get('exchange_rate', exchange_rate))
            src_m_list, src_i_list, src_usd, src_thb = process_members_and_items(remaining_members, src_rate)
            src_pax = len(src_m_list)
            src_sender = source_item.get('sender_name') or source_item.get('group_info', {}).get('sender_name') or 'VIP Group'
            src_first_cust = src_m_list[0]['full_english_name'] if src_m_list else 'N/A'
            formatted_src_cust = format_group_customer_names(src_m_list) or src_first_cust

            source_item['members'] = src_m_list
            source_item['customer_name'] = f"{src_sender} ({src_pax} នាក់)" if src_pax > 0 else src_sender
            if 'customer' in source_item:
                source_item['customer']['full_english_name'] = f"GROUP: {src_sender} ({src_pax} នាក់)"
                source_item['customer']['sex'] = f"{src_pax} Pax"
            if 'group_info' in source_item:
                source_item['group_info']['customer_name'] = formatted_src_cust
                source_item['group_info']['pax_count'] = src_pax
            if 'group_data' in source_item:
                source_item['group_data']['items'] = src_i_list
                source_item['group_data']['totals'] = {'usd': src_usd, 'baht': src_thb}
                source_item['group_data']['group_customer_name'] = formatted_src_cust
            source_item['totals'] = {'usd': src_usd, 'baht': src_thb}

            # Create new invoice record for the split members
            new_sender = new_sender_name or src_sender
            new_tdate = format_display_date(new_travel_date) if new_travel_date else (source_item.get('travel_date') or datetime.datetime.now().strftime("%d-%m-%Y"))
            new_agency = new_agency_company if new_agency_company is not None else (source_item.get('agency_company') or '')
            new_m_list, new_i_list, new_usd, new_thb = process_members_and_items(moved_members, exchange_rate)
            new_pax = len(new_m_list)
            new_first_cust = new_m_list[0]['full_english_name'] if new_m_list else 'N/A'
            formatted_new_cust = format_group_customer_names(new_m_list) or new_first_cust

            new_invoice = {
                'id': str(uuid.uuid4()),
                'receipt_no': new_receipt_no,
                'service_category': service_category,
                'date_saved': datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                'travel_date': new_tdate,
                'sender': new_sender,
                'sender_name': new_sender,
                'agency_company': new_agency,
                'customer_name': f"{new_sender} ({new_pax} នាក់)" if new_pax > 0 else new_sender,
                'payment_status': 'UNPAID',
                'customer': {
                    'receipt_no': new_receipt_no,
                    'full_english_name': f"GROUP: {new_sender} ({new_pax} នាក់)",
                    'nationality': 'GROUP',
                    'agency_company': new_agency,
                    'travel_date': new_tdate,
                    'sex': f"{new_pax} Pax"
                },
                'group_info': {
                    'receipt_no': new_receipt_no,
                    'group_name': new_sender,
                    'sender_name': new_sender,
                    'customer_name': formatted_new_cust,
                    'travel_date': new_tdate,
                    'agency_company': new_agency,
                    'service_category': service_category,
                    'pax_count': new_pax
                },
                'group_data': {
                    'receipt_no': new_receipt_no,
                    'customer_name': new_sender,
                    'sender_name': new_sender,
                    'group_customer_name': formatted_new_cust,
                    'agency_company': new_agency,
                    'date_str': new_tdate,
                    'travel_date': new_tdate,
                    'exchange_rate': exchange_rate,
                    'items': new_i_list,
                    'totals': {'usd': new_usd, 'baht': new_thb}
                },
                'members': new_m_list,
                'totals': {'usd': new_usd, 'baht': new_thb}
            }

            all_invoices.insert(source_idx, new_invoice)
            save_json(SAVED_CUSTOMERS_FILE, all_invoices)

            self.send_json_response({
                'success': True,
                'new_receipt_no': new_receipt_no,
                'source_receipt_no': source_receipt_no,
                'new_count': new_pax,
                'remaining_count': src_pax,
                'remaining_members': src_m_list
            })
            return

        elif path in ['/api/restore_database', '/api/restore']:
            if isinstance(req_data, list):
                new_records = req_data
            else:
                new_records = req_data.get('records') or req_data.get('invoices') or []

            if not isinstance(new_records, list) or len(new_records) == 0:
                self.send_json_response({'success': False, 'error': 'No valid records provided'}, status=400)
                return

            save_json(SAVED_CUSTOMERS_FILE, new_records)

            # Auto calculate and sync counter
            max_inv = 0
            max_visa = 0
            for r in new_records:
                r_no = str(r.get('receipt_no') or r.get('group_data', {}).get('receipt_no') or r.get('customer', {}).get('receipt_no') or '').strip().upper()
                num_part = re.sub(r'[^0-9]', '', r_no)
                if num_part.isdigit():
                    num_val = int(num_part)
                    if r_no.startswith('VISA'):
                        if num_val > max_visa: max_visa = num_val
                    elif r_no.startswith('INV'):
                        if num_val > max_inv: max_inv = num_val

            counter = {
                'last_number': max_inv,
                'prefix': 'INV ',
                'last_visa_number': max_visa,
                'visa_prefix': 'VISA '
            }
            save_json(INVOICE_COUNTER_FILE, counter)

            self.send_json_response({'success': True, 'count': len(new_records), 'last_inv': max_inv, 'last_visa': max_visa})
            return

        elif path == '/api/save_supabase_config':
            new_url = req_data.get('supabase_url', '').strip()
            new_key = req_data.get('supabase_key', '').strip()
            cfg_path = os.path.join(BASE_DIR, 'supabase_config.json')
            try:
                with open(cfg_path, 'w', encoding='utf-8') as fcfg:
                    json.dump({'supabase_url': new_url, 'supabase_key': new_key}, fcfg, indent=2)
                # Seed current database to Supabase if configured
                all_recs = load_json(SAVED_CUSTOMERS_FILE, [])
                if supabase_db and supabase_db.is_configured() and all_recs:
                    threading.Thread(target=supabase_db.upsert_invoices, args=(all_recs,), daemon=True).start()
                self.send_json_response({'success': True, 'message': 'Supabase configuration saved!'})
            except Exception as se:
                self.send_json_response({'success': False, 'error': str(se)}, status=500)
            return

        elif path == '/api/sync_supabase':
            if not supabase_db or not supabase_db.is_configured():
                self.send_json_response({'success': False, 'error': 'Supabase is not configured'}, status=400)
                return
            all_recs = load_json(SAVED_CUSTOMERS_FILE, [])
            success = supabase_db.upsert_invoices(all_recs)
            cur_counter = load_json(INVOICE_COUNTER_FILE, {})
            if cur_counter:
                supabase_db.save_counters(cur_counter)
            self.send_json_response({'success': success, 'count': len(all_recs)})
            return

        elif path == '/api/save_telegram_config':
            token = req_data.get('bot_token', '').strip()
            chat_id = req_data.get('chat_id', '').strip()
            save_telegram_config(token, chat_id)
            if telegram_bot_listener:
                if telegram_bot_listener.running:
                    telegram_bot_listener.stop()
                if token:
                    telegram_bot_listener.start(token)
            self.send_json_response({'success': True})
            return

        elif path == '/api/toggle_telegram_listener':
            action = req_data.get('action', 'toggle')
            if telegram_bot_listener:
                if action == 'start' or (action == 'toggle' and not telegram_bot_listener.running):
                    telegram_bot_listener.start()
                elif action == 'stop' or (action == 'toggle' and telegram_bot_listener.running):
                    telegram_bot_listener.stop()
                status = telegram_bot_listener.get_status()
                self.send_json_response({'success': True, 'status': status})
            else:
                self.send_json_response({'success': False, 'error': 'Telegram listener unavailable'})
            return

        elif path == '/api/send_telegram_bot':
            b64_str = req_data.get('image', '')
            caption = req_data.get('caption', '')
            filename = req_data.get('filename', 'receipt.png')
            if not b64_str:
                self.send_json_response({'success': False, 'error': 'No image data provided'}, status=400)
                return

            if ',' in b64_str:
                b64_str = b64_str.split(',', 1)[1]

            img_bytes = base64.b64decode(b64_str.strip().replace(' ', '+'))
            temp_path = os.path.join(BASE_DIR, 'temp_telegram_share.png')
            with open(temp_path, 'wb') as f:
                f.write(img_bytes)

            cfg = get_telegram_config()
            res = send_telegram_photo_bot(cfg.get('bot_token', ''), cfg.get('chat_id', ''), temp_path, caption=caption)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

            if res.get('ok'):
                self.send_json_response({'success': True, 'message': 'បានផ្ញើរូបភាពវិក្កយបត្រទៅ Telegram រួចរាល់!'})
            else:
                msg = res.get('description') or res.get('error') or 'Telegram Bot API error'
                self.send_json_response({'success': False, 'error': msg})
            return

        elif path == '/api/send_driver_dispatch':
            driver_target = req_data.get('driver_target', '').strip()
            text = req_data.get('text', '').strip()
            image_urls = req_data.get('image_urls', [])

            cfg = get_telegram_config()
            bot_token = cfg.get('bot_token') or '8884318593:AAEipEVki9o1YFL0_8IYoUeSn3Xif4dlVOk'
            
            # Check if target is a Telegram Invite Link (e.g. https://t.me/+... or joinchat)
            is_invite_link = False
            invite_code = ''
            if '+' in driver_target or 'joinchat' in driver_target:
                is_invite_link = True
                if '+' in driver_target:
                    invite_code = driver_target.split('+')[-1].split('/')[0].split('?')[0].strip()
                elif 'joinchat/' in driver_target:
                    invite_code = driver_target.split('joinchat/')[-1].split('/')[0].split('?')[0].strip()

            # Check if we have an auto-discovered group ID from the bot joining the group(s)
            known_group_id = ''
            known_group_title = ''
            for g_dir in [DATA_DIR, BASE_DIR]:
                gf = os.path.join(g_dir, "known_telegram_groups.json")
                if os.path.exists(gf):
                    try:
                        with open(gf, "r", encoding="utf-8") as f_g:
                            kg = json.load(f_g)
                            # 1. Check if this exact link or invite code was mapped to a group
                            for cid, gdata in kg.items():
                                if isinstance(gdata, dict):
                                    if invite_code and gdata.get("invite_code") == invite_code:
                                        known_group_id = cid
                                        known_group_title = gdata.get("title", "")
                                        break
                                    if driver_target and gdata.get("link") == driver_target:
                                        known_group_id = cid
                                        known_group_title = gdata.get("title", "")
                                        break
                                    g_title = str(gdata.get("title", "")).strip().lower()
                                    d_clean = driver_target.replace('👥', '').replace('គ្រុប', '').replace('Telegram', '').replace('៖', '').strip().lower()
                                    if g_title and (g_title == d_clean or g_title in d_clean or d_clean in g_title):
                                        known_group_id = cid
                                        known_group_title = gdata.get("title", "")
                                        break

                            # 2. Fallback to latest discovered group if invite link without exact match
                            if not known_group_id and is_invite_link:
                                known_group_id = kg.get("latest_group_id", "")
                                if known_group_id and known_group_id in kg and isinstance(kg[known_group_id], dict):
                                    known_group_title = kg[known_group_id].get("title", "")

                            # If found, persist invite_code and link for this group
                            if known_group_id and is_invite_link:
                                if known_group_id in kg and isinstance(kg[known_group_id], dict):
                                    kg[known_group_id]["link"] = driver_target
                                    if invite_code:
                                        kg[known_group_id]["invite_code"] = invite_code
                                    try:
                                        with open(gf, "w", encoding="utf-8") as f_save:
                                            json.dump(kg, f_save, indent=2, ensure_ascii=False)
                                    except Exception:
                                        pass
                            break
                    except Exception:
                        pass

            # Determine target chat: Group ID, direct link, or username
            chat_id = ''
            if known_group_id:
                chat_id = known_group_id
            elif is_invite_link or ('http' in driver_target and not driver_target.startswith('@')):
                # Launch telegram directly to this group/invite on user desktop
                if invite_code:
                    try:
                        os.system(f'start "" "tg://join?invite={invite_code}"')
                    except Exception:
                        pass
                elif driver_target.startswith('http'):
                    try:
                        os.system(f'start "" "{driver_target}"')
                    except Exception:
                        pass

                self.send_json_response({
                    'success': True,
                    'is_direct_link': True,
                    'invite_code': invite_code,
                    'target_url': driver_target,
                    'message': 'បានចម្លងទិន្នន័យរួចរាល់! កំពុងបើកទៅកាន់ Telegram Group របស់អ្នក... សូមចុច Ctrl+V ដើម្បី Paste ផ្ញើក្នុង Group!'
                })
                return
            elif driver_target and (driver_target.startswith('-') or driver_target.isdigit() or (driver_target.startswith('@') and '/' not in driver_target)):
                chat_id = driver_target

            if not chat_id:
                # Under NO circumstances fallback to bot admin chat!
                self.send_json_response({
                    'success': False,
                    'error': 'សូមបញ្ចូល Link Telegram ឬ @username របស់អ្នកបើកបរ',
                    'can_open_tme': True
                })
                return

            # Support HTML formatting for bold (<b>...</b> or **...**)
            if '**' in text:
                escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped_text)
                res_text = send_telegram_text_bot(bot_token, chat_id, html_text, parse_mode='HTML')
                if not res_text.get('ok'):
                    res_text = send_telegram_text_bot(bot_token, chat_id, text)
            else:
                res_text = send_telegram_text_bot(bot_token, chat_id, text)
            photos_sent = 0
            for img_rel in image_urls:
                if not img_rel or not isinstance(img_rel, str):
                    continue
                clean_rel = img_rel.replace('/', os.sep).lstrip(os.sep)
                local_path = os.path.join(BASE_DIR, clean_rel)
                if os.path.exists(local_path):
                    send_telegram_photo_bot(bot_token, chat_id, local_path, caption=f"📍 ឯកសារ/ទីតាំងជើងឡាន #{photos_sent+1}")
                    photos_sent += 1

            if res_text.get('ok') or photos_sent > 0:
                target_display = known_group_title or chat_id
                self.send_json_response({
                    'success': True,
                    'bot_sent': True,
                    'message': f'បានបញ្ជូនទិន្នន័យ និងរូបភាព ({photos_sent} សន្លឹក) ចូលទៅក្នុងគ្រុប "{target_display}" រួចរាល់! 🚀',
                    'chat_id': chat_id
                })
            else:
                desc = res_text.get('description', 'Telegram error')
                self.send_json_response({'success': False, 'error': desc, 'can_open_tme': True})
            return

        elif path == '/api/open_telegram_dispatch':
            driver_target = req_data.get('driver_target', '').strip()
            text = req_data.get('text', '').strip()

            try:
                if '+' in driver_target or 'joinchat' in driver_target:
                    invite_code = driver_target.split('+')[-1].split('/')[0].split('?')[0].strip() if '+' in driver_target else driver_target.split('joinchat/')[-1].split('/')[0].split('?')[0].strip()
                    os.system(f'start "" "tg://join?invite={invite_code}"')
                elif driver_target.startswith('http'):
                    os.system(f'start "" "{driver_target}"')
                elif driver_target and not driver_target.startswith('-') and not driver_target.isdigit():
                    clean_u = driver_target.lstrip('@')
                    os.system(f'start "" "tg://resolve?domain={clean_u}"')
                elif text:
                    quoted = urllib.parse.quote(text)
                    os.system(f'start "" "tg://msg_url?text={quoted}"')
                else:
                    launch_telegram_desktop()
            except Exception as e:
                print("Error launching telegram:", e)
                launch_telegram_desktop()

            self.send_json_response({'success': True, 'message': 'បានបើកកម្មវិធី Telegram Desktop រួចរាល់!'})
            return

        elif path == '/api/open_images_folder':
            image_urls = req_data.get('image_urls', [])
            opened = False
            for img_rel in image_urls:
                if not img_rel:
                    continue
                clean_rel = img_rel.replace('/', os.sep).lstrip(os.sep)
                local_path = os.path.join(BASE_DIR, clean_rel)
                if os.path.exists(local_path):
                    try:
                        os.system(f'explorer.exe /select,"{local_path}"')
                        opened = True
                        break
                    except Exception:
                        pass
            if not opened:
                img_dir = os.path.join(BASE_DIR, 'telegram_images')
                if os.path.exists(img_dir):
                    os.system(f'explorer.exe "{img_dir}"')
                    opened = True
            self.send_json_response({'success': True, 'opened': opened})
            return

        elif path == '/api/record_telegram_message':
            text = req_data.get('text', '').strip()
            sender = req_data.get('sender', 'Telegram User').strip()
            date_str = req_data.get('date', datetime.datetime.now().strftime('%d/%m/%Y %H:%M'))
            images = req_data.get('images', [])
            if text or images:
                msg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
                if not os.path.exists(os.path.dirname(msg_file)):
                    msg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
                msgs = load_json(msg_file, [])
                if not any((m.get('text') == text and len(m.get('images', [])) == len(images)) for m in msgs):
                    msgs.insert(0, {
                        'id': int(datetime.datetime.now().timestamp() * 1000),
                        'text': text or "📷 រូបភាពភ្ជាប់ពី Telegram",
                        'sender': sender,
                        'date': date_str,
                        'timestamp': int(datetime.datetime.now().timestamp()),
                        'images': images
                    })
                    msgs = msgs[:100]
                    save_json(msg_file, msgs)
                self.send_json_response({'success': True, 'count': len(msgs)})
            else:
                self.send_json_response({'success': False, 'error': 'No text or images provided'}, status=400)
            return

        elif path == '/api/parse_flight_ticket':
            img_url = req_data.get('image_url', '').strip()
            data_url = req_data.get('data_url', '').strip()
            local_path = None

            if img_url:
                clean_rel = img_url.replace('/', os.sep).lstrip(os.sep)
                cand_path = os.path.join(BASE_DIR, clean_rel)
                if os.path.exists(cand_path):
                    local_path = cand_path
                else:
                    cand_path2 = os.path.join(DATA_DIR, clean_rel)
                    if os.path.exists(cand_path2):
                        local_path = cand_path2

            if not local_path and data_url and 'base64,' in data_url:
                try:
                    tmp_img_dir = os.path.join(BASE_DIR, 'telegram_images')
                    os.makedirs(tmp_img_dir, exist_ok=True)
                    tmp_f = os.path.join(tmp_img_dir, f"tmp_flight_{int(time.time()*1000)}.jpg")
                    b64_str = data_url.split('base64,')[1]
                    with open(tmp_f, 'wb') as f_out:
                        f_out.write(base64.b64decode(b64_str))
                    local_path = tmp_f
                except Exception:
                    pass

            if local_path and os.path.exists(local_path) and ocr_engine and getattr(ocr_engine, 'rapid_ocr', None):
                try:
                    res, _ = ocr_engine.rapid_ocr(local_path)
                    txt_lines = [t.strip() for b, t, s in (res or []) if t and t.strip()]
                    full_txt = ' '.join(txt_lines)

                    # 1. Extract Times
                    time_matches = re.findall(r'\b([012]?\d[:.][0-5]\d)\b', full_txt)
                    clean_times = [t.replace('.', ':').zfill(5) for t in time_matches if len(t.split(':')[0] if ':' in t else t.split('.')[0]) <= 2]

                    dep_time = clean_times[0] if len(clean_times) > 0 else ''
                    arr_time = clean_times[1] if len(clean_times) > 1 else dep_time

                    # Look for explicit arrival keyword in ticket
                    arr_m = re.search(r'(?:arrival|ถึง|landing|sai|rep|pnh|techo|เสียมเรียบ|เตโช|ភ្នំពេញ)[^\d\n\r]*?([012]?\d[:.][0-5]\d)', full_txt, re.IGNORECASE)
                    if arr_m:
                        arr_time = arr_m.group(1).replace('.', ':')
                        if len(arr_time) == 4: arr_time = '0' + arr_time

                    # 2. Extract Date
                    flight_date = ''
                    dmy_m = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](202\d)', full_txt)
                    if dmy_m:
                        flight_date = f"{dmy_m.group(3)}-{dmy_m.group(2).zfill(2)}-{dmy_m.group(1).zfill(2)}"
                    else:
                        en_m = re.search(r'(\d{1,2})\s*(?:st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]+(202\d)', full_txt, re.IGNORECASE)
                        if en_m:
                            month_map = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06','jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                            flight_date = f"{en_m.group(3)}-{month_map[en_m.group(2).lower()[:3]]}-{en_m.group(1).zfill(2)}"

                    # 3. Extract Flight Number
                    flight_no_m = re.search(r'\b([A-Z0-9]{2}[-\s]?\d{3,4})\b', full_txt)
                    flight_no = flight_no_m.group(1).replace(' ', '').replace('-', '') if flight_no_m else ''

                    self.send_json_response({
                        'success': True,
                        'arrival_time': arr_time,
                        'departure_time': dep_time,
                        'date': flight_date,
                        'flight_no': flight_no,
                        'full_text': full_txt[:300]
                    })
                    return
                except Exception as ex:
                    print("Parse flight ticket error:", ex)

            self.send_json_response({'success': False, 'error': 'Could not parse flight ticket'})
            return

        elif path == '/api/bookings':
            bk_file = os.path.join(DATA_DIR, 'saved_bookings.json')
            if not os.path.exists(os.path.dirname(bk_file)):
                bk_file = os.path.join(BASE_DIR, 'saved_bookings.json')

            bookings = req_data.get('bookings')
            booking = req_data.get('booking')

            current_bks = load_json(bk_file, [])
            if isinstance(bookings, list):
                save_json(bk_file, bookings)
                if supabase_db and supabase_db.is_configured():
                    try:
                        threading.Thread(target=supabase_db.save_bookings, args=(bookings,), daemon=True).start()
                    except Exception:
                        pass
                self.send_json_response({'success': True, 'count': len(bookings)})
            elif isinstance(booking, dict) and booking.get('id'):
                target_id = booking['id']
                idx = next((i for i, b in enumerate(current_bks) if b.get('id') == target_id), -1)
                if idx >= 0:
                    old_b = current_bks[idx]
                    same_cust = (str(old_b.get('customerName') or '').strip().lower() == str(booking.get('customerName') or '').strip().lower())
                    same_date = (str(old_b.get('date') or '').strip() == str(booking.get('date') or '').strip())
                    same_time = (str(old_b.get('time') or '').strip() == str(booking.get('time') or '').strip())
                    if same_cust and (same_date or same_time):
                        current_bks[idx] = booking
                    else:
                        max_num = 1000
                        for b in current_bks:
                            m = re.match(r'^BK-(\d+)$', str(b.get('id') or ''))
                            if m:
                                max_num = max(max_num, int(m.group(1)))
                        new_safe_id = f"BK-{max_num + 1}"
                        booking['id'] = new_safe_id
                        current_bks.insert(0, booking)
                else:
                    current_bks.insert(0, booking)
                save_json(bk_file, current_bks)
                self.send_json_response({'success': True, 'booking': booking})
            else:
                self.send_json_response({'success': False, 'error': 'Invalid booking data'}, status=400)
            return

        elif path == '/api/customers':
            cust_file = os.path.join(DATA_DIR, 'autorent_customers.json')
            if not os.path.exists(os.path.dirname(cust_file)):
                cust_file = os.path.join(BASE_DIR, 'autorent_customers.json')

            customers = req_data.get('customers')
            customer = req_data.get('customer')

            current_custs = load_json(cust_file, [])
            if isinstance(customers, list):
                save_json(cust_file, customers)
                self.send_json_response({'success': True, 'count': len(customers)})
            elif isinstance(customer, dict) and customer.get('name'):
                nm = customer['name'].strip()
                idx = next((i for i, c in enumerate(current_custs) if str(c.get('name') or '').strip().lower() == nm.lower()), -1)
                if idx >= 0:
                    current_custs[idx].update(customer)
                else:
                    if not customer.get('id'):
                        customer['id'] = f"CUST-{len(current_custs)+1:03d}"
                    current_custs.append(customer)
                save_json(cust_file, current_custs)
                self.send_json_response({'success': True, 'customer': customer, 'count': len(current_custs)})
            else:
                self.send_json_response({'success': False, 'error': 'Invalid customer data'}, status=400)
            return

        elif path == '/api/cars':
            car_file = os.path.join(DATA_DIR, 'autorent_cars.json')
            if not os.path.exists(os.path.dirname(car_file)):
                car_file = os.path.join(BASE_DIR, 'autorent_cars.json')
            cars = req_data.get('cars')
            if isinstance(cars, list):
                save_json(car_file, cars)
                self.send_json_response({'success': True, 'count': len(cars)})
            else:
                self.send_json_response({'success': False, 'error': 'Invalid cars data'}, status=400)
            return

        elif path == '/api/hidden_senders':
            hf = os.path.join(DATA_DIR, 'hidden_senders.json')
            if not os.path.exists(os.path.dirname(hf)):
                hf = os.path.join(BASE_DIR, 'hidden_senders.json')
            current_h = load_json(hf, [])
            if not isinstance(current_h, list):
                current_h = []
            if 'sender_name' in req_data:
                s_nm = str(req_data['sender_name']).strip()
                if s_nm and s_nm not in current_h:
                    current_h.append(s_nm)
                save_json(hf, current_h)
                self.send_json_response({'success': True, 'hidden_senders': current_h})
            else:
                h_list = req_data.get('hidden_senders', [])
                save_json(hf, h_list)
                self.send_json_response({'success': True, 'count': len(h_list)})
            return

        elif path == '/api/save_telegram_photo':
            data_url = req_data.get('data_url') or req_data.get('url') or ''
            file_name = req_data.get('name') or f"tg_photo_{int(time.time()*1000)}.jpg"
            if data_url and 'base64,' in data_url:
                try:
                    tg_img_dir = os.path.join(BASE_DIR, 'telegram_images')
                    os.makedirs(tg_img_dir, exist_ok=True)
                    head, b64_str = data_url.split('base64,', 1)
                    raw_bytes = base64.b64decode(b64_str)
                    clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '', file_name)
                    out_path = os.path.join(tg_img_dir, clean_name)
                    with open(out_path, 'wb') as f:
                        f.write(raw_bytes)
                    web_url = f"/telegram_images/{clean_name}"
                    self.send_json_response({'success': True, 'url': web_url, 'name': clean_name})
                    return
                except Exception as e:
                    self.send_json_response({'success': False, 'error': str(e)}, status=500)
                    return
            self.send_json_response({'success': False, 'error': 'No valid base64 image data provided'}, status=400)
            return

        elif path == '/api/delete_telegram_message':
            msg_id = req_data.get('id')
            msg_ids = req_data.get('ids', [])
            msg_text = (req_data.get('text') or '').strip()
            clear_all = req_data.get('all', False)

            tg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
            if not os.path.exists(tg_file):
                tg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
            msgs = load_json(tg_file, [])
            orig_len = len(msgs)

            if clear_all:
                msgs = []
            elif msg_ids and isinstance(msg_ids, list):
                del_set = set(str(x) for x in msg_ids if x is not None)
                msgs = [m for m in msgs if str(m.get('id')) not in del_set]
            elif msg_id is not None:
                msgs = [m for m in msgs if str(m.get('id')) != str(msg_id)]
            elif msg_text:
                msgs = [m for m in msgs if m.get('text', '').strip() != msg_text]

            save_json(tg_file, msgs)
            self.send_json_response({'success': True, 'deleted': orig_len - len(msgs), 'remaining': len(msgs), 'messages': msgs})
            return

        self.send_json_response({'error': 'Invalid endpoint'}, status=404)


    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

def download_telegram_photo_file(token, file_id, update_id):
    """
    Downloads a photo from Telegram Bot API using file_id and saves to telegram_images/ folder.
    Returns the relative web path: /telegram_images/tg_photo_<update_id>_<short_id>.jpg
    """
    try:
        tg_img_dir = os.path.join(BASE_DIR, 'telegram_images')
        os.makedirs(tg_img_dir, exist_ok=True)

        # 1. Get file path from Telegram
        get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        req = urllib.request.Request(get_file_url, headers={'User-Agent': 'ImvoiBotPoller/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            f_data = json.loads(resp.read().decode('utf-8'))

        if not f_data.get('ok') or not f_data.get('result', {}).get('file_path'):
            return None

        file_path = f_data['result']['file_path']
        ext = os.path.splitext(file_path)[1].lower() or '.jpg'
        if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            ext = '.jpg'

        clean_file_id = re.sub(r'[^a-zA-Z0-9]', '', str(file_id))[:10]
        filename = f"tg_photo_{update_id}_{clean_file_id}{ext}"
        dest_path = os.path.join(tg_img_dir, filename)

        # 2. Download file content
        dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        req_dl = urllib.request.Request(dl_url, headers={'User-Agent': 'ImvoiBotPoller/1.0'})
        with urllib.request.urlopen(req_dl, timeout=20) as resp_dl:
            img_bytes = resp_dl.read()
            with open(dest_path, 'wb') as f:
                f.write(img_bytes)

        return f"/telegram_images/{filename}"
    except Exception as e:
        print(f"[TelegramBotPoller] Error downloading photo {file_id}: {e}")
        return None

def detect_photo_category(caption_text, img_path=None):
    text_lower = (caption_text or "").lower()
    if any(k in text_lower for k in ['flight', '✈', '✈️', 'dmk', 'bkk', 'sai', 'airasia', 'air', 'fd', 'fd-', 'fd ', 'we', 'sl', 'v9', 'k6', 'pg', 'tg', 'qv', 'ហោះហើរ', 'សំបុត្រ', 'ตั๋วเครื่องบิน', 'ไฟลท์', 'ขาเข้า', 'ขาออก', 'สนามบิน', 'airport', 'pnr', 'boarding']):
        return 'សំបុត្រយន្តហោះ'
    elif any(k in text_lower for k in ['passport', 'បាសស្ព័រ', 'ប៉ាស្ព័រ', 'លិខិតឆ្លងដែន', 'พาสปอร์ต', 'pass', 'pp']):
        return 'ប៉ាស្ព័រ'
    elif any(k in text_lower for k in ['alphard', 'hiace', 'staria', 'ឡានជួល']):
        return 'រូបឡាន'
    
    if img_path and os.path.exists(img_path):
        try:
            from PIL import Image
            with Image.open(img_path) as im:
                w, h = im.size
                aspect = max(w, h) / max(min(w, h), 1)
                if h > w and aspect >= 1.62:
                    if any(k in text_lower for k in ['flight', '✈', 'dmk', 'sai', 'bkk', 'airasia', 'ขาเข้า', 'ขาออก', 'pnr']):
                        return 'សំបុត្រយន្តហោះ'
                elif 1.20 <= aspect <= 1.58:
                    return 'ប៉ាស្ព័រ'
        except Exception:
            pass
    # In VIP border/airport transport system, default customer photos without car/flight text are passports
    return 'ប៉ាស្ព័រ'

def start_telegram_bot_message_poller():
    """Continuously polls Telegram Bot for incoming text, photos, and photo captions and stores them in received_telegram_messages.json"""
    def _poll_thread():
        token = "8884318593:AAEipEVki9o1YFL0_8IYoUeSn3Xif4dlVOk"
        cfg = get_telegram_config()
        if cfg and cfg.get("bot_token"):
            token = cfg.get("bot_token")
        
        offset = 0
        msg_file = os.path.join(DATA_DIR, 'received_telegram_messages.json')
        if not os.path.exists(os.path.dirname(msg_file)):
            msg_file = os.path.join(BASE_DIR, 'received_telegram_messages.json')
            
        print(f"[TelegramBotPoller] Live message & photo monitor active for token: {token[:12]}...")
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=20"
                req = urllib.request.Request(url, headers={'User-Agent': 'ImvoiBotPoller/1.0'})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get('ok') and data.get('result'):
                        for u in data['result']:
                            offset = max(offset, u['update_id'] + 1)

                            # 1. Detect chat migration from basic group to supergroup
                            msg_obj = u.get('message') or u.get('channel_post') or {}
                            migrate_to = msg_obj.get('migrate_to_chat_id')
                            if migrate_to:
                                old_c_id = str((msg_obj.get('chat') or {}).get('id', ''))
                                _handle_chat_migration(old_c_id, str(migrate_to))

                            # 2. Detect & remember any group / supergroup
                            chat_candidate = None
                            if u.get('my_chat_member'):
                                chat_candidate = u['my_chat_member'].get('chat')
                            elif msg_obj.get('chat'):
                                chat_candidate = msg_obj.get('chat')

                            if chat_candidate and str(chat_candidate.get('type', '')).lower() in ['group', 'supergroup', 'channel']:
                                grp_id = str(chat_candidate.get('id', ''))
                                grp_title = chat_candidate.get('title') or 'Telegram Group'
                                try:
                                    for g_dir in [DATA_DIR, BASE_DIR]:
                                        gf = os.path.join(g_dir, "known_telegram_groups.json")
                                        kg = {}
                                        if os.path.exists(gf):
                                            try:
                                                with open(gf, "r", encoding="utf-8") as f_g:
                                                    kg = json.load(f_g)
                                            except Exception:
                                                kg = {}
                                        to_remove = [k for k, v in kg.items() if k != "latest_group_id" and isinstance(v, dict) and v.get("title") == grp_title and k != grp_id and grp_id.startswith("-100")]
                                        for rk in to_remove:
                                            del kg[rk]
                                        old_link = (kg.get(grp_id) or {}).get('link', '')
                                        old_code = (kg.get(grp_id) or {}).get('invite_code', '')
                                        kg[grp_id] = {
                                            "id": grp_id,
                                            "title": grp_title,
                                            "link": old_link,
                                            "invite_code": old_code,
                                            "updated_at": datetime.datetime.now().isoformat()
                                        }
                                        kg["latest_group_id"] = grp_id
                                        with open(gf, "w", encoding="utf-8") as f_g:
                                            json.dump(kg, f_g, indent=2, ensure_ascii=False)
                                except Exception:
                                    pass

                            m = msg_obj
                            if not m:
                                continue

                            chat_obj = m.get('chat') or {}
                            c_id_str = str(chat_obj.get('id', '')).strip()
                            c_type = str(chat_obj.get('type', '')).lower()
                            txt = (m.get('text') or m.get('caption') or '').strip()

                            # 3. Handle /start command in group with confirmation
                            if txt.lower().startswith('/start') and c_type in ['group', 'supergroup']:
                                grp_title = chat_obj.get('title') or 'Telegram Group'
                                greet_msg = f"🤖 សួស្តី! Bot ការកក់ឡាន បានភ្ជាប់ជាមួយគ្រុប «{grp_title}» ដោយជោគជ័យ! 🎉\n\nឥឡូវនេះ លោកអ្នកអាចជ្រើសរើសគ្រុបនេះក្នុងប្រព័ន្ធ Web App ដើម្បីបញ្ជូនទិន្នន័យការងារជើងឡានបានភ្លាមៗ។"
                                send_telegram_text_bot(token, c_id_str, greet_msg)
                                continue

                            # 🛑 Chat Filter: allow configured chat OR any known connected groups
                            cfg_tg = get_telegram_config()
                            allowed_chat_id = str(cfg_tg.get("chat_id", "")).strip()
                            allowed_chat_ids = [str(x).strip() for x in cfg_tg.get("allowed_chat_ids", []) if str(x).strip()]
                            if allowed_chat_id and allowed_chat_id not in allowed_chat_ids:
                                allowed_chat_ids.append(allowed_chat_id)

                            is_known = False
                            for g_dir in [DATA_DIR, BASE_DIR]:
                                gf = os.path.join(g_dir, "known_telegram_groups.json")
                                if os.path.exists(gf):
                                    try:
                                        with open(gf, "r", encoding="utf-8") as f_g:
                                            if c_id_str in json.load(f_g):
                                                is_known = True
                                                break
                                    except Exception:
                                        pass

                            if allowed_chat_ids and c_id_str not in allowed_chat_ids and not is_known:
                                continue

                            txt = (m.get('text') or m.get('caption') or '').strip()
                            photos = m.get('photo')
                            doc = m.get('document')
                            has_img = bool(photos) or (doc and (doc.get('mime_type') or '').startswith('image/'))

                            # Skip if neither text nor image
                            if not txt and not has_img:
                                continue

                            # Forward info detection
                            forward_from = m.get('forward_from')
                            forward_chat = m.get('forward_from_chat')
                            forward_sender_name = m.get('forward_sender_name')
                            f_origin = ''
                            if forward_from:
                                f_origin = (forward_from.get('first_name', '') + ' ' + (forward_from.get('last_name') or '')).strip()
                            elif forward_chat and forward_chat.get('title'):
                                f_origin = forward_chat.get('title')
                            elif forward_sender_name:
                                f_origin = forward_sender_name

                            base_sender = ""
                            if m.get('from'):
                                base_sender = f"{m['from'].get('first_name', '')} {m['from'].get('last_name', '')}".strip()
                                if not base_sender and m['from'].get('username'):
                                    base_sender = f"@{m['from']['username']}"
                            elif m.get('chat') and m['chat'].get('title'):
                                base_sender = m['chat']['title']

                            if f_origin and base_sender:
                                sender = f"{base_sender} (Forwarded from {f_origin})"
                            elif f_origin:
                                sender = f"Forwarded from {f_origin}"
                            else:
                                sender = base_sender or 'Telegram User'

                            ts = m.get('date', int(datetime.datetime.now().timestamp()))
                            dt_str = datetime.datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M')

                            img_list = []
                            cat = detect_photo_category(txt)

                            # Handle photos (grab highest resolution)
                            if photos and len(photos) > 0:
                                best_photo = photos[-1]
                                f_id = best_photo.get('file_id')
                                if f_id:
                                    img_url = download_telegram_photo_file(token, f_id, u['update_id'])
                                    if img_url:
                                        # Refine category with actual downloaded image dimensions
                                        full_local_path = os.path.join(BASE_DIR, img_url.lstrip('/'))
                                        cat = detect_photo_category(txt, full_local_path)
                                        img_list.append({
                                            'id': f"IMG-TG-{u['update_id']}",
                                            'name': f"telegram_photo_{u['update_id']}.jpg",
                                            'category': cat,
                                            'url': img_url,
                                            'date': dt_str
                                        })
                            elif doc and (doc.get('mime_type') or '').startswith('image/'):
                                f_id = doc.get('file_id')
                                if f_id:
                                    img_url = download_telegram_photo_file(token, f_id, u['update_id'])
                                    if img_url:
                                        full_local_path = os.path.join(BASE_DIR, img_url.lstrip('/'))
                                        cat = detect_photo_category(txt, full_local_path)
                                        img_list.append({
                                            'id': f"IMG-TG-{u['update_id']}",
                                            'name': doc.get('file_name') or f"telegram_doc_{u['update_id']}.jpg",
                                            'category': cat,
                                            'url': img_url,
                                            'date': dt_str
                                        })

                            if not txt and img_list:
                                txt = f"📷 រូបភាព ({cat}) ពី {sender}"

                            msgs = load_json(msg_file, [])
                            is_dup = any(
                                str(item.get('id')) == str(u['update_id']) or
                                (img_list and any(
                                    any(img.get('url') == ex_img.get('url') for ex_img in item.get('images', []))
                                    for img in img_list
                                ))
                                for item in msgs
                            )
                            if not is_dup:
                                mg_id = m.get('media_group_id')
                                merged_into_recent = False

                                # Check if there is an existing message from the same sender within 3 minutes (same batch/conversation)
                                for ex_msg in msgs[:15]:
                                    same_mg = mg_id and ex_msg.get('media_group_id') == mg_id
                                    same_sender_time = (ex_msg.get('sender') == sender and abs(ts - ex_msg.get('timestamp', ts)) <= 240)
                                    if same_mg or same_sender_time:
                                        # 1. Merge images
                                        if img_list:
                                            if 'images' not in ex_msg or not isinstance(ex_msg['images'], list):
                                                ex_msg['images'] = []
                                            for new_img in img_list:
                                                if not any(e_img.get('url') == new_img.get('url') for e_img in ex_msg['images']):
                                                    ex_msg['images'].append(new_img)
                                        
                                        # 2. Merge texts intelligently
                                        ex_text = (ex_msg.get('text') or '').strip()
                                        new_text = (txt or '').strip()
                                        is_ex_placeholder = not ex_text or ex_text.startswith('📷 រូបភាព') or ex_text.startswith('📘 រូបប៉ាស្ព័រ')
                                        is_new_placeholder = not new_text or new_text.startswith('📷 រូបភាព') or new_text.startswith('📘 រូបប៉ាស្ព័រ')

                                        if is_ex_placeholder and not is_new_placeholder:
                                            ex_msg['text'] = new_text
                                        elif not is_ex_placeholder and not is_new_placeholder and new_text != ex_text:
                                            if new_text not in ex_text and ex_text not in new_text:
                                                ex_msg['text'] = f"{ex_text}\n\n{new_text}"
                                        
                                        ex_msg['timestamp'] = max(ts, ex_msg.get('timestamp', ts))
                                        ex_msg['date'] = dt_str
                                        if mg_id and not ex_msg.get('media_group_id'):
                                            ex_msg['media_group_id'] = mg_id
                                        merged_into_recent = True
                                        break

                                if not merged_into_recent:
                                    new_entry = {
                                        'id': u['update_id'],
                                        'text': txt,
                                        'sender': sender,
                                        'date': dt_str,
                                        'timestamp': ts,
                                        'media_group_id': mg_id,
                                        'images': img_list
                                    }
                                    msgs.insert(0, new_entry)

                                msgs = msgs[:100]
                                save_json(msg_file, msgs)
                                print(f"[TelegramBotPoller] ⚡ Received/Updated message from {sender} (Total images: {len(msgs[0].get('images', []))}): {txt[:35]}...")
            except Exception:
                pass
            time.sleep(3)

    t = threading.Thread(target=_poll_thread, daemon=True)
    t.start()

def main():
    global PORT
    httpd = None
    env_port = os.environ.get('PORT')
    ports = [int(env_port)] if env_port else [8000, 8080, 8001, 8888]

    # 1. First check if Imvoi server is already running on any of these ports
    for p in ports:
        try:
            req = urllib.request.Request(f"http://localhost:{p}/api/telegram_bot_status")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    print(f"[*] Imvoi server is already running on http://localhost:{p}")
                    try:
                        webbrowser.open(f"http://localhost:{p}")
                    except Exception:
                        pass
                    return
        except Exception:
            pass

    # 2. Bind server exclusively to available port
    for p in ports:
        try:
            httpd = SafeThreadingHTTPServer(("", p), ImvoiWebHandler)
            PORT = p
            break
        except OSError:
            continue

    if httpd is None:
        print("❌ Error: Could not bind server to any port (8000, 8001, 8080, 8888).")
        return

    print("=" * 60)
    print(f"Launching Imvoi Web Server on http://localhost:{PORT}")
    print("=" * 60)

    try:
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass

    print(f"Server Ready! Access in browser: http://localhost:{PORT}")

    # Start single unified Telegram listener (avoids polling conflict)
    if telegram_bot_listener:
        try:
            telegram_bot_listener.start()
        except Exception as e:
            print("[TelegramBotListener] Start notice:", e)
            start_telegram_bot_message_poller()
    else:
        start_telegram_bot_message_poller()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
