<?php
/**
 * CMP Golden Mekong Commercial Service - Group Invoice Form Creator
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
    <title><?= APP_NAME ?> - បង្កើតវិក្កយបត្រក្រុម (Group Invoice)</title>
    <link rel="stylesheet" href="assets/css/styles.css">
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
            <a href="group_invoice.php" class="nav-btn btn-emerald active">👥 + បង្កើតក្រុម (Group Invoice)</a>
            <a href="single_invoice.php" class="nav-btn">👤 + វិក្កយបត្រទោល (Single)</a>
        </div>
    </header>

    <div class="container">
        
        <form id="groupInvoiceForm" action="api.php?action=save_group" method="POST">
            
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title">👥 បង្កើតវិក្កយបត្រក្រុមថ្មី (New Group Invoice)</h2>
                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan);">
                        វិក្កយបត្រលេខ៖ <span style="background: rgba(56,189,248,0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid var(--accent-cyan);"><?= htmlspecialchars($nextReceiptNo) ?></span>
                    </div>
                </div>

                <input type="hidden" name="receipt_no" value="<?= htmlspecialchars($nextReceiptNo) ?>">

                <!-- Group Top Info Form Grid -->
                <div class="form-grid">
                    <div class="form-group">
                        <label>ឈ្មោះក្រុម / អ្នកផ្ញើ (Group / Sender Name) *</label>
                        <input type="text" name="group_name" class="form-control" placeholder="ឧទាហរណ៍៖ Hr 222 - Sokha" required>
                    </div>

                    <div class="form-group">
                        <label>ឈ្មោះតំណាងអតិថិជន (Representative Customer)</label>
                        <input type="text" name="customer_name" class="form-control" placeholder="ឈ្មោះសមាជិកតំណាង...">
                    </div>

                    <div class="form-group">
                        <label>ភ្នាក់ងារ / ក្រុមហ៊ុន (Agency / Company)</label>
                        <input type="text" name="agency_company" class="form-control" placeholder="អាសយដ្ឋាន ឬឈ្មោះក្រុមហ៊ុន...">
                    </div>

                    <div class="form-group">
                        <label>កាលបរិច្ឆេទធ្វើដំណើរ (Travel Date) *</label>
                        <input type="text" name="travel_date" class="form-control" value="<?= $todayStr ?>" required>
                    </div>

                    <div class="form-group">
                        <label>អត្រាប្តូរប្រាក់ (Exchange Rate USD to THB)</label>
                        <input type="number" step="0.1" id="exchangeRateInput" name="exchange_rate" class="form-control num-input" value="33.90" oninput="calculateGrandTotal()">
                    </div>

                    <div class="form-group">
                        <label>ស្ថានភាពបង់ប្រាក់ (Payment Status)</label>
                        <select name="payment_status" class="form-control" style="font-weight: 700;">
                            <option value="UNPAID" selected>❌ មិនទាន់បង់ (UNPAID)</option>
                            <option value="PAID">✅ បង់រួច (PAID)</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- AI Passport Batch OCR Upload Card -->
            <div class="panel-card" style="border: 2px dashed var(--accent-blue); background: rgba(15, 23, 42, 0.4);">
                <div class="drop-zone" id="groupDropZone" style="padding: 20px; text-align: center; cursor: pointer;">
                    <div style="font-size: 2rem;">📷 📂</div>
                    <div style="font-weight: 700; font-size: 1.05rem; margin-top: 6px; color: var(--accent-cyan);">
                        ទម្លាក់រូបភាព Passport ជាក្រុមនៅទីនេះ (Drag & Drop Passport Images Here)
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
                        ឬចុចទីនេះដើម្បីជ្រើសរើសរូបភាព Passport ច្រើនសន្លឹក (ស្កេនឈ្មោះអូតូចូលតារាង)
                    </div>
                    <input type="file" id="groupFileInput" multiple accept="image/*" style="display: none;">
                    <div id="groupOcrStatus" style="margin-top: 10px; font-weight: 700; color: #38bdf8; display: none;">
                        ⌛ AI Document AI កំពុងស្កេនរូបភាព...
                    </div>
                </div>
            </div>

            <!-- Member Items Table Panel -->
            <div class="panel-card">
                <div class="panel-header">
                    <h3 class="panel-title">📋 បញ្ជីឈ្មោះសមាជិក និងតម្លៃសេវាកម្ម (Group Members & Fee Grid)</h3>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button type="button" class="btn btn-success" onclick="addGroupMemberRow()">➕ បន្ថែមសមាជិក 1 នាក់</button>
                    </div>
                </div>

                <!-- Quick Service & Fee Preset Bar -->
                <div class="quick-fee-bar">
                    <span style="font-weight: 700; color: var(--accent-cyan); font-size: 0.9rem;">⚡ ប៊ូតុងថ្លៃ និងសេវា (Fee Presets):</span>
                    <button type="button" class="fee-btn-preset" onclick="applyPresetFees(280, 40, 0, 0, 0, 0)">👑 VIP Standard ($280+$40)</button>
                    <button type="button" class="fee-btn-preset" onclick="applyPresetFees(280, 40, 0, 50, 0, 0)">🚗 VIP + Car ($370)</button>
                    <button type="button" class="fee-btn-preset" onclick="applyPresetFees(280, 40, 0, 0, 0, 35)">💻 VIP + E-Visa ($355)</button>
                    <button type="button" class="fee-btn-preset" onclick="applyPresetFees(0, 0, 0, 0, 0, 0)">🧹 កំណត់ថ្លៃ 0.00</button>
                    
                    <div style="margin-left: auto; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 0.85rem; color: var(--text-muted);">ចំនួន Pax:</span>
                        <input type="number" id="paxBatchInput" class="form-control num-input" value="3" style="width: 65px; padding: 4px 8px; text-align: center;" min="1" max="100">
                        <button type="button" class="btn btn-primary btn-sm" onclick="generatePaxRows()">⚡ បង្កើតជួរ Pax</button>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="custom-table">
                        <thead>
                            <tr>
                                <th style="width: 40px;">#</th>
                                <th style="min-width: 180px;">ឈ្មោះសមាជិក (Customer Name)</th>
                                <th style="min-width: 130px;">លេខ Passport</th>
                                <th style="width: 100px;">សញ្ជាតិ</th>
                                <th style="width: 95px;">VIP ($)</th>
                                <th style="width: 95px;">Clearance ($)</th>
                                <th style="width: 95px;">Permit ($)</th>
                                <th style="width: 95px;">Car ($)</th>
                                <th style="width: 95px;">Visa ($)</th>
                                <th style="width: 95px;">E-Visa ($)</th>
                                <th style="width: 110px;">សរុប USD</th>
                                <th style="width: 50px;">លុប</th>
                            </tr>
                        </thead>
                        <tbody id="groupMembersBody">
                            <!-- Default Row 1 -->
                            <tr>
                                <td class="text-center font-bold row-num">1</td>
                                <td><input type="text" name="member_name[]" class="form-control" placeholder="Customer Name" required></td>
                                <td><input type="text" name="member_passport[]" class="form-control" placeholder="Passport No"></td>
                                <td><input type="text" name="member_nationality[]" class="form-control" value="THAI"></td>
                                <td><input type="number" step="0.01" name="member_vip[]" class="form-control fee-calc input-vip num-input" value="280.00"></td>
                                <td><input type="number" step="0.01" name="member_clearance[]" class="form-control fee-calc input-clearance num-input" value="40.00"></td>
                                <td><input type="number" step="0.01" name="member_work_permit[]" class="form-control fee-calc input-work-permit num-input" value="0.00"></td>
                                <td><input type="number" step="0.01" name="member_car_fee[]" class="form-control fee-calc input-car-fee num-input" value="0.00"></td>
                                <td><input type="number" step="0.01" name="member_visa_fee[]" class="form-control fee-calc input-visa-fee num-input" value="0.00"></td>
                                <td><input type="number" step="0.01" name="member_evisa[]" class="form-control fee-calc input-evisa num-input" value="0.00"></td>
                                <td><input type="number" step="0.01" name="member_total_usd[]" class="form-control input-total-usd num-input" value="320.00" readonly></td>
                                <td class="text-center">
                                    <button type="button" class="btn btn-danger btn-sm" onclick="removeGroupMemberRow(this)">🗑️</button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Grand Total Footer Bar -->
                <div style="margin-top: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; background: rgba(15,23,42,0.9); padding: 16px 20px; border-radius: var(--radius-md); border: 1px solid var(--border-color);">
                    <div style="display: flex; gap: 24px; align-items: center;">
                        <div>
                            <span style="color: var(--text-muted); font-size: 0.85rem;">ចំនួនសមាជិក៖</span>
                            <span id="paxCountLabel" style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-left: 6px;">1 Pax</span>
                        </div>
                        <div>
                            <span style="color: var(--text-muted); font-size: 0.85rem;">សរុប (USD)៖</span>
                            <span id="grandTotalUSD" style="font-weight: 800; color: var(--accent-emerald); font-size: 1.4rem; margin-left: 6px;">$320.00</span>
                        </div>
                        <div>
                            <span style="color: var(--text-muted); font-size: 0.85rem;">សរុប (THB)៖</span>
                            <span id="grandTotalTHB" style="font-weight: 800; color: var(--accent-cyan); font-size: 1.3rem; margin-left: 6px;">฿10,848.00</span>
                        </div>
                    </div>

                    <div style="display: flex; gap: 12px;">
                        <a href="index.php" class="btn btn-secondary">❌ បោះបង់</a>
                        <button type="submit" class="btn btn-emerald" style="padding: 10px 24px; font-size: 1rem;">💾 រក្សាទុកវិក្កយបត្រ (Save Invoice)</button>
                    </div>
                </div>
            </div>

        </form>

    </div>

    <script src="assets/js/app.js"></script>
    <script>
        const groupDropZone = document.getElementById('groupDropZone');
        const groupFileInput = document.getElementById('groupFileInput');
        const groupOcrStatus = document.getElementById('groupOcrStatus');

        if (groupDropZone && groupFileInput) {
            groupDropZone.addEventListener('click', () => groupFileInput.click());

            groupFileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    processBatchPassports(e.target.files);
                }
            });

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                groupDropZone.addEventListener(eventName, e => {
                    e.preventDefault();
                    e.stopPropagation();
                });
            });

            groupDropZone.addEventListener('drop', e => {
                let dt = e.dataTransfer;
                let files = dt.files;
                if (files.length > 0) {
                    processBatchPassports(files);
                }
            });
        }

        function processBatchPassports(files) {
            if (!files || files.length === 0) return;

            groupOcrStatus.style.display = 'block';
            groupOcrStatus.textContent = `⌛ AI Document AI កំពុងស្កេនរូបភាព ${files.length} សន្លឹក...`;

            let formData = new FormData();
            Array.from(files).forEach(f => formData.append('images[]', f));

            fetch('ocr_scan.php', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(res => {
                groupOcrStatus.style.display = 'none';
                if (res.success && res.results && res.results.length > 0) {
                    const tbody = document.getElementById('groupMembersBody');

                    res.results.forEach(item => {
                        const name = item.full_english_name || 'PASSPORT CUSTOMER';
                        const passNo = item.passport_no || '';
                        const nat = item.nationality || 'THAI';

                        let emptyRow = null;
                        tbody.querySelectorAll('tr').forEach(r => {
                            const nameInp = r.querySelector('input[name="member_name[]"]');
                            if (nameInp && !nameInp.value.trim() && !emptyRow) {
                                emptyRow = r;
                            }
                        });

                        if (emptyRow) {
                            emptyRow.querySelector('input[name="member_name[]"]').value = name;
                            emptyRow.querySelector('input[name="member_passport[]"]').value = passNo;
                            emptyRow.querySelector('input[name="member_nationality[]"]').value = nat;
                        } else {
                            addGroupMemberRowWithData(name, passNo, nat);
                        }
                    });

                    calculateGrandTotal();
                }
            })
            .catch(err => {
                groupOcrStatus.style.display = 'none';
                console.log('Group OCR Error:', err);
            });
        }

        function addGroupMemberRowWithData(name, passNo, nat) {
            const tableBody = document.getElementById('groupMembersBody');
            if (!tableBody) return;

            const rowCount = tableBody.querySelectorAll('tr').length + 1;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-center font-bold row-num">${rowCount}</td>
                <td><input type="text" name="member_name[]" class="form-control" value="${name}" placeholder="Customer Name" required></td>
                <td><input type="text" name="member_passport[]" class="form-control" value="${passNo}" placeholder="Passport No"></td>
                <td><input type="text" name="member_nationality[]" class="form-control" value="${nat}"></td>
                <td><input type="number" step="0.01" name="member_vip[]" class="form-control fee-calc input-vip num-input" value="280.00"></td>
                <td><input type="number" step="0.01" name="member_clearance[]" class="form-control fee-calc input-clearance num-input" value="40.00"></td>
                <td><input type="number" step="0.01" name="member_work_permit[]" class="form-control fee-calc input-work-permit num-input" value="0.00"></td>
                <td><input type="number" step="0.01" name="member_car_fee[]" class="form-control fee-calc input-car-fee num-input" value="0.00"></td>
                <td><input type="number" step="0.01" name="member_visa_fee[]" class="form-control fee-calc input-visa-fee num-input" value="0.00"></td>
                <td><input type="number" step="0.01" name="member_evisa[]" class="form-control fee-calc input-evisa num-input" value="0.00"></td>
                <td><input type="number" step="0.01" name="member_total_usd[]" class="form-control input-total-usd num-input" value="320.00" readonly></td>
                <td class="text-center">
                    <button type="button" class="btn btn-danger btn-sm" onclick="removeGroupMemberRow(this)">🗑️</button>
                </td>
            `;
            tableBody.appendChild(tr);
            calculateRowTotal(tr);
            calculateGrandTotal();
        }
    </script>
</body>
</html>
