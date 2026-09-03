# 📖 ការណែនាំដំឡើង Supabase Cloud Database (ឥតគិតថ្លៃ ១០០%)

ដើម្បីការពារទិន្នន័យវេបសាយកុំឲ្យបាត់បង់រហូត ទោះបី Render Sleep ឬ Restart រាប់ពាន់ដងក៏ដោយ សូមអនុវត្តតាម ៣ ជំហានងាយៗខាងក្រោម (ចំណាយពេលត្រឹមតែ ២ នាទី)៖

---

## ជំហានទី ១៖ បង្កើត Project លើ Supabase (ឥតគិតថ្លៃ)
1. ចូលទៅកាន់វេបសាយ [https://supabase.com](https://supabase.com)
2. ចុច **Start your project** រួច Sign in ដោយប្រើ **GitHub** ឬ **Google Email**
3. ចុចប៊ូតុង **New Project**
4. បំពេញព័ត៌មាន៖
   - **Name**: ដាក់ឈ្មោះតាមចិត្ត (ឧ. `imvoi-db`)
   - **Database Password**: ដាក់ Password ណាមួយដែលអ្នកចង់បាន (ឬ Generate Password)
   - **Region**: ជ្រើសរើស **Singapore (ap-southeast-1)** (នៅក្បែរកម្ពុជា ដើរលឿនបំផុត)
5. ចុច **Create new project** ហើយរង់ចាំប្រហែល ១ នាទី។

---

## ជំហានទី ២៖ បង្កើត Table (ចម្លង Code ១ ផ្ទាំងទៅ Run)
1. នៅលើ Menu ខាងឆ្វេងក្នុង Supabase ចុចលើ **SQL Editor** (រូបតំណាង `>_`)
2. ចុចលើ **New query**
3. ចម្លង (Copy) កូដ SQL ខាងក្រោមនេះយកទៅបិទភ្ជាប់ (Paste)៖

```sql
-- 1. Create Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    receipt_no TEXT PRIMARY KEY,
    category TEXT DEFAULT 'car',
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create Counters Table
CREATE TABLE IF NOT EXISTS app_counters (
    key TEXT PRIMARY KEY,
    val JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Enable Full Access via API
ALTER TABLE invoices DISABLE ROW LEVEL SECURITY;
ALTER TABLE app_counters DISABLE ROW LEVEL SECURITY;

-- 4. Fast Search Indexes
CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices(category);
CREATE INDEX IF NOT EXISTS idx_invoices_updated_at ON invoices(updated_at DESC);
```

4. ចុចប៊ូតុង **Run** (ពណ៌បៃតង) នៅផ្នែកខាងស្តាំដៃក្រោម។ វានឹងបង្ហាញពាក្យថា **Success**!

---

## ជំហានទី ៣៖ យក URL និង API Key
1. នៅលើ Menu ខាងឆ្វេង ចុចលើរូបកង់ Settings ⚙️ (**Project Settings**) -> ជ្រើសរើស **API**
2. លោកអ្នកនឹងឃើញ៖
   - **Project URL** (ឧ. `https://abcdefghijklm.supabase.co`)
   - **Project API Keys** -> យកបន្ទាត់ `anon` `public` (កូដវែង `eyJhbGci...`)

---

## ជំហានទី ៤៖ ភ្ជាប់ជាមួយ Imvoi App

### វិធីស្រួលបំផុត (តាមកុំព្យូទ័រ)៖
1. ចុច Double-click លើ File [setup_supabase.bat](file:///d:/Imvoi/setup_supabase.bat)
2. បិទភ្ជាប់ (Paste) **Project URL** និង **anon key** ដែលទើបចម្លងមក
3. វានឹង Upload ទិន្នន័យវិក្កយបត្រទាំង ២៥៤ សន្លឹកទៅកាន់ Supabase ដោយស្វ័យប្រវត្តិ!

### សម្រាប់ Render.com (ដើម្បីឲ្យវេបសាយ Online ដើរជាប់រហូត)៖
1. ចូលទៅ [https://dashboard.render.com](https://dashboard.render.com)
2. ចុចលើ Web Service របស់អ្នក (`imvoi-app`)
3. ចុចលើ Menu **Environment** នៅខាងឆ្វេង
4. ចុច **Add Environment Variable**៖
   - Key: `SUPABASE_URL` | Value: `(Project URL របស់អ្នក)`
   - Key: `SUPABASE_KEY` | Value: `(anon public key របស់អ្នក)`
5. ចុច **Save Changes**!
   Render នឹងធ្វើការ Restart ហើយចាប់ពីពេលនេះតទៅ ទោះបី Render Sleep ឬបិទកុំព្យូទ័រ ក៏ទិន្នន័យត្រូវបានរក្សាទុកជាប់ជានិច្ច ១០០%!
