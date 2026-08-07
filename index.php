<?php
/**
 * CMP Golden Mekong Commercial Service - Main Web Application & Invoice Manager
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

$invoices = load_saved_customers();
$nextReceiptNo = get_next_invoice_no();
?>
<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= APP_NAME ?> - AI OCR Passport Scanner & VIP Border Service</title>
    <link rel="stylesheet" href="assets/css/styles.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
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
            <a href="index.php" class="nav-btn active">📊 ផ្ទាំងគ្រប់គ្រង (Dashboard)</a>
            <a href="group_invoice.php" class="nav-btn btn-emerald">👥 + បង្កើតក្រុម (Group Invoice)</a>
            <a href="single_invoice.php" class="nav-btn">👤 + វិក្កយបត្រទោល (Single)</a>
        </div>
    </header>

    <!-- Top Window Status Bar -->
    <div class="app-topbar">
        <div class="topbar-title">
            <span>🧾 GOLDEN MEKONG COMMERCIAL SERVICE</span>
            <span style="color: var(--accent-cyan); font-size: 13px;">| AI OCR Passport Scanner & VIP Border Service System</span>
        </div>
        <div class="status-badge">
            🟢 System Ready | RapidOCR / Tesseract OCR, Batch Group OCR & VIP Service Engine (PHP Server Active)
        </div>
    </div>

    <!-- Main Workspace Top Splitter (Left: Scanner | Right: Group Form) -->
    <div class="workspace-grid">
        
        <!-- Left Panel: Passport Scanner -->
        <div class="panel-box">
            <div class="panel-title">📷 PASSPORT / ID IMAGE SCANNER</div>

            <div id="dropZone" class="dropzone-box">
                <div style="font-size: 2.5rem; margin-bottom: 8px;">📁</div>
                <div style="font-weight: 700; color: #fff; margin-bottom: 4px;">Drag & Drop Passport Image(s) Here</div>
                <div style="font-size: 11px; color: var(--text-sub); margin-bottom: 12px;">(អាច Drag & Drop រូបភាព Passport 1 ឬច្រើនក្នុងពេលតែមួយ)</div>
                <div style="font-size: 11px; color: #64748b;">ឬចុចប៊ូតុងខាងក្រោមដើម្បី Upload / ថតកាមេរ៉ា</div>
                <input type="file" id="fileInput" accept="image/*" multiple style="display: none;" onchange="handleImageFiles(this.files)">
            </div>

            <div id="ocrSpinner" style="margin-top: 8px; font-size: 11px; color: var(--accent-cyan); text-align: center; display: none;">
                ⏳ AI Document AI កំពុងស្កេនរូបភាព (Processing Batch OCR...)...
            </div>

            <div id="imagePreviewBox" style="margin-top: 8px; text-align: center; display: none;">
                <img id="previewImage" src="" alt="Passport Preview" style="max-width: 100%; max-height: 180px; border-radius: 6px; border: 1px solid var(--border-color);">
                <div id="batchScanCountLabel" style="font-size: 11px; color: var(--accent-emerald); margin-top: 4px; font-weight: 700;"></div>
            </div>

            <div class="scanner-btn-row">
                <button type="button" class="btn-sys btn-indigo" onclick="document.getElementById('fileInput').click()">📁 Select Image File(s)</button>
                <button type="button" class="btn-sys btn-dark" onclick="alert('📹 WebCam System is Ready!')">📹 WebCam Snap</button>
            </div>
        </div>

        <!-- Right Panel: Group Customer Entry Form -->
        <div class="panel-box">
            <div class="panel-title">📋 BATCH / GROUP CUSTOMERS DATA (ទិន្នន័យបញ្ចូលជាក្រុម)</div>

            <!-- Form Fields Grid -->
            <div class="form-row">
                <div class="form-group-sm" style="grid-column: span 2;">
                    <label>ឈ្មោះអ្នកបញ្ជូន / អ្នកនាំ (Sender Name) <span style="color: #f43f5e;">*</span>:</label>
                    <input type="text" id="senderName" class="form-input" placeholder="ឧ. HR(CS)- សុខ ឬ ឈ្មោះអ្នកបញ្ជូន..." required>
                </div>

                <div class="form-group-sm">
                    <label>ថ្ងៃធ្វើដំណើរ:</label>
                    <input type="date" id="travelDate" class="form-input" style="color-scheme: dark; cursor: pointer;" onclick="this.showPicker()">
                </div>
            </div>

            <div class="form-row">
                <div class="form-group-sm" style="grid-column: span 2;">
                    <label>ឈ្មោះអតិថិជន (តាម Passport):</label>
                    <input type="text" id="custNamePassport" class="form-input" placeholder="តាមការរៀបចំលិខិតឆ្លងដែន (ឧ. SOMCHAI SUWANNAKOT)..." onkeydown="if(event.key==='Enter'){ event.preventDefault(); addPassportMember(); }">
                </div>

                <div class="form-group-sm" style="display:flex; align-items:flex-end;">
                    <button type="button" class="btn-sys btn-indigo" style="width:100%; padding:6px;" onclick="addPassportMember()">⚡ រៀបចំ Passport</button>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group-sm">
                    <label>ឈ្មោះភ្នាក់ងារ:</label>
                    <input type="text" id="agencyCompany" class="form-input">
                </div>

                <div class="form-group-sm">
                    <label>លេខវិក្កយបត្រ:</label>
                    <input type="text" id="receiptNo" class="form-input highlight-input" value="<?= htmlspecialchars($nextReceiptNo) ?>" readonly>
                </div>

                <div class="form-group-sm">
                    <label>អត្រាប្តូរប្រាក់:</label>
                    <input type="number" step="0.1" id="exchangeRate" class="form-input highlight-input" value="<?= DEFAULT_EXCHANGE_RATE ?>" oninput="calcTotals()">
                </div>
            </div>

            <!-- Quick Fee & Service Presets Bar -->
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-weight: 700; color: #38bdf8; font-size: 12px;">⚡ ប៊ូតុងថ្លៃ និងសេវា:</span>
                <button type="button" class="btn-sys btn-dark" style="font-size: 11px; padding: 4px 10px; background: rgba(30, 41, 59, 0.9); border: 1px solid #334155;" onclick="applyQuickFeePreset(280, 40, 0, 0)">👑 VIP Standard ($280+$40)</button>
                <button type="button" class="btn-sys btn-dark" style="font-size: 11px; padding: 4px 10px; background: rgba(30, 41, 59, 0.9); border: 1px solid #334155;" onclick="applyQuickFeePreset(280, 40, 50, 0)">🚗 VIP + Car ($370)</button>
                <button type="button" class="btn-sys btn-dark" style="font-size: 11px; padding: 4px 10px; background: rgba(30, 41, 59, 0.9); border: 1px solid #334155;" onclick="applyQuickFeePreset(280, 40, 0, 35)">💻 VIP + E-Visa ($355)</button>
                <button type="button" class="btn-sys btn-dark" style="font-size: 11px; padding: 4px 10px; background: rgba(30, 41, 59, 0.9); border: 1px solid #334155;" onclick="applyQuickFeePreset(0, 0, 0, 0)">🧹 កំណត់ថ្លៃ 0.00</button>
            </div>

            <div class="form-row">
                <div class="form-group-sm">
                    <label>ថ្លៃ E-VISA ($):</label>
                    <input type="number" step="0.01" id="feeEvisa" class="form-input num-input" value="" placeholder="" oninput="updateMemberFeesDefaults()">
                </div>

                <div class="form-group-sm">
                    <label>ថ្លៃ VIP ($):</label>
                    <input type="number" step="0.01" id="feeVip" class="form-input num-input" value="" placeholder="" oninput="updateMemberFeesDefaults()">
                </div>

                <div class="form-group-sm">
                    <label>ថ្លៃឡានចម្លង ($):</label>
                    <input type="number" step="0.01" id="feeCar" class="form-input num-input" value="" placeholder="" oninput="updateMemberFeesDefaults()">
                </div>
            </div>

            <!-- Pax & Controls Row -->
            <div class="control-bar">
                <div style="font-weight: 700; color: var(--accent-cyan);">
                    ចំនួនសមាជិកក្រុម: <span id="paxCountLabel">0</span> នាក់
                </div>

                <div style="display: flex; gap: 8px; align-items: center;">
                    <span style="color: var(--text-muted); font-size: 11px;">Pax:</span>
                    <input type="number" id="paxInput" class="form-input" value="3" style="width: 50px; text-align: center;" min="1" max="50">
                    <button type="button" class="btn-sys btn-indigo" onclick="setPaxRows()">⚡ ដំឡើង Pax</button>
                    <button type="button" class="btn-sys btn-dark" onclick="removeLastPaxRow()">➖ បន្ថយសមាជិក 1 នាក់</button>
                    <button type="button" class="btn-sys btn-amber" onclick="clearGroupForm()">🧹 សម្អាត Form</button>
                </div>
            </div>

            <!-- Full Width Save Button -->
            <button type="button" class="save-btn-green" onclick="saveGroupRecord()">
                💾 រក្សាទុកទិន្នន័យក្រុម (Save Group Record)
            </button>

            <!-- Inner Members Table Grid -->
            <div class="table-container" style="max-height: 180px; overflow-y: auto;">
                <table class="app-table">
                    <thead>
                        <tr>
                            <th style="width: 40px; text-align: center;">ល.រ (#)</th>
                            <th>ឈ្មោះតាមលិខិតឆ្លងដែន (Passport Name)</th>
                            <th style="width: 80px;">ថ្លៃឡាន ($)</th>
                            <th style="width: 80px;">ថ្លៃ E-VISA ($)</th>
                            <th style="width: 80px;">ថ្លៃ VIP ($)</th>
                            <th style="width: 90px;">ថ្លៃកាត់ឈ្មោះ ($)</th>
                            <th style="width: 80px;">សរុប ($)</th>
                        </tr>
                    </thead>
                    <tbody id="groupMembersBody">
                        <!-- Dynamic member rows -->
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Bottom Full Width Panel: Saved Customers Database -->
    <div class="panel-box">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div class="panel-title" style="margin-bottom: 0;">
                📋 SAVED CUSTOMERS DATABASE (បញ្ជីទិន្នន័យអតិថិជនដែលបានរក្សាទុក)
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span id="totalRecordsLabel" style="font-size: 11px; color: var(--text-sub); font-weight: 600;">សរុប: <?= count($invoices) ?> ត្រា (Total Records: <?= count($invoices) ?>)</span>
                <button type="button" class="btn-sys btn-rose btn-action-sm" onclick="clearAllRecords()">🗑️ លុបទិន្នន័យ (Clear All)</button>
            </div>
        </div>

        <!-- Search Bar Row -->
        <div style="display: flex; gap: 8px; margin-bottom: 10px;">
            <input type="text" id="searchInput" class="form-input" placeholder="🔍 ស្វែងរក៖ ឈ្មោះអ្នកផ្ញើ, លេខវិក្កយបត្រ, ថ្ងៃធ្វើដំណើរ, ឈ្មោះអតិថិជន, ស្ថានភាព (បង់រួច/មិនទាន់បង់)..." onkeyup="renderDatabaseTable()">
            <button type="button" class="btn-sys btn-indigo" onclick="renderDatabaseTable()">🔍 ស្វែងរក (Search)</button>
            <button type="button" class="btn-sys btn-dark" onclick="resetSearch()">✖️ សម្អាត (Reset)</button>
        </div>

        <!-- Database Records Table -->
        <div class="table-container">
            <table class="app-table">
                <thead>
                    <tr>
                        <th style="width: 40px; text-align: center;">ល.រ</th>
                        <th style="width: 100px;">លេខវិក្កយបត្រ</th>
                        <th style="width: 100px;">ថ្ងៃធ្វើដំណើរ</th>
                        <th style="width: 140px;">ភ្នាក់ងារ / ក្រុម</th>
                        <th style="width: 100px;">ទឹកប្រាក់សរុប</th>
                        <th style="width: 110px;">ស្ថានភាព</th>
                        <th style="width: 220px; text-align: center;">សកម្មភាព (Actions)</th>
                        <th>ឈ្មោះអតិថិជន (Customer)</th>
                    </tr>
                </thead>
                <tbody id="databaseTableBody">
                    <tr><td colspan="8" style="text-align: center; padding: 20px; color: var(--text-sub);">⏳ កំពុងទាញយកទិន្នន័យ (Loading database...)...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Group Members Management Modal -->
    <div id="groupMembersModal" class="modal-overlay">
        <div class="modal-card" style="max-width: 750px;">
            <div class="modal-toolbar" style="background: #0f172a; border-bottom: 1px solid var(--border-color); padding: 14px 20px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.4rem;">👥</div>
                    <div>
                        <div style="font-weight: 800; font-size: 16px; color: #38bdf8;" id="gmmTitle">📋 គ្រប់គ្រងសមាជិកក្រុម</div>
                        <div style="font-size: 11px; color: var(--text-sub);" id="gmmSubTitle">👤 គ្រប់គ្រងសមាជិកក្រុម: -</div>
                    </div>
                </div>
                <button type="button" class="btn-sys btn-dark" onclick="closeGroupMembersModal()">✖️ បិទ (Close)</button>
            </div>

            <div style="padding: 20px;">
                <div id="gmmAlert" style="margin-bottom: 12px; font-size: 12px; color: #cbd5e1; background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; padding: 8px 12px; border-radius: 6px;">
                    💡 លុបឈ្មោះសមាជិកចេញពីក្រុម នឹង លុបចេញពីផ្ទាំងបង្កើតវិក្កយបត្រដើម្បីកុំឱ្យគណនាលើសតម្លៃ។
                </div>

                <div class="table-container" style="max-height: 350px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 8px;">
                    <table class="app-table">
                        <thead>
                            <tr style="background: #1e293b; color: #f8fafc;">
                                <th style="width: 40px; text-align: center;">ល.រ</th>
                                <th>ឈ្មោះសមាជិក (Passport Name)</th>
                                <th style="width: 120px;">លេខ Passport</th>
                                <th style="width: 90px; text-align: center;">សញ្ជាតិ</th>
                                <th style="width: 90px; text-align: right;">តម្លៃ ($)</th>
                                <th style="width: 110px; text-align: center;">សកម្មភាព</th>
                            </tr>
                        </thead>
                        <tbody id="gmmMembersBody">
                            <!-- Dynamic member rows -->
                        </tbody>
                    </table>
                </div>
            </div>

            <div style="padding: 12px 20px; background: #0f172a; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                <div id="gmmTotalFooter" style="font-size: 13px; font-weight: 700; color: var(--accent-emerald);">
                    💵 ថ្លៃសេវាសរុប៖ $0.00
                </div>
                <button type="button" class="btn-sys btn-dark" onclick="closeGroupMembersModal()">❌ បិទផ្ទាំង (Close)</button>
            </div>
        </div>
    </div>


    <!-- Official Receipt Printable Modal Popup -->
    <div id="receiptModal" class="modal-overlay">
        <div class="modal-card">
            <div class="modal-toolbar">
                <div style="font-weight: 700; font-size: 16px; color: #0f172a;">🧾 Official Receipt Preview</div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn-sys btn-indigo" onclick="window.print()">🖨️ បោះពុម្ព (Print)</button>
                    <button class="btn-sys btn-emerald" onclick="downloadReceiptPNG()">🖼️ PNG Image</button>
                    <button class="btn-sys btn-purple" onclick="shareReceiptTelegram()">✈️ Telegram</button>
                    <button class="btn-sys btn-dark" onclick="closeReceiptModal()">❌ បិទ (Close)</button>
                </div>
            </div>

            <!-- Receipt Document Content -->
            <div id="printableReceiptArea" style="background: #ffffff; color: #0f172a; padding: 40px 48px; border-radius: 12px; box-sizing: border-box; width: 100%; max-width: 850px; margin: 0 auto; position: relative;">
                <div id="mStampContainer" style="position: absolute; top: 25px; right: 25px; z-index: 10;"></div>
                <div style="border-bottom: 2px double #cbd5e1; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between;">

                    <div>
                        <div style="font-size: 0.85rem; font-weight: 700; color: #0284c7;"><?= COMPANY_NAME_KH ?></div>
                        <div style="font-size: 0.92rem; font-weight: 700; color: #0f172a;"><?= COMPANY_NAME_EN ?></div>

                        <div style="font-size: 0.75rem; color: #475569; margin-top: 4px;">
                            📍 <?= COMPANY_ADDRESS ?><br>
                            📞 Tel: <?= COMPANY_PHONE ?>
                        </div>

                    </div>

                    <div style="text-align: right;">
                        <div style="font-size: 0.75rem; font-weight: 700; color: #64748b;">INVOICE</div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #0f172a;">OFFICIAL INVOICE</div>
                        <div style="font-size: 0.88rem; font-weight: 800; color: #0284c7; margin-top: 4px;">
                            No: <span id="mReceiptNo">INV ...</span>
                        </div>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-size: 0.85rem;">
                    <div>
                        <div><strong>Customer / Group Name:</strong> <span id="mSenderName">-</span></div>
                        <div><strong>Agency / Company:</strong> <span id="mAgencyName">-</span></div>
                    </div>
                    <div style="text-align: right;">
                        <div><strong>Travel Date:</strong> <span id="mTravelDate">-</span></div>
                        <div><strong>Exchange Rate:</strong> <span id="mRate">1 USD = <?= DEFAULT_EXCHANGE_RATE ?> THB</span></div>
                        <div><strong>Date Issued:</strong> <span id="mDateSaved">-</span></div>
                    </div>
                </div>

                <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 0.85rem;">
                    <thead>
                        <tr style="background: #0f172a; color: #ffffff;">
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 35px; text-align: center;">No</th>
                            <th style="padding: 8px; border: 1px solid #0f172a;">Customer Name</th>
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 70px; text-align: right;">VIP</th>
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 75px; text-align: right;">Clearance</th>
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 70px; text-align: right;">Permit</th>
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 70px; text-align: right;">Car/Visa</th>
                            <th style="padding: 8px; border: 1px solid #0f172a; width: 85px; text-align: right;">Total USD</th>
                        </tr>
                    </thead>
                    <tbody id="mReceiptItemsBody">
                        <!-- Dynamic items -->
                    </tbody>
                </table>

                <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: 12px; gap: 16px;">
                    <!-- Bank Details Card -->
                    <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 16px; font-size: 0.82rem; flex-grow: 1; color: #0f172a;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; line-height: 1.5;">
                            <div>
                                <div><strong>Bank:</strong> <span style="font-weight: 700; color: #0284c7;">ABA</span></div>
                                <div><strong>Account:</strong> <span style="font-weight: 700; color: #0f172a;">005 870 215</span></div>
                                <div><strong>Name:</strong> <span style="font-weight: 700; color: #0f172a;">Hol Sokha</span></div>
                            </div>
                            <div>
                                <div><strong>Bank:</strong> <span style="font-weight: 700; color: #4f46e5;">ไทยพาณិชย์</span></div>
                                <div><strong>Account:</strong> <span style="font-weight: 700; color: #0f172a;">6924007211</span></div>
                                <div><strong>Name:</strong> <span style="font-weight: 700; color: #0f172a;">Mr. KHLORNG ORN</span></div>
                            </div>
                        </div>
                    </div>

                    <div style="width: 270px; flex-shrink: 0;">
                        <div style="display:flex; justify-content:space-between; padding:4px 8px; border-bottom:1px solid #e2e8f0; font-size:0.85rem;">
                            <span>Total Pax:</span><strong id="mPaxCount">1 Pax</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; padding:6px 8px; font-size:0.95rem; font-weight:800; color:#0284c7; background:#f0f9ff; border-radius:6px; margin-top:4px;">
                            <span>GRAND TOTAL:</span><span id="mGrandUSD">$0.00</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; padding:4px 8px; color:#0284c7; font-weight:700; font-size:0.82rem;">
                            <span>Total Baht (THB):</span><span id="mGrandTHB">฿0.00</span>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    </div>

    <!-- Web App JavaScript Engine -->
    <script>
        let allDatabaseRecords = <?= json_encode($invoices) ?> || [];
        let currentModalReceiptData = null;

        document.addEventListener('DOMContentLoaded', () => {
            const now = new Date();
            const yyyy = now.getFullYear();
            const mm = String(now.getMonth() + 1).padStart(2, '0');
            const dd = String(now.getDate()).padStart(2, '0');
            document.getElementById('travelDate').value = `${yyyy}-${mm}-${dd}`;

            fetchNextReceiptNo();
            setPaxRows();
            loadDatabaseRecords();
            setupDropZone();
        });

        function apiFetch(endpoint, options = {}) {
            let url = endpoint;
            if (!url.startsWith('http') && !url.startsWith('api.php')) {
                if (url.startsWith('/api/')) {
                    const action = url.substring(5).split('?')[0];
                    const query = url.includes('?') ? '&' + url.split('?')[1] : '';
                    url = `api.php?action=${action}${query}`;
                }
            }
            return fetch(url, options);
        }

        function fetchNextReceiptNo() {
            apiFetch('/api/next_no')
                .then(r => r.json())
                .then(d => {
                    if (d.next_no) document.getElementById('receiptNo').value = d.next_no;
                })
                .catch(e => console.log('Fetch error:', e));
        }

        function setPaxRows() {
            const count = parseInt(document.getElementById('paxInput').value || 3);
            const tbody = document.getElementById('groupMembersBody');
            tbody.innerHTML = '';

            for (let i = 1; i <= count; i++) {
                addMemberRow(i);
            }

            document.getElementById('paxCountLabel').textContent = count;
            calcTotals();
        }

        function handleNameKeydown(event, input) {
            if (event.key === 'Enter' || event.key === 'ArrowDown') {
                if (event.key === 'Enter') event.preventDefault();
                const tr = input.closest('tr');
                let nextTr = tr ? tr.nextElementSibling : null;
                if (!nextTr && event.key === 'Enter') {
                    addMemberRow();
                    const tbody = document.getElementById('groupMembersBody');
                    nextTr = tbody ? tbody.lastElementChild : null;
                    const paxInput = document.getElementById('paxInput');
                    if (paxInput && tbody) {
                        paxInput.value = tbody.children.length;
                    }
                }
                if (nextTr) {
                    const nextInput = nextTr.querySelector('.input-m-name');
                    if (nextInput) {
                        nextInput.focus();
                        nextInput.select();
                    }
                }
            } else if (event.key === 'ArrowUp') {
                const tr = input.closest('tr');
                const prevTr = tr ? tr.previousElementSibling : null;
                if (prevTr) {
                    const prevInput = prevTr.querySelector('.input-m-name');
                    if (prevInput) {
                        prevInput.focus();
                        prevInput.select();
                    }
                }
            }
        }

        function addMemberRow(rowNum, name = '', pass = '') {
            const tbody = document.getElementById('groupMembersBody');
            const num = rowNum || (tbody.children.length + 1);

            const vip = parseFloat(document.getElementById('feeVip').value || 0);
            const car = parseFloat(document.getElementById('feeCar').value || 0);
            const evisa = parseFloat(document.getElementById('feeEvisa').value || 0);
            const clearance = 0.0;
            const fmtVal = v => (v > 0 ? (v % 1 === 0 ? v : v.toFixed(2)) : '');

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-center font-bold" style="text-align:center;">${num}</td>
                <td><input type="text" class="form-input input-m-name" value="${name}" placeholder="ឈ្មោះតាម Passport (ឧ. SOMCHAI SUWANNAKOT)..." oninput="calcTotals()" onfocus="this.select()" onkeydown="handleNameKeydown(event, this)"></td>
                <td><input type="number" step="0.01" class="form-input input-m-car num-input" value="${fmtVal(car)}" placeholder="" oninput="calcMemberTotal(this)"></td>
                <td><input type="number" step="0.01" class="form-input input-m-evisa num-input" value="${fmtVal(evisa)}" placeholder="" oninput="calcMemberTotal(this)"></td>
                <td><input type="number" step="0.01" class="form-input input-m-vip num-input" value="${fmtVal(vip)}" placeholder="" oninput="calcMemberTotal(this)"></td>
                <td><input type="number" step="0.01" class="form-input input-m-clearance num-input" value="${fmtVal(clearance)}" placeholder="" oninput="calcMemberTotal(this)"></td>
                <td><input type="number" step="0.01" class="form-input input-m-total num-input" value="${fmtVal(vip+car+evisa+clearance)}" readonly></td>
            `;
            tbody.appendChild(tr);
            document.getElementById('paxCountLabel').textContent = tbody.children.length;
        }

        function removeLastPaxRow() {
            const tbody = document.getElementById('groupMembersBody');
            if (tbody.children.length <= 1) return;
            tbody.lastElementChild.remove();
            document.getElementById('paxInput').value = tbody.children.length;
            document.getElementById('paxCountLabel').textContent = tbody.children.length;
            calcTotals();
        }

        function updateMemberFeesDefaults() {
            const vip = parseFloat(document.getElementById('feeVip').value || 0);
            const car = parseFloat(document.getElementById('feeCar').value || 0);
            const evisa = parseFloat(document.getElementById('feeEvisa').value || 0);
            const fmtVal = v => (v > 0 ? (v % 1 === 0 ? v : v.toFixed(2)) : '');

            document.querySelectorAll('#groupMembersBody tr').forEach(r => {
                r.querySelector('.input-m-vip').value = fmtVal(vip);
                r.querySelector('.input-m-car').value = fmtVal(car);
                r.querySelector('.input-m-evisa').value = fmtVal(evisa);
                calcMemberTotal(r.querySelector('.input-m-vip'));
            });
        }

        function calcMemberTotal(el) {
            const row = el.closest('tr');
            const getV = sel => parseFloat(row.querySelector(sel)?.value || 0);
            const total = getV('.input-m-car') + getV('.input-m-evisa') + getV('.input-m-vip') + getV('.input-m-clearance');
            const fmtVal = v => (v > 0 ? (v % 1 === 0 ? v : v.toFixed(2)) : '');
            row.querySelector('.input-m-total').value = fmtVal(total);
            calcTotals();
        }

        function calcTotals() {
            // Handled automatically
        }

        function addPassportMember() {
            const rawVal = document.getElementById('custNamePassport').value.trim();
            if (!rawVal) {
                alert('សូមបញ្ចូលឈ្មោះអតិថិជន (តាម Passport)!');
                return;
            }

            const names = rawVal.split(/[\n,;]+/).map(n => n.trim()).filter(n => n.length > 0);
            if (names.length === 0) return;

            const tbody = document.getElementById('groupMembersBody');
            
            names.forEach(name => {
                let emptyRow = null;
                tbody.querySelectorAll('tr').forEach(r => {
                    const nameInp = r.querySelector('.input-m-name');
                    if (nameInp && (!nameInp.value.trim() || nameInp.value.trim() === 'Passport Name') && !emptyRow) {
                        emptyRow = r;
                    }
                });

                if (emptyRow) {
                    const nameInp = emptyRow.querySelector('.input-m-name');
                    nameInp.value = name;
                    calcMemberTotal(nameInp);
                } else {
                    addMemberRow(tbody.children.length + 1, name);
                }
            });

            const paxInput = document.getElementById('paxInput');
            if (paxInput) paxInput.value = tbody.children.length;
            document.getElementById('paxCountLabel').textContent = tbody.children.length;

            document.getElementById('custNamePassport').value = '';
            document.getElementById('custNamePassport').focus();
        }

        function applyQuickFeePreset(vip, clearance, car, evisa) {
            const tbody = document.getElementById('groupMembersBody');
            if (!tbody) return;
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(r => {
                const inpCar = r.querySelector('.input-m-car');
                const inpEvisa = r.querySelector('.input-m-evisa');
                const inpVip = r.querySelector('.input-m-vip');
                const inpClearance = r.querySelector('.input-m-clearance');

                if (inpCar) inpCar.value = car ? car.toFixed(2) : '0.00';
                if (inpEvisa) inpEvisa.value = evisa ? evisa.toFixed(2) : '0.00';
                if (inpVip) inpVip.value = vip ? vip.toFixed(2) : '0.00';
                if (inpClearance) inpClearance.value = clearance ? clearance.toFixed(2) : '0.00';

                const nameInp = r.querySelector('.input-m-name');
                if (nameInp) calcMemberTotal(nameInp);
            });
            calcTotals();
        }

        function clearGroupForm() {
            document.getElementById('senderName').value = '';
            document.getElementById('custNamePassport').value = '';
            document.getElementById('agencyCompany').value = '';
            document.getElementById('feeEvisa').value = '0.00';
            document.getElementById('feeVip').value = '0.00';
            document.getElementById('feeCar').value = '0.00';
            document.getElementById('paxInput').value = 3;
            setPaxRows();
        }

        function saveGroupRecord() {
            const sender = document.getElementById('senderName').value.trim();
            if (!sender) {
                alert('⚠️ សូមបញ្ចូលឈ្មោះអ្នកផ្ញើ / អ្នកនាំ (Sender Name) ជាមុនសិន ទើបអាចរក្សាទុកបាន!');
                document.getElementById('senderName').focus();
                return;
            }
            const rawDate = document.getElementById('travelDate').value.trim();
            let travelDate = rawDate;
            if (rawDate && rawDate.includes('-')) {
                const parts = rawDate.split('-');
                if (parts.length === 3 && parts[0].length === 4) {
                    travelDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                }
            }
            const agency = document.getElementById('agencyCompany').value.trim();
            const rate = parseFloat(document.getElementById('exchangeRate').value || <?= DEFAULT_EXCHANGE_RATE ?>);
            const receiptNoVal = document.getElementById('receiptNo').value;

            const members = [];
            document.querySelectorAll('#groupMembersBody tr').forEach(r => {
                const name = r.querySelector('.input-m-name').value.trim();
                if (name) {
                    members.push({
                        name: name,
                        car_fee: parseFloat(r.querySelector('.input-m-car').value || 0),
                        evisa: parseFloat(r.querySelector('.input-m-evisa').value || 0),
                        vip: parseFloat(r.querySelector('.input-m-vip').value || 0),
                        clearance: parseFloat(r.querySelector('.input-m-clearance').value || 0),
                        work_permit: 0.0
                    });
                }
            });

            if (members.length === 0) {
                alert('សូមបញ្ចូលឈ្មោះសមាជិកយ៉ាងហោចណាស់ 1 នាក់!');
                return;
            }

            const now = new Date();
            const dateSaved = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${now.getFullYear()} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

            const payload = {
                receipt_no: receiptNoVal,
                group_name: sender,
                customer_name: members[0].name,
                agency_company: agency,
                travel_date: travelDate,
                exchange_rate: rate,
                payment_status: 'UNPAID',
                date_saved: encodeURIComponent(dateSaved),
                members: members
            };

            apiFetch('/api/save_group', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    alert('🎉 រក្សាទុកទិន្នន័យក្រុមបានជោគជ័យ!');
                    fetchNextReceiptNo();
                    clearGroupForm();
                    loadDatabaseRecords();
                } else {
                    alert('បរាជ័យក្នុងការរក្សាទុក៖ ' + (res.error || ''));
                }
            })
            .catch(e => {
                alert('កំហុសក្នុងការផ្ញើទិន្នន័យទៅ Server');
            });
        }

        /* Database Records Loader & Table Renderer */
        function loadDatabaseRecords() {
            apiFetch('/api/invoices')
                .then(r => r.json())
                .then(d => {
                    if (d.success) {
                        allDatabaseRecords = d.invoices || [];
                        renderDatabaseTable();
                    }
                })
                .catch(() => renderDatabaseTable());
        }

        function renderDatabaseTable() {
            const tbody = document.getElementById('databaseTableBody');
            const search = document.getElementById('searchInput').value.toLowerCase().trim();

            let filtered = allDatabaseRecords.filter(item => {
                if (!search) return true;
                return JSON.stringify(item).toLowerCase().includes(search);
            });

            document.getElementById('totalRecordsLabel').textContent = `សរុប: ${filtered.length} ត្រា (Total Records: ${filtered.length})`;

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:var(--text-sub);">មិនមានទិន្នន័យអតិថិជនឡើយ</td></tr>`;
                return;
            }

            let html = '';
            filtered.forEach((item, idx) => {
                const rNo = item.group_data?.receipt_no || item.customer?.receipt_no || 'N/A';
                const travelDate = item.group_info?.travel_date || item.group_data?.date_str || item.customer?.date_saved || '-';
                const sender = item.group_info?.group_name || item.customer?.full_english_name || 'N/A';
                const custName = item.group_info?.customer_name || item.customer?.full_english_name || '-';
                const members = item.members || [];
                const paxCount = members.length || 1;
                const isGroup = paxCount > 1;
                const custLabel = isGroup ? `${custName} (+${paxCount-1} នាក់)` : custName;
                const usdTotal = parseFloat(item.group_data?.totals?.usd || item.totals?.usd || 0);
                const status = (item.payment_status || 'UNPAID').toUpperCase();

                let custContent = '';
                if (isGroup) {
                    custContent = `
                        <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; padding:2px 4px;">
                            <span style="font-weight:600; color:#e2e8f0;">👥 ${custLabel}</span>
                            <button type="button" class="btn-sys btn-indigo btn-action-sm" style="font-size:11px; padding:3px 8px; font-weight:700; background: linear-gradient(135deg, #0284c7, #2563eb); border: 1px solid #38bdf8; color: #ffffff;" onclick="event.stopPropagation(); openGroupMembersModal('${encodeURIComponent(rNo)}')">👁️ មើលលម្អិត (${paxCount})</button>
                        </div>
                    `;
                } else {
                    custContent = `
                        <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; padding:2px 4px;">
                            <span style="font-weight:600; color:#f8fafc;">👤 ${custName}</span>
                            <button type="button" class="btn-sys btn-amber btn-action-sm" style="font-size:10px; padding:2px 6px;" onclick="event.stopPropagation(); loadRecordIntoForm('${encodeURIComponent(rNo)}')">✏️ កែប្រែ</button>
                        </div>
                    `;
                }

                html += `
                    <tr style="cursor:pointer; vertical-align:top;" title="ចុចទីនេះដើម្បីមើលសមាជិកក្រុម" onclick="openGroupMembersModal('${encodeURIComponent(rNo)}')">
                        <td style="text-align:center; font-weight:bold;">${idx + 1}</td>
                        <td style="font-weight:700; color:var(--accent-cyan);">${rNo}</td>
                        <td>${travelDate}</td>
                        <td><strong style="color:#fff;">${sender}</strong></td>
                        <td style="font-weight:700; color:var(--accent-emerald);">$${usdTotal.toFixed(2)}</td>
                        <td onclick="event.stopPropagation()">
                            <span class="badge-status ${status==='PAID'?'badge-paid-st':'badge-unpaid-st'}" onclick="toggleStatus('${encodeURIComponent(rNo)}', '${status==='PAID'?'UNPAID':'PAID'}')">
                                ${status==='PAID'?'✅ បង់រួច':'❌ មិនទាន់បង់'}
                            </span>
                        </td>
                        <td style="text-align:center; white-space:nowrap;" onclick="event.stopPropagation()">
                            <button class="btn-sys btn-purple btn-action-sm" onclick="openReceiptModal('${encodeURIComponent(rNo)}')">✈️ Share</button>
                            <button class="btn-sys btn-indigo btn-action-sm" style="background:#0284c7; color:#fff;" onclick="openGroupMembersModal('${encodeURIComponent(rNo)}')">👁️ មើលលម្អិត</button>
                            <button class="btn-sys btn-rose btn-action-sm" onclick="deleteRecord('${encodeURIComponent(rNo)}')">🗑️ Delete</button>
                        </td>
                        <td onclick="event.stopPropagation()">${custContent}</td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
        }

        let currentGmmReceiptNo = '';

        function openGroupMembersModal(rNoEnc) {
            const rNo = decodeURIComponent(rNoEnc);
            currentGmmReceiptNo = rNo;
            apiFetch(`/api/receipt?no=${encodeURIComponent(rNo)}`)
                .then(r => r.json())
                .then(res => {
                    if (!res.success || (!res.invoice && !res.data)) {
                        alert('មិនអាចរកឃើញទិន្នន័យវិក្កយបត្រនេះទេ');
                        return;
                    }
                    const item = res.invoice || res.data;
                    const members = item.members || [];
                    const sender = item.group_info?.group_name || item.group_data?.customer_name || item.customer?.full_english_name || 'VIP Group';

                    document.getElementById('gmmTitle').textContent = `📋 គ្រប់គ្រងសមាជិកក្រុម ${rNo} (${members.length} នាក់)`;
                    document.getElementById('gmmSubTitle').textContent = `👤 គ្រប់គ្រងសមាជិកក្រុម: ${sender}`;
                    
                    renderGmmMembersList(members, rNo);

                    const modal = document.getElementById('groupMembersModal');
                    if (modal) modal.style.display = 'flex';
                })
                .catch(err => {
                    alert('កំហុសក្នុងការទាញយកទិន្នន័យសមាជិក');
                });
        }

        function renderGmmMembersList(members, rNo) {
            const tbody = document.getElementById('gmmMembersBody');
            if (!tbody) return;

            let totalUsd = 0;
            if (!members || members.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-sub);">មិនមានសមាជិកនៅក្នុងក្រុមនេះទេ</td></tr>`;
                document.getElementById('gmmTotalFooter').textContent = `💵 ថ្លៃសេវាសរុប៖ $0.00`;
                return;
            }

            let html = '';
            members.forEach((m, idx) => {
                const name = m.full_english_name || m.english_name || m.name || 'N/A';
                const pass = m.passport_no || '-';
                const nat = m.nationality || 'THAI';
                let usd = parseFloat(m.usd || 0);
                if (usd === 0) {
                    usd = (parseFloat(m.vip||0) + parseFloat(m.clearance_fee||0) + parseFloat(m.work_permit||0) + parseFloat(m.car_fee||0) + parseFloat(m.visa_fee||0) + parseFloat(m.e_visa||0));
                }
                totalUsd += usd;

                html += `
                    <tr>
                        <td style="text-align:center; font-weight:bold; color:var(--accent-cyan);">${idx + 1}</td>
                        <td style="font-weight:700; color:#fff;">${name}</td>
                        <td style="color:var(--accent-cyan); font-family:monospace;">${pass}</td>
                        <td style="text-align:center;"><span class="badge-status" style="background:#1e293b; color:#38bdf8;">${nat}</span></td>
                        <td style="text-align:right; font-weight:700; color:var(--accent-emerald);">$${usd.toFixed(2)}</td>
                        <td style="text-align:center;">
                            <button type="button" class="btn-sys btn-rose btn-action-sm" style="font-size:11px; padding:4px 10px; background:#dc2626; color:#ffffff; font-weight:bold; border-radius:4px;" onclick="deleteMemberFromGroup('${encodeURIComponent(rNo)}', ${idx}, '${encodeURIComponent(name)}')">
                                ❌ លុបចេញ
                            </button>
                        </td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
            document.getElementById('gmmTotalFooter').textContent = `💵 ថ្លៃសេវាសរុប៖ $${totalUsd.toFixed(2)}`;
        }

        function deleteMemberFromGroup(rNoEnc, index, nameEnc) {
            const rNo = decodeURIComponent(rNoEnc);
            const name = decodeURIComponent(nameEnc);

            if (!confirm(`តើលោកអ្នកពិតជាចង់លុបសមាជិកឈ្មោះ "${name}" ចេញពីក្រុមនេះមែនទេ?`)) {
                return;
            }

            apiFetch(`/api/delete_member?no=${encodeURIComponent(rNo)}&index=${index}`)
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        loadDatabaseRecords();
                        openGroupMembersModal(encodeURIComponent(rNo));
                    } else {
                        alert('បរាជ័យក្នុងការលុបសមាជិក៖ ' + (res.error || ''));
                    }
                })
                .catch(err => {
                    alert('កំហុសក្នុងការផ្ញើទិន្នន័យលុបសមាជិក');
                });
        }

        function closeGroupMembersModal() {
            const modal = document.getElementById('groupMembersModal');
            if (modal) modal.style.display = 'none';
        }

        function toggleStatus(rNo, newStatus) {
            apiFetch(`/api/toggle_status?no=${rNo}&status=${newStatus}`)
                .then(r => r.json())
                .then(res => { if (res.success) loadDatabaseRecords(); });
        }

        function deleteRecord(rNo) {
            if (confirm(`តើអ្នកពិតជាចង់លុបវិក្កយបត្រ ${decodeURIComponent(rNo)} នេះមែនទេ?`)) {
                apiFetch(`/api/delete?no=${rNo}`)
                    .then(r => r.json())
                    .then(res => { if (res.success) loadDatabaseRecords(); });
            }
        }

        function clearAllRecords() {
            if (confirm('⚠️ តើអ្នកពិតជាចង់លុបទិន្នន័យទាំងអស់មែនទេ? (Clear All Records)')) {
                apiFetch('/api/clear_all')
                    .then(r => r.json())
                    .then(res => { if (res.success) loadDatabaseRecords(); });
            }
        }

        function resetSearch() {
            document.getElementById('searchInput').value = '';
            renderDatabaseTable();
        }

        function loadRecordIntoForm(rNo) {
            const item = allDatabaseRecords.find(i => (i.group_data?.receipt_no || i.customer?.receipt_no || '') === decodeURIComponent(rNo));
            if (!item) return;

            document.getElementById('senderName').value = item.group_info?.group_name || item.customer?.full_english_name || '';
            document.getElementById('travelDate').value = item.group_info?.travel_date || item.group_data?.date_str || '';
            document.getElementById('agencyCompany').value = item.group_info?.agency_company || '';

            const members = item.members || [];
            if (members.length > 0) {
                document.getElementById('paxInput').value = members.length;
                const tbody = document.getElementById('groupMembersBody');
                tbody.innerHTML = '';
                members.forEach((m, idx) => {
                    addMemberRow(idx + 1, m.full_english_name || m.english_name || '');
                });
            }
            alert(`បាន Load ទិន្នន័យវិក្កយបត្រ ${decodeURIComponent(rNo)} ចូលក្នុង Form រក្សាទុក!`);
        }

        /* Passport Multi-File & Drag-and-Drop Batch AI OCR Scanner */
        function setupDropZone() {
            const dz = document.getElementById('dropZone');
            if (!dz) return;
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }));

            dz.addEventListener('drop', e => {
                let files = e.dataTransfer.files;
                if (files.length > 0) handleImageFiles(files);
            });
        }

        function handleImageFiles(filesList) {
            if (!filesList || filesList.length === 0) return;

            const files = Array.from(filesList);
            document.getElementById('ocrSpinner').style.display = 'block';
            document.getElementById('ocrSpinner').textContent = `⏳ AI Document AI កំពុងស្កេនរូបភាព (Processing ${files.length} Passports Batch OCR...)...`;

            let reader = new FileReader();
            reader.onload = e => {
                document.getElementById('previewImage').src = e.target.result;
                document.getElementById('imagePreviewBox').style.display = 'block';
                document.getElementById('batchScanCountLabel').textContent = `✅ ស្កេនបានចំនួន ${files.length} រូបភាព Passport`;
            };
            reader.readAsDataURL(files[0]);

            let formData = new FormData();
            files.forEach(file => formData.append('images[]', file));

            apiFetch('/api/ocr_scan', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(res => {
                document.getElementById('ocrSpinner').style.display = 'none';
                if (res.success && res.results && res.results.length > 0) {
                    processExtractedPassportResults(res.results);
                }
            })
            .catch(err => {
                document.getElementById('ocrSpinner').style.display = 'none';
                console.log("OCR Error:", err);
            });
        }

        function processExtractedPassportResults(results) {
            const tbody = document.getElementById('groupMembersBody');
            
            if (results.length === 1 && results[0].full_english_name) {
                document.getElementById('custNamePassport').value = results[0].full_english_name;
            }

            results.forEach(res => {
                const name = res.full_english_name || 'PASSPORT CUSTOMER';
                const passNo = res.passport_no || '';

                let emptyRow = null;
                tbody.querySelectorAll('tr').forEach(r => {
                    if (!r.querySelector('.input-m-name').value.trim() && !emptyRow) {
                        emptyRow = r;
                    }
                });

                if (emptyRow) {
                    emptyRow.querySelector('.input-m-name').value = name;
                } else {
                    addMemberRow(tbody.children.length + 1, name, passNo);
                }
            });

            document.getElementById('paxCountLabel').textContent = tbody.children.length;
            document.getElementById('paxInput').value = tbody.children.length;
            calcTotals();
        }

        /* Printable Receipt Modal Controls */
        function openReceiptModal(rNo) {
            const item = allDatabaseRecords.find(i => (i.group_data?.receipt_no || i.customer?.receipt_no || '') === decodeURIComponent(rNo));
            if (!item) return;
            currentModalReceiptData = item;

            const isGroup = item.group_info || item.group_data;
            const recNo = item.group_data?.receipt_no || item.customer?.receipt_no || 'INV';
            const status = (item.payment_status || 'UNPAID').toUpperCase();

            document.getElementById('mReceiptNo').textContent = recNo;
            document.getElementById('mSenderName').textContent = item.group_info?.group_name || item.customer?.full_english_name || '-';
            document.getElementById('mAgencyName').textContent = item.group_info?.agency_company || item.customer?.agency_company || '-';
            document.getElementById('mTravelDate').textContent = item.group_info?.travel_date || item.group_data?.date_str || '-';
            document.getElementById('mDateSaved').textContent = item.date_saved || '-';

            const rate = parseFloat(item.group_data?.exchange_rate || item.fees?.exchange_rate || <?= DEFAULT_EXCHANGE_RATE ?>);
            document.getElementById('mRate').textContent = `1 USD = ${rate.toFixed(2)} THB`;

            const grandUSD = parseFloat(item.group_data?.totals?.usd || item.totals?.usd || 0);
            const grandTHB = parseFloat(item.group_data?.totals?.baht || item.totals?.baht || (grandUSD * rate));

            document.getElementById('mGrandUSD').textContent = '$' + grandUSD.toFixed(2);
            document.getElementById('mGrandTHB').textContent = '฿' + grandTHB.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});

            const tbody = document.getElementById('mReceiptItemsBody');
            let html = '';
            const members = item.members || [];

            const fmtUsd = v => (v > 0 ? ('$' + (v % 1 === 0 ? v.toFixed(0) : v.toFixed(2))) : '-');
            const fmtTotUsd = v => ('$' + (v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)));

            if (isGroup && members.length > 0) {
                members.forEach((m, idx) => {
                    const name = m.full_english_name || m.english_name || 'Guest';
                    const vip = parseFloat(m.vip || 0);
                    const clear = parseFloat(m.clearance_fee || 0);
                    const permit = parseFloat(m.work_permit || 0);
                    const carVisa = parseFloat(m.car_fee || 0) + parseFloat(m.visa_fee || 0);
                    const tot = parseFloat(m.usd || (vip + clear + permit + carVisa));

                    html += `
                        <tr style="border-bottom:1px solid #cbd5e1;">
                            <td style="padding:6px; text-align:center; border:1px solid #cbd5e1;">${idx + 1}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; font-weight:600;">${name}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(vip)}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(clear)}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(permit)}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(carVisa)}</td>
                            <td style="padding:6px; border:1px solid #cbd5e1; text-align:right; font-weight:bold; color:#0284c7;">${fmtTotUsd(tot)}</td>
                        </tr>
                    `;
                });
                document.getElementById('mPaxCount').textContent = members.length + ' Pax';
            } else {
                const name = item.customer?.full_english_name || 'Guest';
                const fees = item.fees || {};
                const vip = parseFloat(fees.vip_fee || 0);
                const clear = parseFloat(fees.clearance_fee || 0);
                const permit = parseFloat(fees.work_permit || 0);
                const carVisa = parseFloat(fees.car_fee || 0) + parseFloat(fees.visa_fee || 0);

                html = `
                    <tr style="border-bottom:1px solid #cbd5e1;">
                        <td style="padding:6px; text-align:center; border:1px solid #cbd5e1;">1</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; font-weight:600;">${name}</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(vip)}</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(clear)}</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(permit)}</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; text-align:right;">${fmtUsd(carVisa)}</td>
                        <td style="padding:6px; border:1px solid #cbd5e1; text-align:right; font-weight:bold; color:#0284c7;">${fmtTotUsd(grandUSD)}</td>
                    </tr>
                `;
                document.getElementById('mPaxCount').textContent = '1 Pax';
            }

            tbody.innerHTML = html;

            const stamp = document.getElementById('mStampContainer');
            if (stamp) {
                if (status === 'PAID') {
                    stamp.innerHTML = `<div class="stamp-paid">✅ PAID</div>`;
                } else {
                    stamp.innerHTML = `<div class="stamp-unpaid">❌ UNPAID</div>`;
                }
            }

            document.getElementById('receiptModal').classList.add('active');
        }

        function closeReceiptModal() {
            document.getElementById('receiptModal').classList.remove('active');
        }

        function downloadReceiptPNG() {
            let tDate = document.getElementById('mTravelDate')?.textContent?.trim() || '';
            tDate = tDate.replace(/\//g, '-').replace(/[^a-zA-Z0-9\-]/g, '');
            if (!tDate || tDate === '-') {
                const today = new Date();
                const dd = String(today.getDate()).padStart(2, '0');
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const yyyy = today.getFullYear();
                tDate = `${dd}-${mm}-${yyyy}`;
            }

            html2canvas(document.getElementById('printableReceiptArea'), { scale: 2 }).then(canvas => {
                const link = document.createElement('a');
                link.download = `${tDate}.png`;
                link.href = canvas.toDataURL('image/png');
                link.click();
            });
        }

        function shareReceiptTelegram() {
            const rNo = document.getElementById('mReceiptNo')?.textContent || 'INV';
            const sender = document.getElementById('mSenderName')?.textContent || '';
            const total = document.getElementById('mGrandUSD')?.textContent || '';
            const receiptEl = document.getElementById('printableReceiptArea');

            if (receiptEl && typeof html2canvas !== 'undefined') {
                html2canvas(receiptEl, { scale: 2, useCORS: true, backgroundColor: '#ffffff' }).then(canvas => {
                    canvas.toBlob(blob => {
                        if (!blob) {
                            downloadAndOpenTgFallback(canvas, rNo, sender, total);
                            return;
                        }

                        const file = new File([blob], `Receipt_${rNo}.png`, { type: 'image/png' });
                        if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
                            navigator.share({
                                files: [file],
                                title: `Receipt ${rNo}`,
                                text: `🧾 VIP Border Receipt: ${rNo}\n👤 Customer/Group: ${sender}\n💰 Total: ${total}`
                            }).catch(err => {
                                console.log('Mobile share canceled/failed:', err);
                            });
                            return;
                        }

                        if (navigator.clipboard && window.ClipboardItem) {
                            const item = new ClipboardItem({ 'image/png': blob });
                            navigator.clipboard.write([item]).then(() => {
                                alert(`🚀 បាន Copy រូបភាពវិក័យប័ត្រ (${rNo}) ចូល Clipboard រួចរាល់!\n\nសូមចុច Ctrl + V ក្នុង Telegram Chat ដើម្បី Paste ផ្ញើរូបភាព!`);
                                const text = `🧾 VIP Border Receipt: ${rNo}\n👤 Customer/Group: ${sender}\n💰 Total: ${total}`;
                                window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${encodeURIComponent(text)}`, '_blank');
                            }).catch(() => {
                                downloadAndOpenTgFallback(canvas, rNo, sender, total);
                            });
                        } else {
                            downloadAndOpenTgFallback(canvas, rNo, sender, total);
                        }
                    }, 'image/png');
                });
            } else {
                const text = encodeURIComponent(`🧾 VIP Border Receipt: ${rNo}\n👤 Customer/Group: ${sender}\n💰 Total USD: ${total}\n🏢 Golden Mekong Commercial Service`);
                window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${text}`, '_blank');
            }
        }

        function downloadAndOpenTgFallback(canvas, rNo, sender, total) {
            let tDate = document.getElementById('mTravelDate')?.textContent?.trim() || '';
            tDate = tDate.replace(/\//g, '-').replace(/[^a-zA-Z0-9\-]/g, '');
            if (!tDate || tDate === '-') {
                const today = new Date();
                const dd = String(today.getDate()).padStart(2, '0');
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const yyyy = today.getFullYear();
                tDate = `${dd}-${mm}-${yyyy}`;
            }
            const link = document.createElement('a');
            link.download = `${tDate}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
            alert(`📥 បានទាញយករូបភាពវិក័យប័ត្រ (${tDate})!\n\nលោកអ្នកអាច Drag/Upload រូបភាព PNG នេះចូល Telegram Chat បាន!`);
            const shareText = encodeURIComponent(`🧾 VIP Border Receipt: ${rNo}\n👤 Customer/Group: ${sender}\n💰 Total USD: ${total}`);
            window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${shareText}`, '_blank');
        }
    </script>
</body>
</html>
