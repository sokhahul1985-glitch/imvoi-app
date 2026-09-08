"""
Script to upload existing local JSON database into Supabase Cloud.
Can be executed directly or run automatically during server startup.
"""

import os
import json
import sys
import supabase_db

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def migrate_to_supabase():
    if not supabase_db.is_configured():
        print("❌ Supabase មិនទាន់ត្រូវបានកំណត់ (Credentials missing).")
        print("សូមកំណត់ SUPABASE_URL និង SUPABASE_KEY ក្នុង supabase_config.json ឬ Environment Variables។")
        return False
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    saved_file = os.path.join(base_dir, 'saved_customers.json')
    counter_file = os.path.join(base_dir, 'invoice_counter.json')
    
    if not os.path.exists(saved_file):
        print(f"❌ មិនឃើញឯកសារ {saved_file} ឡើយ។")
        return False
        
    with open(saved_file, 'r', encoding='utf-8') as f:
        records = json.load(f)
        
    print(f"🚀 កំពុង Upload {len(records)} វិក្កយបត្រ ទៅកាន់ Supabase Cloud...")
    success = supabase_db.upsert_invoices(records)
    
    if success:
        print(f"✅ បាន Upload {len(records)} វិក្កយបត្រ ទៅកាន់ Supabase ដោយជោគជ័យ!")
    else:
        print("❌ បរាជ័យក្នុងការ Upload សូមពិនិត្យមើល Supabase URL, Key និង Table SQL។")
        return False
        
    if os.path.exists(counter_file):
        try:
            with open(counter_file, 'r', encoding='utf-8') as fc:
                counter = json.load(fc)
            supabase_db.save_counters(counter)
            print("✅ បាន Upload Counter ទៅកាន់ Supabase ជោគជ័យ!")
        except Exception as e:
            print("Counter sync notice:", e)

    booking_file = os.path.join(base_dir, 'saved_bookings.json')
    if os.path.exists(booking_file):
        try:
            with open(booking_file, 'r', encoding='utf-8') as fb:
                bookings = json.load(fb)
            if bookings and isinstance(bookings, list):
                print(f"🚀 កំពុង Upload {len(bookings)} ការកក់ឡាន (Bookings) ទៅកាន់ Supabase Cloud...")
                bk_success = supabase_db.save_bookings(bookings)
                if bk_success:
                    print(f"✅ បាន Upload {len(bookings)} ការកក់ឡាន ទៅកាន់ Supabase ជោគជ័យ!")
                else:
                    print("⚠️ បរាជ័យក្នុងការ Upload Bookings ទៅកាន់ Supabase។")
        except Exception as eb:
            print("Booking sync notice:", eb)

    return True

if __name__ == '__main__':
    migrate_to_supabase()
