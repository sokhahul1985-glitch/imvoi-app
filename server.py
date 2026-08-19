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
from PIL import Image

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

try:
    from telegram_utils import (
        get_telegram_config, save_telegram_config, send_telegram_photo_bot,
        send_telegram_text_bot, get_telegram_bot_info, telegram_bot_listener
    )
except Exception as e:
    def get_telegram_config(): return {"bot_token": "", "chat_id": ""}
    def save_telegram_config(b, c): pass
    def send_telegram_photo_bot(b, c, p, caption=""): return {"ok": False, "description": "telegram_utils unavailable"}
    def send_telegram_text_bot(b, c, text): return {"ok": False, "description": "telegram_utils unavailable"}
    def get_telegram_bot_info(t): return {"ok": False}
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
WEB_DIR = BASE_DIR

def load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
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
    counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV ", "last_visa_number": 0, "visa_prefix": "VISA "})
    cat = (category or 'car').lower().strip()
    
    if cat == 'visa':
        prefix = counter.get("visa_prefix", "VISA ")
        nums = []
        for item in data:
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
    else:
        prefix = counter.get("prefix", "INV ")
        nums = []
        for item in data:
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
    counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV ", "last_visa_number": 0, "visa_prefix": "VISA "})
    num_part = int(re.sub(r'[^0-9]', '', next_no))
    if cat == 'visa':
        counter["last_visa_number"] = num_part
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
                data.pop(idx)
                save_json(SAVED_CUSTOMERS_FILE, data)
                self.send_json_response({'success': True})
                return

        # 2. Match by id, receipt_no, passport_no, or customer_name
        filtered = []
        found = False
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
                continue
            filtered.append(item)

        if found:
            save_json(SAVED_CUSTOMERS_FILE, filtered)
            self.send_json_response({'success': True})
            return

        # 3. Fallback: numeric receipt_no as index
        if receipt_no.isdigit():
            idx = int(receipt_no)
            if 0 <= idx < len(data):
                data.pop(idx)
                save_json(SAVED_CUSTOMERS_FILE, data)
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

        elif path == '/api/next_no':
            cat = query.get('category', ['car'])[0]
            self.send_json_response({'success': True, 'next_no': get_next_invoice_no(cat)})
            return

        elif path == '/api/set_counter':
            cat = query.get('category', ['car'])[0].lower().strip()
            num_str = query.get('number', ['0'])[0]
            num = int(re.sub(r'[^0-9]', '', str(num_str)) or 0)
            counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV ", "last_visa_number": 0, "visa_prefix": "VISA "})
            if cat == 'visa':
                counter["last_visa_number"] = num
            else:
                counter["last_number"] = num
            save_json(INVOICE_COUNTER_FILE, counter)
            self.send_json_response({'success': True, 'category': cat, 'last_number': num, 'next_no': get_next_invoice_no(cat)})
            return

        elif path == '/api/invoice':
            receipt_no = query.get('no', [''])[0].strip().lower().replace('🛂', '').strip()
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            target = None
            for item in data:
                r_no = (item.get('receipt_no') or item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or item.get('passport_no') or item.get('id') or '').strip().lower().replace('🛂', '').strip()
                if r_no == receipt_no or (item.get('passport_no') and item.get('passport_no').strip().lower() == receipt_no):
                    target = item
                    break
            if target:
                self.send_json_response({'success': True, 'invoice': target})
            else:
                self.send_json_response({'success': False, 'error': 'Invoice not found'}, status=404)
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

        elif path == '/api/latest_telegram_scans':
            query_params = urllib.parse.parse_qs(parsed.query)
            since_id = query_params.get('since', [None])[0]
            scans = telegram_bot_listener.get_latest_scans(since_id) if telegram_bot_listener else []
            self.send_json_response({'success': True, 'scans': scans})
            return


        # Serve static web files
        if path == '/assets/css/styles.css':
            css_path = os.path.join(BASE_DIR, 'assets', 'css', 'styles.css')
            if os.path.exists(css_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/css; charset=utf-8')
                self.end_headers()
                with open(css_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        if path == '/' or path == '':
            self.path = '/index.html'

        return super().do_GET()

    def do_POST(self):
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
                name = m.get('name', '').strip()
                if not name: continue
                pass_no = m.get('passport', '').strip()
                nat = m.get('nationality', 'THAI').strip()
                vip = float(m.get('vip', 0))
                clearance = float(m.get('clearance_fee', m.get('clearance', 0)))
                permit = float(m.get('work_permit', 0))
                car = float(m.get('car_fee', m.get('car', 0)))
                visa = float(m.get('visa_fee', m.get('visa', 0)))
                evisa = float(m.get('evisa', m.get('e_visa', 0)))
                overstay = float(m.get('overstay', m.get('fine_fee', m.get('fine', 0))))
                months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                visa_status = 'issued' if is_issued else 'pending'

                row_usd = vip + clearance + permit + car + visa + evisa + overstay
                grand_usd += row_usd

                members.append({
                    'full_english_name': name,
                    'english_name': name,
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
                    'usd': row_usd,
                    'qty': '1',
                    'visa_issued': is_issued,
                    'visa_status': visa_status
                })

                items.append({
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
                    'usd': row_usd,
                    'visa_issued': is_issued,
                    'visa_status': visa_status
                })

            pax_count = len(members)
            grand_thb = grand_usd * exchange_rate
            formatted_cust_name = format_group_customer_names(members) or customer_name or (members[0]['full_english_name'] if members else group_name)
            service_category = req_data.get('service_category', 'car')

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

                    exchange_rate = float(item.get('group_data', {}).get('exchange_rate', 33.90))
                    new_members = []
                    new_items = []
                    grand_usd = 0.0

                    for idx, m in enumerate(members_data, 1):
                        name = (m.get('full_english_name') or m.get('name') or m.get('english_name') or '').strip()
                        if not name:
                            continue
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

                        grand_usd += usd

                        new_members.append({
                            'full_english_name': name,
                            'english_name': name,
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

                        new_items.append({
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

                    grand_thb = grand_usd * exchange_rate
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
                exchange_rate = float(req_data.get('exchange_rate', 33.90))
                service_category = req_data.get('service_category', 'car')
                new_members = []
                new_items = []
                grand_usd = 0.0

                for idx_m, m in enumerate(members_data):
                    m_name = m.get('full_english_name') or m.get('name', '')
                    if not m_name:
                        continue
                    evisa = float(m.get('e_visa') or m.get('evisa') or 0)
                    vip = float(m.get('vip') or 0)
                    clearance = float(m.get('clearance_fee') or m.get('clearance') or 0)
                    permit = float(m.get('work_permit') or m.get('permit') or 0)
                    car = float(m.get('car_fee') or m.get('car') or 0)
                    visa = float(m.get('visa_fee') or m.get('visa') or 0)
                    overstay = float(m.get('overstay') or m.get('fine_fee') or m.get('fine') or 0)
                    months = str(m.get('extension_months') or m.get('months') or m.get('visa_months') or '').strip()
                    is_issued = m.get('visa_issued') in [True, 'true', 'True', 1, '1'] or m.get('visa_status') == 'issued' or m.get('status') == 'issued'
                    visa_status = 'issued' if is_issued else 'pending'
                    usd = float(m.get('usd') or 0)
                    if usd == 0:
                        usd = evisa + vip + clearance + permit + car + visa + overstay

                    grand_usd += usd
                    new_members.append({
                        'full_english_name': m_name,
                        'name': m_name,
                        'extension_months': months,
                        'months': months,
                        'visa_months': months,
                        'e_visa': evisa,
                        'vip': vip,
                        'clearance_fee': clearance,
                        'work_permit': permit,
                        'car_fee': car,
                        'visa_fee': visa,
                        'overstay': overstay,
                        'fine_fee': overstay,
                        'usd': usd,
                        'qty': '1',
                        'visa_issued': is_issued,
                        'visa_status': visa_status
                    })
                    new_items.append({
                        'no': idx_m + 1,
                        'description': m_name,
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

                grand_thb = grand_usd * exchange_rate
                pax_count = len(new_members)
                first_cust_name = new_members[0]['full_english_name'] if new_members else 'N/A'
                group_name = group_name_input or sender_name or 'VIP Group'

                clean_r_no = req_data.get('receipt_no', '').strip()
                if not clean_r_no:
                    clean_r_no = increment_invoice_no(service_category)
                else:
                    if service_category == 'visa' and not (clean_r_no.upper().startswith('VISA') or clean_r_no.upper().startswith('INV')):
                        clean_r_no = f"VISA {clean_r_no.lstrip('#').strip()}"
                    elif service_category != 'visa' and not (clean_r_no.upper().startswith('INV') or clean_r_no.upper().startswith('CAR')):
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
                        'sex': f"{pax_count} Pax"
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
            exchange_rate = float(req_data.get('exchange_rate', 33.90))

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
                    if service_category == 'visa':
                        if num_val > counter.get("last_visa_number", 0):
                            counter["last_visa_number"] = num_val
                            save_json(INVOICE_COUNTER_FILE, counter)
                    else:
                        if num_val > counter.get("last_number", 0):
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

        self.send_json_response({'error': 'Invalid endpoint'}, status=404)


    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

def main():
    global PORT
    httpd = None
    env_port = os.environ.get('PORT')
    ports = [int(env_port)] if env_port else [8080, 8888, 8000, 8001]

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

    if telegram_bot_listener:
        try:
            telegram_bot_listener.start()
        except Exception as e:
            print("[TelegramBotListener] Start notice:", e)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
