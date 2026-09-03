"""
Interactive Supabase Setup & Test Tool for Imvoi
"""

import os
import json
import sys
import urllib.request
import supabase_db
import sync_to_supabase

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'supabase_config.json')

def main():
    print("=" * 65)
    print("🚀 IMVOI SUPABASE CLOUD DATABASE SETUP")
    print("ការពារទិន្នន័យវិក្កយបត្រ ២៤ ម៉ោង / ៧ ថ្ងៃ លើ PostgreSQL Cloud")
    print("=" * 65)
    
    cur_url, cur_key = supabase_db.get_supabase_credentials()
    
    if cur_url and cur_key:
        print(f"📌 កំពុងប្រើប្រាស់ Configuration បច្ចុប្បន្ន:")
        print(f"   URL: {cur_url}")
        print(f"   Key: {cur_key[:8]}...{cur_key[-4:]}")
        ans = input("\nតើអ្នកចង់ប្តូរ URL/Key ថ្មីដែរឬទេ? (y/N): ").strip().lower()
        if ans != 'y':
            test_and_migrate()
            return
            
    print("\nសូមបំពេញព័ត៌មានពី Supabase Dashboard (Project Settings -> API):")
    url = input("1. បញ្ចូល Project URL (ឧ. https://xyz.supabase.co): ").strip()
    key = input("2. បញ្ចូល API anon public key (eyJhbGci...): ").strip()
    
    if not url or not key:
        print("❌ មិនអាចទទេបានឡើយ។ សូមព្យាយាមម្តងទៀត។")
        return
        
    if url.endswith('/'):
        url = url[:-1]
        
    cfg = {'supabase_url': url, 'supabase_key': key}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
        
    print(f"\n✅ បានរក្សាទុកក្នុង {CONFIG_FILE} រួចរាល់!")
    test_and_migrate()

def test_and_migrate():
    print("\n🔍 កំពុងធ្វើតេស្តការភ្ជាប់ទៅកាន់ Supabase...")
    url, key = supabase_db.get_supabase_credentials()
    
    # Test connection
    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/invoices?select=receipt_no&limit=1",
            headers={
                'apikey': key,
                'Authorization': f'Bearer {key}',
                'User-Agent': 'Imvoi-App/2.0'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("✅ ភ្ជាប់ទៅកាន់ Supabase Database បានជោគជ័យ ១០០%!")
    except Exception as e:
        print(f"❌ មិនទាន់អាចភ្ជាប់បានទេ: {e}")
        print("👉 សូមប្រាកដថាអ្នកបានចូលទៅកាន់ Supabase -> SQL Editor ហើយ Run code ក្នុង supabase_schema.sql រួចរាល់!")
        return
        
    # Upload existing records
    print("\n📤 កំពុងធ្វើដំណើរការ Upload ទិន្នន័យចាស់ទាំងអស់ទៅកាន់ Supabase...")
    if sync_to_supabase.migrate_to_supabase():
        print("\n" + "=" * 65)
        print("🎉 អបអរសាទរ! ប្រព័ន្ធ Supabase Cloud Database ដំណើរការរួចរាល់!")
        print("💡 ជំហានចុងក្រោយសម្រាប់ Render.com:")
        print("   1. ចូលទៅកាន់ https://dashboard.render.com")
        print("   2. ចុចលើ Web Service របស់អ្នក (imvoi-app)")
        print("   3. ចូល Environment -> Add Environment Variable:")
        print(f"      - SUPABASE_URL = {url}")
        print(f"      - SUPABASE_KEY = {key}")
        print("   4. ចុច Save Changes ជាការស្រេច! វេបសាយនឹងមិនបាត់ទិន្នន័យទៀតឡើយ!")
        print("=" * 65)

if __name__ == '__main__':
    main()
