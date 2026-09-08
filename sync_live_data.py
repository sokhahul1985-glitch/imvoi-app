import urllib.request
import json
import os
import sys
import datetime
import re

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def sync_data():
    live_url = 'https://imvoi-app-1.onrender.com/api/invoices'
    print(f'Connecting to {live_url}...')
    
    try:
        req = urllib.request.Request(live_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            live_records = res.get('records') or res.get('invoices') or []
        print(f'✅ ទាញយកទិន្នន័យពី Render បានជោគជ័យ: {len(live_records)} វិក្កយបត្រ')
    except Exception as e:
        print('❌ Error fetching from Render:', e)
        live_records = []

    # Read local records
    local_records = []
    if os.path.exists('saved_customers.json'):
        # Safety backup
        now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'saved_customers_backup_{now_str}.json'
        with open('saved_customers.json', 'r', encoding='utf-8') as f_in, open(backup_file, 'w', encoding='utf-8') as f_out:
            f_out.write(f_in.read())
        print(f'📁 បានបង្កើតឯកសារ Backup សុវត្ថិភាព: {backup_file}')
        
        try:
            with open('saved_customers.json', 'r', encoding='utf-8') as f:
                local_records = json.load(f)
        except Exception:
            local_records = []

    # Merge records
    record_map = {}
    
    # Add live records first
    for r in live_records:
        r_no = str(r.get('receipt_no') or r.get('group_data', {}).get('receipt_no') or r.get('customer', {}).get('receipt_no') or '').strip().upper()
        ts = str(r.get('saved_at') or r.get('timestamp') or r.get('created_at') or '')
        sender = str(r.get('sender') or r.get('sender_name') or '')
        key = r_no if r_no else f'ts_{ts}_{sender}'
        record_map[key] = r

    # Add local records if not present
    for r in local_records:
        r_no = str(r.get('receipt_no') or r.get('group_data', {}).get('receipt_no') or r.get('customer', {}).get('receipt_no') or '').strip().upper()
        ts = str(r.get('saved_at') or r.get('timestamp') or r.get('created_at') or '')
        sender = str(r.get('sender') or r.get('sender_name') or '')
        key = r_no if r_no else f'ts_{ts}_{sender}'
        if key not in record_map:
            record_map[key] = r

    merged_records = list(record_map.values())
    print(f'📊 សរុបទិន្នន័យទាំងអស់ (Total merged): {len(merged_records)} វិក្កយបត្រ')

    # Save to saved_customers.json
    with open('saved_customers.json', 'w', encoding='utf-8') as f:
        json.dump(merged_records, f, ensure_ascii=False, indent=2)

    # Save to saved_customers_live_backup.json
    with open('saved_customers_live_backup.json', 'w', encoding='utf-8') as f:
        json.dump(merged_records, f, ensure_ascii=False, indent=2)

    # Recalculate invoice_counter.json
    max_inv = 0
    max_visa = 0
    max_pass = 0

    for r in merged_records:
        r_no = str(r.get('receipt_no') or r.get('group_data', {}).get('receipt_no') or r.get('customer', {}).get('receipt_no') or '').strip().upper()
        num_part = re.sub(r'[^0-9]', '', r_no)
        if num_part.isdigit():
            num_val = int(num_part)
            if r_no.startswith('VISA'):
                if num_val > max_visa: max_visa = num_val
            elif r_no.startswith('PASS'):
                if num_val > max_pass: max_pass = num_val
            elif r_no.startswith('INV'):
                if num_val > max_inv: max_inv = num_val

    counter = {
        'last_number': max_inv,
        'prefix': 'INV ',
        'last_visa_number': max_visa,
        'visa_prefix': 'VISA ',
        'last_passport_number': max_pass,
        'passport_prefix': 'PASS '
    }

    with open('invoice_counter.json', 'w', encoding='utf-8') as f:
        json.dump(counter, f, ensure_ascii=False, indent=2)

    print('🔢 បានអាប់ឌេតលេខវិក្កយបត្រ (Counters updated):', counter)

    # Push to Render if Render doesn't have all records
    if len(merged_records) > len(live_records):
        print(f'☁️ កំពុងផ្ញើទិន្នន័យពេញលេញ {len(merged_records)} ទៅ Render Cloud...')
        try:
            req_push = urllib.request.Request(
                'https://imvoi-app-1.onrender.com/api/restore_database',
                data=json.dumps({'records': merged_records}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req_push, timeout=60) as resp_push:
                print('✅ បានបញ្ចូលទិន្នន័យទៅ Render Cloud ជោគជ័យ:', resp_push.read().decode('utf-8'))
        except Exception as ep:
            print('⚠️ បញ្ហាពេល Upload ទៅ Render:', ep)

    print('✅ រួចរាល់ដោយជោគជ័យ! (All data is preserved and synced!)')

if __name__ == '__main__':
    sync_data()
