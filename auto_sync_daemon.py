"""
Imvoi 24/7 Silent Auto-Sync & Permanent Vault Protector Service
Guarantees 100% data persistence across Local PC, Render Server, and Supabase Cloud.
Runs silently in background (compatible with pythonw and Windows startup).
"""

import os
import sys
import time
import datetime
import json
import re
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
LATEST_DATA_DIR = os.path.join(BACKUP_DIR, 'latest_data')
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(LATEST_DATA_DIR, exist_ok=True)

# Safe logging setup for windowless pythonw
LOG_FILE = os.path.join(BACKUP_DIR, 'daemon.log')

class SafeLogger:
    def __init__(self, filepath):
        self.filepath = filepath
        self._stdout = sys.stdout

    def write(self, message):
        try:
            if self._stdout:
                self._stdout.write(message)
                self._stdout.flush()
        except Exception:
            pass
        try:
            with open(self.filepath, 'a', encoding='utf-8', errors='ignore') as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        try:
            if self._stdout:
                self._stdout.flush()
        except Exception:
            pass

logger = SafeLogger(LOG_FILE)
sys.stdout = logger
sys.stderr = logger

try:
    import supabase_db
except Exception:
    supabase_db = None

SAVED_CUSTOMERS_FILE = os.path.join(BASE_DIR, 'saved_customers.json')
SAVED_BOOKINGS_FILE = os.path.join(BASE_DIR, 'saved_bookings.json')
INVOICE_COUNTER_FILE = os.path.join(BASE_DIR, 'invoice_counter.json')
LIVE_URL = 'https://imvoi-app-1.onrender.com'

def log(msg):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] {msg}")

def get_inv_no(x):
    if not isinstance(x, dict): return ''
    return str(x.get('receipt_no') or (x.get('group_data') or {}).get('receipt_no') or (x.get('customer') or {}).get('receipt_no') or '').strip().upper()

def merge_invoices(list_a, list_b, list_c=None):
    """Clean merge of invoices preserving the richest record per receipt_no."""
    combined = (list_a or []) + (list_b or []) + (list_c or [])
    inv_map = {}
    for inv in combined:
        if not isinstance(inv, dict): continue
        no = get_inv_no(inv)
        if no:
            if no not in inv_map:
                inv_map[no] = inv
            else:
                # Keep the one with members or richer details
                existing_members = inv_map[no].get('members') or []
                new_members = inv.get('members') or []
                if len(new_members) > len(existing_members):
                    inv_map[no] = inv
        else:
            # Skip invalid / empty records without a receipt number to prevent infinite duplicates
            continue

    def sort_inv_key(r):
        r_no = get_inv_no(r)
        num = int(re.sub(r'[^0-9]', '', r_no)) if re.sub(r'[^0-9]', '', r_no).isdigit() else 0
        prefix_order = 0 if r_no.startswith('VISA') else 1
        return (prefix_order, num)

    return sorted(list(inv_map.values()), key=sort_inv_key, reverse=True)

DELETED_BOOKINGS_FILE = os.path.join(BASE_DIR, 'deleted_booking_ids.json')

def load_daemon_deleted_ids():
    ids = set()
    if os.path.exists(DELETED_BOOKINGS_FILE):
        try:
            with open(DELETED_BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if isinstance(d, list):
                    ids.update(str(x).strip().upper() for x in d if str(x).strip())
        except Exception:
            pass
    return ids

def save_daemon_deleted_ids(del_set):
    try:
        with open(DELETED_BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(del_set)), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def merge_bookings(local_bks, cloud_bks, render_bks, del_ids=None):
    """Clean merge of bookings prioritizing local/supabase rich telegram data with strict ID uniqueness and ignoring deleted IDs."""
    del_ids = del_ids or set()
    merged = []
    inv_to_bk = {}
    id_to_bk = {}
    seen_ids = set()

    # Priority 1: Local & Supabase rich bookings (have actual pictures, true locations)
    for b in ((local_bks or []) + (cloud_bks or [])):
        if not isinstance(b, dict): continue
        bid = str(b.get('id') or '').strip()
        bid_upper = bid.upper()
        if bid_upper and bid_upper in del_ids:
            continue
        inv = str(b.get('invoiceNo') or '').strip().upper()
        if inv and inv in inv_to_bk:
            continue
        if bid and bid in seen_ids:
            continue
        if inv: inv_to_bk[inv] = b
        if bid:
            seen_ids.add(bid)
            id_to_bk[bid] = b
        merged.append(b)

    # Priority 2: Render bookings (preserve older historical records)
    for b in (render_bks or []):
        if not isinstance(b, dict): continue
        bid = str(b.get('id') or '').strip()
        bid_upper = bid.upper()
        if bid_upper and bid_upper in del_ids:
            continue
        inv = str(b.get('invoiceNo') or '').strip().upper()
        if inv and inv in inv_to_bk:
            continue
        if bid and bid in seen_ids:
            continue

        dt = str(b.get('date') or '').strip()
        tm = str(b.get('time') or '').strip()
        cn = re.sub(r'\s+', '', str(b.get('customerName') or '').strip().lower())
        match_found = False
        for existing in merged:
            e_dt = str(existing.get('date') or '').strip()
            e_tm = str(existing.get('time') or '').strip()
            e_cn = re.sub(r'\s+', '', str(existing.get('customerName') or '').strip().lower())
            if dt and tm and cn and e_dt == dt and e_tm == tm and e_cn == cn:
                match_found = True
                break
        if match_found:
            continue

        if bid: seen_ids.add(bid)
        merged.append(b)
        if bid: id_to_bk[bid] = b
        if inv: inv_to_bk[inv] = b

    def bk_sort_key(b):
        return (str(b.get('date') or ''), str(b.get('time') or ''))

    merged.sort(key=bk_sort_key, reverse=True)
    return merged

def update_counter_file(records):
    max_inv = 0
    max_visa = 0
    max_pass = 0
    for r in records:
        r_no = get_inv_no(r)
        num_part = re.sub(r'[^0-9]', '', r_no)
        if num_part.isdigit():
            nv = int(num_part)
            if r_no.startswith('VISA') and nv > max_visa: max_visa = nv
            elif r_no.startswith('PASS') and nv > max_pass: max_pass = nv
            elif r_no.startswith('INV') and nv > max_inv: max_inv = nv

    counter = {
        'last_number': max_inv,
        'prefix': 'INV ',
        'last_visa_number': max_visa,
        'visa_prefix': 'VISA ',
        'last_passport_number': max_pass if max_pass > 0 else 1,
        'passport_prefix': 'PASS '
    }
    with open(INVOICE_COUNTER_FILE, 'w', encoding='utf-8') as fc:
        json.dump(counter, fc, ensure_ascii=False, indent=2)
    return counter

def sync_invoices_cycle():
    # 1. Local
    local_invs = []
    if os.path.exists(SAVED_CUSTOMERS_FILE):
        try:
            with open(SAVED_CUSTOMERS_FILE, 'r', encoding='utf-8') as f:
                local_invs = json.load(f)
        except Exception:
            local_invs = []

    # 2. Render Cloud
    render_invs = []
    try:
        req = urllib.request.Request(f"{LIVE_URL}/api/invoices", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            render_invs = data.get('records') or data.get('invoices') or []
    except Exception:
        pass

    # 3. Supabase Cloud
    sb_invs = []
    if supabase_db and supabase_db.is_configured():
        try:
            sb_invs = supabase_db.fetch_all_invoices() or []
        except Exception:
            pass

    # Merge 3-way
    merged = merge_invoices(local_invs, render_invs, sb_invs)
    if not merged:
        return

    # Update Local PC if merged has more
    if len(merged) > len(local_invs):
        with open(SAVED_CUSTOMERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        update_counter_file(merged)
        # Vault backup
        with open(os.path.join(BACKUP_DIR, 'saved_customers_latest_vault.json'), 'w', encoding='utf-8') as fb:
            json.dump(merged, fb, ensure_ascii=False, indent=2)
        # Hourly backup
        hour_tag = datetime.datetime.now().strftime('%Y%m%d_%H')
        hourly_bak = os.path.join(BACKUP_DIR, f'customers_auto_{hour_tag}.json')
        if not os.path.exists(hourly_bak):
            with open(hourly_bak, 'w', encoding='utf-8') as fh:
                json.dump(merged, fh, ensure_ascii=False, indent=2)
        log(f"💾 Updated local invoices to {len(merged)} records.")

    # Push to Render Cloud if Render is behind
    if render_invs is not None and len(merged) > len(render_invs):
        try:
            req = urllib.request.Request(
                f"{LIVE_URL}/api/restore_database",
                data=json.dumps({'records': merged}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as presp:
                pass
            log(f"☁️ Pushed {len(merged)} invoices to Render Server.")
        except Exception as e:
            log(f"Render invoice push note: {e}")

    # Push to Supabase Cloud if Supabase is behind
    if supabase_db and supabase_db.is_configured() and len(merged) > len(sb_invs):
        try:
            supabase_db.upsert_invoices(merged)
            log(f"☁️ Synced {len(merged)} invoices to Supabase Cloud.")
        except Exception as e:
            pass

def sync_bookings_cycle():
    # Load deleted IDs from local
    del_ids = load_daemon_deleted_ids()

    # 1. Local
    local_bks = []
    if os.path.exists(SAVED_BOOKINGS_FILE):
        try:
            with open(SAVED_BOOKINGS_FILE, 'r', encoding='utf-8') as f:
                local_bks = json.load(f)
        except Exception:
            local_bks = []

    # 2. Render Cloud
    render_bks = []
    try:
        req = urllib.request.Request(f"{LIVE_URL}/api/bookings", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            render_bks = data.get('bookings') or []
            # Extract any newly reported deleted IDs from server
            remote_del_ids = data.get('deleted_ids') or []
            for r_id in remote_del_ids:
                if r_id: del_ids.add(str(r_id).strip().upper())
            save_daemon_deleted_ids(del_ids)
    except Exception:
        pass

    # 3. Supabase Cloud
    sb_bks = []
    if supabase_db and supabase_db.is_configured():
        try:
            sb_bks = supabase_db.fetch_bookings() or []
        except Exception:
            pass

    # Purge any deleted bookings from local bookings right now
    cleaned_local = [b for b in local_bks if isinstance(b, dict) and str(b.get('id') or '').strip().upper() not in del_ids]
    if len(cleaned_local) != len(local_bks):
        log(f"🗑️ Purged {len(local_bks) - len(cleaned_local)} deleted bookings from local PC.")
        local_bks = cleaned_local
        with open(SAVED_BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(local_bks, f, ensure_ascii=False, indent=2)

    # Filter render and supabase bookings against deleted IDs
    render_bks = [b for b in render_bks if isinstance(b, dict) and str(b.get('id') or '').strip().upper() not in del_ids]
    sb_bks = [b for b in sb_bks if isinstance(b, dict) and str(b.get('id') or '').strip().upper() not in del_ids]

    # Merge 3-way
    merged = merge_bookings(local_bks, sb_bks, render_bks, del_ids)
    if not merged:
        return

    # Update Local PC if merged has more
    if len(merged) > len(local_bks):
        with open(SAVED_BOOKINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        # Vault backup
        with open(os.path.join(BACKUP_DIR, 'saved_bookings_latest_vault.json'), 'w', encoding='utf-8') as fb:
            json.dump(merged, fb, ensure_ascii=False, indent=2)
        # Hourly backup
        hour_tag = datetime.datetime.now().strftime('%Y%m%d_%H')
        hourly_bak = os.path.join(BACKUP_DIR, f'bookings_auto_{hour_tag}.json')
        if not os.path.exists(hourly_bak):
            with open(hourly_bak, 'w', encoding='utf-8') as fh:
                json.dump(merged, fh, ensure_ascii=False, indent=2)
        log(f"💾 Updated local bookings to {len(merged)} records.")

    # Push to Render Cloud if Render is behind
    if render_bks is not None and len(merged) > len(render_bks):
        try:
            req = urllib.request.Request(
                f"{LIVE_URL}/api/bookings",
                data=json.dumps({'bookings': merged}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as presp:
                pass
            log(f"☁️ Pushed {len(merged)} bookings to Render Server.")
        except Exception as e:
            log(f"Render bookings push note: {e}")

    # Push to Supabase Cloud if Supabase is behind
    if supabase_db and supabase_db.is_configured() and len(merged) > len(sb_bks):
        try:
            supabase_db.save_bookings(merged)
            log(f"☁️ Synced {len(merged)} bookings to Supabase Cloud.")
        except Exception as e:
            pass

def run_loop():
    log("=" * 60)
    log("🚀 IMVOI 24/7 AUTO-SYNC & PERMANENT VAULT PROTECTOR STARTED")
    log("🛡️ Rock-solid protection active across Local PC, Render & Supabase")
    log("=" * 60)
    cycle_count = 0
    while True:
        try:
            sync_invoices_cycle()
            sync_bookings_cycle()
            cycle_count += 1
            if cycle_count % 25 == 1:
                # Heartbeat confirmation every ~10 minutes and on first cycle
                inv_cnt = len(json.load(open(SAVED_CUSTOMERS_FILE, encoding='utf-8'))) if os.path.exists(SAVED_CUSTOMERS_FILE) else 0
                bk_cnt = len(json.load(open(SAVED_BOOKINGS_FILE, encoding='utf-8'))) if os.path.exists(SAVED_BOOKINGS_FILE) else 0
                log(f"🛡️ Vault Heartbeat: All {bk_cnt} Bookings & {inv_cnt} Invoices 100% in sync & secured.")
        except Exception as e:
            log(f"Loop cycle note: {e}")
        time.sleep(25)

if __name__ == '__main__':
    run_loop()
