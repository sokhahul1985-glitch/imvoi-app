"""
CMP Golden Mekong Commercial Service - Instant Web Application Server
Runs zero-config Web Server on http://localhost:8000 with Multipart & Base64 AI OCR Engine.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import webbrowser
import base64
import io
import re
from PIL import Image

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
    from telegram_utils import get_telegram_config, save_telegram_config, send_telegram_photo_bot
except Exception as e:
    def get_telegram_config(): return {"bot_token": "", "chat_id": ""}
    def save_telegram_config(b, c): pass
    def send_telegram_photo_bot(b, c, p, caption=""): return {"ok": False, "description": "telegram_utils unavailable"}


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

def get_next_invoice_no():
    counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV "})
    next_num = counter.get("last_number", 0) + 1
    prefix = counter.get("prefix", "INV ")
    return f"{prefix}{next_num:05d}"

def increment_invoice_no():
    counter = load_json(INVOICE_COUNTER_FILE, {"last_number": 0, "prefix": "INV "})
    counter["last_number"] = counter.get("last_number", 0) + 1
    save_json(INVOICE_COUNTER_FILE, counter)
    prefix = counter.get("prefix", "INV ")
    return f"{prefix}{counter['last_number']:05d}"

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
        cand_name = f"{sur} {given}".strip()
        cleaned_cand = clean_person_name(cand_name)
        if cleaned_cand:
            return cleaned_cand

    # Try extracted full english name or others
    candidates = [
        data.get('full_english_name'),
        data.get('thai_name'),
        data.get('khmer_name'),
        f"{sur} {given}".strip(),
        given,
        sur
    ]

    for cand in candidates:
        if not cand:
            continue
        cleaned = clean_person_name(cand) if not (data.get('thai_name') and cand == data.get('thai_name')) and not (data.get('khmer_name') and cand == data.get('khmer_name')) else cand.strip()
        if cleaned:
            return cleaned

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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API Routes
        if path in ['/api/invoices', '/api/get_database']:
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            self.send_json_response({'success': True, 'records': data, 'invoices': data})
            return

        elif path == '/api/next_no':
            self.send_json_response({'success': True, 'next_no': get_next_invoice_no()})
            return

        elif path == '/api/receipt':
            receipt_no = query.get('no', [''])[0].strip().lower()
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            target = None
            for item in data:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
                    target = item
                    break
            if target:
                self.send_json_response({'success': True, 'invoice': target})
            else:
                self.send_json_response({'success': False, 'error': 'Invoice not found'}, status=404)
            return

        elif path == '/api/toggle_status':
            receipt_no = query.get('no', [''])[0].strip().lower()
            new_status = query.get('status', ['UNPAID'])[0].upper()
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            found = False
            for item in data:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
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
            return

        elif path == '/api/delete':
            receipt_no = query.get('no', [''])[0].strip().lower()
            data = load_json(SAVED_CUSTOMERS_FILE, [])
            filtered = []
            found = False
            for item in data:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
                    found = True
                    continue
                filtered.append(item)
            if found:
                save_json(SAVED_CUSTOMERS_FILE, filtered)
                self.send_json_response({'success': True})
            else:
                self.send_json_response({'success': False, 'error': 'Receipt not found'}, status=404)
            return

        elif path == '/api/delete_member':
            receipt_no = query.get('no', [''])[0].strip().lower()
            try:
                m_idx = int(query.get('index', [-1])[0])
            except Exception:
                m_idx = -1

            data = load_json(SAVED_CUSTOMERS_FILE, [])
            found = False
            for item in data:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
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
        body_bytes = self.rfile.read(length)
        try:
            req_data = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            req_data = {}

        if path == '/api/save_group':
            group_name = req_data.get('group_name', 'VIP Group').strip()
            customer_name = req_data.get('customer_name', '').strip()
            agency_company = req_data.get('agency_company', '').strip()
            travel_date = req_data.get('travel_date', '').strip()
            exchange_rate = float(req_data.get('exchange_rate', 33.90))
            payment_status = req_data.get('payment_status', 'UNPAID').upper()
            members_raw = req_data.get('members', [])

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

                row_usd = vip + clearance + permit + car + visa + evisa
                grand_usd += row_usd

                members.append({
                    'full_english_name': name,
                    'english_name': name,
                    'passport_no': pass_no,
                    'nationality': nat,
                    'car_fee': car,
                    'visa_fee': visa,
                    'price': 0.0,
                    'e_visa': evisa,
                    'vip': vip,
                    'clearance_fee': clearance,
                    'work_permit': permit,
                    'usd': row_usd,
                    'qty': '1'
                })

                items.append({
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

            pax_count = len(members)
            grand_thb = grand_usd * exchange_rate

            new_invoice = {
                'date_saved': urllib.parse.unquote(req_data.get('date_saved', '')),
                'customer': {
                    'full_english_name': f"GROUP: {group_name} ({pax_count} Pax)",
                    'nationality': 'GROUP',
                    'sex': f"{pax_count} Pax",
                    'receipt_no': receipt_no
                },
                'payment_status': payment_status,
                'group_info': {
                    'group_name': group_name,
                    'sender_name': group_name,
                    'customer_name': customer_name or (members[0]['full_english_name'] if members else group_name),
                    'agency_company': agency_company,
                    'travel_date': travel_date
                },
                'members': members,
                'group_data': {
                    'customer_name': group_name,
                    'sender_name': group_name,
                    'group_customer_name': customer_name or (members[0]['full_english_name'] if members else group_name),
                    'agency_company': agency_company,
                    'date_str': travel_date,
                    'receipt_no': receipt_no,
                    'exchange_rate': exchange_rate,
                    'items': items,
                    'totals': {'usd': grand_usd, 'baht': grand_thb}
                },
                'totals': {'usd': grand_usd, 'baht': grand_thb}
            }

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
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

            if not receipt_no:
                self.send_json_response({'success': False, 'error': 'Missing receipt_no'}, status=400)
                return

            all_invoices = load_json(SAVED_CUSTOMERS_FILE, [])
            found = False
            updated_item = None

            for item in all_invoices:
                r_no = item.get('group_data', {}).get('receipt_no') or item.get('customer', {}).get('receipt_no') or ''
                if r_no.strip().lower() == receipt_no:
                    if travel_date:
                        formatted_tdate = format_display_date(travel_date)
                        item['travel_date'] = formatted_tdate
                        if 'group_info' in item:
                            item['group_info']['travel_date'] = formatted_tdate
                        if 'group_data' in item:
                            item['group_data']['travel_date'] = formatted_tdate
                            item['group_data']['date_str'] = formatted_tdate
                    if sender_name:
                        if 'group_info' in item:
                            item['group_info']['group_name'] = sender_name
                        if 'group_data' in item:
                            item['group_data']['customer_name'] = sender_name

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
                        car = float(m.get('car_fee', 0.0))
                        visa = float(m.get('visa_fee', 0.0))
                        evisa = float(m.get('e_visa', 0.0) or m.get('evisa', 0.0))

                        if usd == 0 and (vip or clearance or permit or car or visa or evisa):
                            usd = vip + clearance + permit + car + visa + evisa

                        grand_usd += usd

                        new_members.append({
                            'full_english_name': name,
                            'english_name': name,
                            'passport_no': pass_no,
                            'nationality': nat,
                            'car_fee': car,
                            'visa_fee': visa,
                            'price': 0.0,
                            'e_visa': evisa,
                            'vip': vip,
                            'clearance_fee': clearance,
                            'work_permit': permit,
                            'usd': usd,
                            'qty': '1'
                        })

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
                            'usd': usd
                        })

                    grand_thb = grand_usd * exchange_rate
                    pax_count = len(new_members)
                    first_cust_name = new_members[0]['full_english_name'] if new_members else 'N/A'
                    group_name = sender_name or item.get('group_info', {}).get('group_name') or item.get('group_data', {}).get('customer_name') or 'VIP Group'

                    item['members'] = new_members
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

            if found:
                save_json(SAVED_CUSTOMERS_FILE, all_invoices)
                self.send_json_response({'success': True, 'invoice': updated_item})
            else:
                self.send_json_response({'success': False, 'error': 'Receipt not found'}, status=404)
            return

        elif path == '/api/save_telegram_config':
            token = req_data.get('bot_token', '').strip()
            chat_id = req_data.get('chat_id', '').strip()
            save_telegram_config(token, chat_id)
            self.send_json_response({'success': True})
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
    ports = [int(env_port)] if env_port else [8000, 8001, 8080, 8888]
    for p in ports:
        try:
            httpd = socketserver.TCPServer(("", p), ImvoiWebHandler)
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
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
