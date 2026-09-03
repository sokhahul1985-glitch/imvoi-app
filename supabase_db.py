"""
Supabase Cloud Database Integration for Imvoi Web App
Zero-dependency REST API implementation using Python standard library (urllib.request).
Safeguards invoice records permanently in PostgreSQL cloud database.
"""

import os
import json
import urllib.request
import urllib.parse
import re

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'supabase_config.json')

def get_supabase_credentials():
    url = os.environ.get('SUPABASE_URL', '').strip()
    key = os.environ.get('SUPABASE_KEY', '').strip()
    
    if not url or not key:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    url = url or cfg.get('supabase_url', '').strip()
                    key = key or cfg.get('supabase_key', '').strip()
            except Exception:
                pass
    
    # Clean trailing slash from URL
    if url.endswith('/'):
        url = url[:-1]
        
    return url, key

def is_configured():
    url, key = get_supabase_credentials()
    return bool(url and key)

def _make_request(endpoint, method='GET', data=None, extra_headers=None):
    url, key = get_supabase_credentials()
    if not url or not key:
        return None
        
    full_url = f"{url}/rest/v1/{endpoint}"
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'User-Agent': 'Imvoi-App/2.0'
    }
    if extra_headers:
        headers.update(extra_headers)
        
    payload = None
    if data is not None:
        payload = json.dumps(data).encode('utf-8')
        
    req = urllib.request.Request(full_url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8')
            if body:
                return json.loads(body)
            return True
    except Exception as e:
        print(f"[Supabase] Request Error ({method} {endpoint}): {e}")
        return None

def fetch_all_invoices():
    """Fetch all invoice records stored in Supabase."""
    if not is_configured():
        return None
    try:
        # Order by receipt_no or updated_at descending
        rows = _make_request('invoices?select=receipt_no,data&order=updated_at.desc')
        if isinstance(rows, list):
            records = []
            for r in rows:
                if isinstance(r, dict) and 'data' in r and isinstance(r['data'], dict):
                    records.append(r['data'])
            return records
    except Exception as e:
        print(f"[Supabase] fetch_all_invoices error: {e}")
    return None

def upsert_invoices(records):
    """Upsert a list of invoice records into Supabase in batches."""
    if not is_configured() or not records:
        return False
    try:
        batch_size = 50
        rows = []
        for r in records:
            r_no = str(r.get('receipt_no') or (r.get('group_data') or {}).get('receipt_no') or (r.get('customer') or {}).get('receipt_no') or '').strip().upper()
            if not r_no:
                continue
            cat = str(r.get('service_category') or (r.get('group_info') or {}).get('service_category') or 'car').lower()
            rows.append({
                'receipt_no': r_no,
                'category': cat,
                'data': r
            })
            
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            _make_request(
                'invoices',
                method='POST',
                data=chunk,
                extra_headers={'Prefer': 'resolution=merge-duplicates'}
            )
        return True
    except Exception as e:
        print(f"[Supabase] upsert_invoices error: {e}")
        return False

def upsert_single_invoice(record):
    """Upsert a single invoice record into Supabase."""
    if not is_configured() or not record:
        return False
    try:
        r_no = str(record.get('receipt_no') or (record.get('group_data') or {}).get('receipt_no') or (record.get('customer') or {}).get('receipt_no') or '').strip().upper()
        if not r_no:
            return False
        cat = str(record.get('service_category') or (record.get('group_info') or {}).get('service_category') or 'car').lower()
        payload = [{
            'receipt_no': r_no,
            'category': cat,
            'data': record
        }]
        res = _make_request(
            'invoices',
            method='POST',
            data=payload,
            extra_headers={'Prefer': 'resolution=merge-duplicates'}
        )
        return res is not None
    except Exception as e:
        print(f"[Supabase] upsert_single_invoice error: {e}")
        return False

def delete_invoice(receipt_no):
    """Delete an invoice by receipt_no."""
    if not is_configured() or not receipt_no:
        return False
    try:
        enc_no = urllib.parse.quote(str(receipt_no).strip().upper())
        res = _make_request(f'invoices?receipt_no=eq.{enc_no}', method='DELETE')
        return res is not None
    except Exception as e:
        print(f"[Supabase] delete_invoice error: {e}")
        return False

def fetch_counters():
    """Fetch counter state from Supabase."""
    if not is_configured():
        return None
    try:
        rows = _make_request('app_counters?key=eq.invoice_counter&select=val')
        if isinstance(rows, list) and len(rows) > 0:
            return rows[0].get('val')
    except Exception as e:
        print(f"[Supabase] fetch_counters error: {e}")
    return None

def save_counters(counter_dict):
    """Save counter state to Supabase."""
    if not is_configured() or not counter_dict:
        return False
    try:
        payload = [{
            'key': 'invoice_counter',
            'val': counter_dict
        }]
        res = _make_request(
            'app_counters',
            method='POST',
            data=payload,
            extra_headers={'Prefer': 'resolution=merge-duplicates'}
        )
        return res is not None
    except Exception as e:
        print(f"[Supabase] save_counters error: {e}")
        return False
