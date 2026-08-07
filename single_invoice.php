<?php
/**
 * CMP Golden Mekong Commercial Service - Single Invoice Form Creator with Passport OCR Scanner
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

$nextReceiptNo = get_next_invoice_no();
$todayStr = date('d-m-Y');
?>
<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= APP_NAME ?> - បង្កើតវិក្កយបត្រទោល (Single Invoice)</title>
    <link rel="stylesheet" href="assets/css/styles.css">
    <!-- Optional Client Tesseract for Passport OCR Scan -->
    <script src="https://cdn.jsdelivr.net/npm/tesseract.js@4/dist/tesseract.min.js"></script>
</head>
<body>

    <!-- Header Navigation -->
    <header class="app-header">
        <div class="brand-container">
            <div class="brand-logo">🧾</div>
            <div>
                <div class="brand-title"><?= COMPANY_NAME_EN ?></div>
                <div class="brand-subtitle"><?= COMPANY_NAME_KH ?></div>
            </div>
        </div>
        <div class="nav-links">
            <a href="index.php" class="nav-btn">📊 ផ្ទាំងគ្រប់គ្រង (Dashboard)</a>
            <a href="group_invoice.php" class="nav-btn btn-emerald">👥 + បង្កើតក្រុម (Group Invoice)</a>
            <a href="single_invoice.php" class="nav-btn active">👤 + វិក្កយបត្រទោល (Single)</a>
        </div>
    </header>

    <div class="container">
        
        <form id="singleInvoiceForm" action="api.php?action=save_single" method="POST" enctype="multipart/form-data">
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                
                <!-- Left Panel: Drag and Drop Passport Image Scanner -->
                <div class="panel-card">
                    <div class="panel-header">
                        <h2 class="panel-title">📷 សែនរូបថត លិខិតឆ្លងដែន (Passport OCR Scanner)</h2>
                    </div>

                    <div id="dropZone" style="border: 2px dashed var(--accent-cyan); border-radius: var(--radius-lg); background: #0f172a; padding: 40px 20px; text-align: center; cursor: pointer; transition: all 0.2s ease;">
                        <div style="font-size: 3rem; margin-bottom: 10px;">📁</div>
                        <div style="font-weight: 700; color: #fff; margin-bottom: 6px;">Drag & Drop Passport Image Here</div>
                        <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px;">(ទាញទម្លាក់រូបថតលិខិតឆ្លងដែនទីនេះ ដើម្បីអានឈ្មោះ និងលេខលិខិតឆ្លងដែនស្វ័យប្រវត្តិ)</div>
                        <input type="file" id="passportFileInput" name="passport_file" accept="image/*" style="display: none;" onchange="handlePassportUpload(this.files[0])">
                        <button type="button" class="btn btn-primary" onclick="document.getElementById('passportFileInput').click()">Choose File / ជ្រើសរើសរូបថត</button>
                    </div>

                    <div id="ocrStatus" style="margin-top: 14px; font-size: 0.85rem; color: var(--accent-cyan); text-align: center; display: none;">
                        ⏳ កំពុងដំណើរការអានទិន្នន័យពី Passport (Processing OCR...)...
                    </div>

                    <div id="imagePreviewContainer" style="margin-top: 16px; text-align: center; display: none;">
                        <img id="passportPreviewImg" src="" alt="Passport Preview" style="max-width: 100%; max-height: 240px; border-radius: 8px; border: 1px solid var(--border-color);">
                    </div>
                </div>

                <!-- Right Panel: Customer Details & Fee Breakdown Form -->
                <div class="panel-card">
                    <div class="panel-header">
                        <h2 class="panel-title">👤 ព័ត៌មានអតិថិជន និងសេវាកម្ម</h2>
                        <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan);">
                            វិក្កយបត្រលេខ៖ <span style="background: rgba(56,189,248,0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid var(--accent-cyan);"><?= htmlspecialchars($nextReceiptNo) ?></span>
                        </div>
                    </div>

                    <input type="hidden" name="receipt_no" value="<?= htmlspecialchars($nextReceiptNo) ?>">

                    <div class="form-group" style="margin-bottom: 14px;">
                        <label>ឈ្មោះពេញអតិថិជន (Full English Name) *</label>
                        <input type="text" id="custNameInput" name="full_english_name" class="form-control" placeholder="ឧទាហរណ៍៖ SOMCHAI SUKSAWAD" required>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;">
                        <div class="form-group">
                            <label>លេខ Passport (Passport No)</label>
                            <input type="text" id="custPassportInput" name="passport_no" class="form-control" placeholder="AA1234567">
                        </div>

                        <div class="form-group">
                            <label>សញ្ជាតិ (Nationality)</label>
                            <input type="text" id="custNatInput" name="nationality" class="form-control" value="THAI">
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;">
                        <div class="form-group">
                            <label>ថ្ងៃខែឆ្នាំកំណើត (DOB)</label>
                            <input type="text" id="custDobInput" name="dob" class="form-control" placeholder="DD/MM/YYYY">
                        </div>

                        <div class="form-group">
                            <label>កាលបរិច្ឆេទធ្វើដំណើរ (Travel Date)</label>
                            <input type="text" name="travel_date" class="form-control" value="<?= $todayStr ?>">
                        </div>
                    </div>

                    <h4 style="color: var(--accent-cyan); margin: 18px 0 12px 0; border-bottom: 1px solid var(--border-color); padding-bottom: 6px;">💰 តារាងគណនាតម្លៃសេវាកម្ម (Fees Calculation)</h4>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px;">
                        <div class="form-group">
                            <label>VIP Service ($)</label>
                            <input type="number" step="0.01" id="singleVip" name="vip_fee" class="form-control single-fee num-input" value="280.00">
                        </div>

                        <div class="form-group">
                            <label>Clearance Fee ($)</label>
                            <input type="number" step="0.01" id="singleClearance" name="clearance_fee" class="form-control single-fee num-input" value="40.00">
                        </div>

                        <div class="form-group">
                            <label>Work Permit ($)</label>
                            <input type="number" step="0.01" id="singleWorkPermit" name="work_permit" class="form-control single-fee num-input" value="40.00">
                        </div>

                        <div class="form-group">
                            <label>Car Fee ($)</label>
                            <input type="number" step="0.01" id="singleCarFee" name="car_fee" class="form-control single-fee num-input" value="0.00">
                        </div>

                        <div class="form-group">
                            <label>Visa Fee ($)</label>
                            <input type="number" step="0.01" id="singleVisaFee" name="visa_fee" class="form-control single-fee num-input" value="0.00">
                        </div>

                        <div class="form-group">
                            <label>E-Visa ($)</label>
                            <input type="number" step="0.01" id="singleEvisa" name="e_visa" class="form-control single-fee num-input" value="0.00">
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">
                        <div class="form-group">
                            <label>សរុប (Total USD)</label>
                            <input type="number" step="0.01" id="singleTotalUsd" name="total_usd" class="form-control num-input" value="360.00" style="font-size: 1.2rem; color: var(--accent-emerald);" readonly>
                        </div>

                        <div class="form-group">
                            <label>ស្ថានភាពបង់ប្រាក់ (Status)</label>
                            <select name="payment_status" class="form-control" style="font-weight: 700;">
                                <option value="UNPAID" selected>❌ មិនទាន់បង់ (UNPAID)</option>
                                <option value="PAID">✅ បង់រួច (PAID)</option>
                            </select>
                        </div>
                    </div>

                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <a href="index.php" class="btn btn-secondary">❌ បោះបង់</a>
                        <button type="submit" class="btn btn-primary" style="padding: 10px 24px;">💾 រក្សាទុកវិក្កយបត្រ (Save Single Invoice)</button>
                    </div>

                </div>

            </div>

        </form>

    </div>

    <script src="assets/js/app.js"></script>
    <script>
        const dropZone = document.getElementById('dropZone');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            let dt = e.dataTransfer;
            let files = dt.files;
            if (files.length > 0) {
                handlePassportUpload(files[0]);
            }
        }

        function handlePassportUpload(file) {
            if (!file) return;

            const previewImg = document.getElementById('passportPreviewImg');
            const previewContainer = document.getElementById('imagePreviewContainer');
            const statusEl = document.getElementById('ocrStatus');

            previewImg.src = URL.createObjectURL(file);
            previewContainer.style.display = 'block';
            statusEl.style.display = 'block';
            statusEl.textContent = '⌛ AI Document AI កំពុងស្កេនរូបភាព (Processing OCR)...';

            let formData = new FormData();
            formData.append('passport_file', file);

            fetch('ocr_scan.php', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(res => {
                statusEl.style.display = 'none';
                if (res.success && res.results && res.results.length > 0) {
                    const data = res.results[0];
                    if (data.full_english_name) {
                        document.getElementById('custNameInput').value = data.full_english_name;
                    }
                    if (data.passport_no) {
                        const passInput = document.querySelector('input[name="passport_no"]');
                        if (passInput) passInput.value = data.passport_no;
                    }
                    if (data.nationality) {
                        const natInput = document.querySelector('input[name="nationality"]');
                        if (natInput) natInput.value = data.nationality;
                    }
                    if (data.dob) {
                        const dobInput = document.querySelector('input[name="dob"]');
                        if (dobInput) dobInput.value = data.dob;
                    }
                }
            })
            .catch(err => {
                statusEl.style.display = 'none';
                console.log('OCR Error:', err);
            });
        }
    </script>
</body>
</html>
