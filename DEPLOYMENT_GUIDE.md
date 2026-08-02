# ណែនាំអំពីការបោះពុម្ពផ្សាយវេបសាយ (Deploy Imvoi Web App Online 24/7)

ឯកសារនេះណែនាំពីរបៀបយក Imvoi Web App ទៅ Upload និង Deploy លើ Cloud / Hosting ដើម្បីឲ្យមនុស្សគ្រប់គ្នាអាចចូលតាម Link នៃវេបសាយបាន ២៤ ម៉ោង / ៧ ថ្ងៃ ទោះបីជាបិទកុំព្យូទ័រក៏ដោយ។

---

## វិធីសាស្ត្រទី ១៖ Deploy ឥតគិតថ្លៃ ១០០% លើ Render.com (Python Server)

 Render.com ផ្តល់ជូននូវ Web Hosting ឥតគិតថ្លៃ ១០០% មាន Link HTTPS (ឧ. `https://imvoi-app.onrender.com`)។

### ជំហានអនុវត្ត៖
1. **បង្កើត Account លើ GitHub** (បើមិនទាន់មាន)៖
   - ចូលទៅ [github.com](https://github.com) ហើយចុះឈ្មោះ Sign Up (ឥតគិតថ្លៃ)។
   - បង្កើត Repository ថ្មីមួយឈ្មោះ `Imvoi-Web-App`។
   - Upload ឯកសារទាំងអស់ក្នុង Folder នេះចូលទៅក្នុង GitHub Repository នោះ។

2. **ចុះឈ្មោះលើ Render.com**៖
   - ចូលទៅ [render.com](https://render.com) ហើយជ្រើសរើស **GET STARTED FOR FREE** (អាច Login ជាមួយ GitHub Account បាន)។

3. **បង្កើត Web Service ថ្មី**៖
   - ចុចលើប៊ូតុង **New +** -> ជ្រើសរើស **Web Service**។
   - ជ្រើសរើស Repository `Imvoi-Web-App` ដែលបាន Upload អំបាញ់មិញ។
   - បំពេញព័ត៌មានដូចខាងក្រោម៖
     * **Name**: `imvoi-app` (ឬឈ្មោះតាមចិត្ត)
     * **Runtime**: `Python 3`
     * **Build Command**: `pip install -r requirements_server.txt`
     * **Start Command**: `python server.py`
     * **Instance Type**: ជ្រើសរើស **Free**

4. **ចុច Create Web Service**៖
   - រង់ចាំ Render រៀបចំ និង Build ប្រហែល 1-2 នាទី។
   - ពេលរៀបចំរួចរាល់ លោកអ្នកនឹងទទួលបាន Public Link ដូចជា `https://imvoi-app.onrender.com` ដែលអាចផ្ញើទៅកាន់អ្នកណាៗក៏អាចបើកមើលបាន។

---

## វិធីសាស្ត្រ Upgrade ទៅកាន់ Paid Plan លើ Render.com (ដើម្បីដើរ 24/7 គ្មាន Sleep)

ប្រសិនបើលោកអ្នកចង់ឲ្យវេបសាយ **បើកភ្លាមដើរភ្លាម ២៤/៧** ដោយមិនចាំបាច់រង់ចាំ Loading/Sleep Mode (តម្លៃត្រឹម $7/ខែ)៖

### ជំហាន Upgrade៖
1. ចូលទៅកាន់ Dashbaord លើ [render.com](https://dashboard.render.com)
2. ចុចលើ Web Service របស់លោកអ្នក (**imvoi-app**)
3. ចុចលើម៉ឺនុយ **Settings** នៅផ្នែកខាងឆ្វេង
4. រំកិលចុះក្រោមទៅកាន់ផ្នែក **Instance Type** (បច្ចុប្បន្នជា `Free`)
5. ចុចប៊ូតុង **Change Instance Type** -> ជ្រើសរើស **Starter** ($7 / month)
6. បំពេញព័ត៌មានកាតធនាគារ (Visa / Mastercard / ABA Mastercard) រួចចុច **Save Changes**
7. រួចរាល់! វេបសាយនឹងដំណើរការ 24 ម៉ោង/7 ថ្ងៃ ដោយគ្មានទាក់ ឬចាំ Wake up ទៀតឡើយ។

---

## វិធីសាស្ត្រទី ២៖ Upload ទៅកាន់ PHP Web Hosting (ដូចជា Hostinger, InfinityFree, cPanel)

ប្រសិនបើលោកអ្នកមាន Web Hosting (PHP) ស្រាប់ ឬប្រើ InfinityFree (ឥតគិតថ្លៃ)៖

### ជំហានអនុវត្ត៖
1. បើកចូលទៅកាន់ File Manager នៃ Hosting របស់លោកអ្នក (ឬថត `public_html`)។
2. Zip ឯកសារទាំងអស់ដែលនៅក្នុងថត `php_app/` ៖
   * `index.php`
   * `api.php`
   * `db.php`
   * `config.php`
   * `single_invoice.php`
   * `group_invoice.php`
   * `view_receipt.php`
   * ថត `assets/`
3. Upload ឯកសារ Zip នោះចូល `public_html` រួចចុច **Extract**។
4. វេបសាយនឹងដំណើការភ្លាមៗ តាម Domain របស់លោកអ្នក!

---

> [!NOTE]
> ប្រសិនបើលោកអ្នកត្រូវការជំនួយក្នុងការបង្កើត GitHub Repository ឬ Upload ឯកសារ ខ្ញុំអាចបន្តជួយណែនាំជំហានបន្ទាប់ជូនបាន!
