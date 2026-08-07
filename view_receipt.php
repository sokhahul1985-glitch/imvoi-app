<?php
/**
 * CMP Golden Mekong Commercial Service - Official Receipt Viewer & Print Template
 * 100% Matching Python receipt_generator.py layout
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

$receiptNo = $_GET['no'] ?? '';
$invoice = get_invoice_by_no($receiptNo);

if (!$invoice) {
    echo "<div style='color:red; font-size: 1.2rem; text-align:center; padding: 40px;'>❌ មិនរកឃើញវិក្កយបត្រ " . htmlspecialchars($receiptNo) . " ទេ! <br><br><a href='index.php'>ត្រឡប់ទៅផ្ទាំងគ្រប់គ្រង</a></div>";
    exit;
}

$isGroup = isset($invoice['group_info']) || isset($invoice['group_data']);
$status = strtoupper($invoice['payment_status'] ?? 'UNPAID');

$rNo = $invoice['group_data']['receipt_no'] ?? ($invoice['customer']['receipt_no'] ?? ($receiptNo ?: 'INV 0000'));
$dateStr = $invoice['group_data']['date_str'] ?? ($invoice['group_info']['travel_date'] ?? ($invoice['customer']['travel_date'] ?? ($invoice['date_saved'] ?? date('d-m-Y'))));
$exchangeRate = floatval($invoice['group_data']['exchange_rate'] ?? ($invoice['fees']['exchange_rate'] ?? 33.90));

// Determine clean Customer / Sender display name
$customerName = '';
if ($isGroup) {
    $sender = $invoice['group_data']['sender_name'] ?? ($invoice['group_info']['sender_name'] ?? '');
    $cust = $invoice['group_data']['group_customer_name'] ?? ($invoice['group_info']['customer_name'] ?? '');
    $groupNm = $invoice['group_info']['group_name'] ?? '';

    if (strpos($sender, '|') !== false) {
        $parts = explode('|', $sender);
        $sender = trim(end($parts));
    }
    if (strpos($cust, '|') !== false) {
        $parts = explode('|', $cust);
        $cust = trim(end($parts));
    }

    if (!empty($sender) && !in_array(strtoupper($sender), ['VIP GROUP', 'GROUP', ''])) {
        $customerName = $sender;
    } elseif (!empty($cust) && !in_array(strtoupper($cust), ['VIP GROUP', 'GROUP', ''])) {
        $customerName = $cust;
    } elseif (!empty($invoice['members'][0]['full_english_name'])) {
        $firstM = $invoice['members'][0]['full_english_name'];
        if (strpos($firstM, '|') !== false) {
            $parts = explode('|', $firstM);
            $firstM = trim(end($parts));
        }
        $customerName = $firstM;
    } else {
        $customerName = $groupNm ?: 'HR(CS)- แอน';
    }
} else {
    $customerName = $invoice['customer']['full_english_name'] ?? 'HR(CS)- แอน';
}

// Build Items list matching receipt_generator.py format
$rowsData = [];

if (!$isGroup) {
    $fees = $invoice['fees'] ?? [];
    $eVisa = floatval($fees['e_visa'] ?? 0);
    $vip = floatval($fees['vip_fee'] ?? 0);
    $overstay = floatval($fees['overstay_fee'] ?? 0);
    $carFee = floatval($fees['car_fee'] ?? 0) + floatval($fees['visa_fee'] ?? 0);
    $clearanceFee = floatval($fees['clearance_fee'] ?? 0) + floatval($fees['work_permit'] ?? 0);
    $usdTotal = floatval($invoice['totals']['usd'] ?? ($eVisa + $vip + $overstay + $carFee + $clearanceFee));

    $rowsData[] = [
        'no' => 1,
        'description' => $customerName,
        'qty' => '1',
        'e_visa' => $eVisa > 0 ? ('$' . number_format($eVisa, 0)) : '',
        'vip' => $vip > 0 ? ('$' . number_format($vip, 0)) : '',
        'overstay' => $overstay > 0 ? ('$' . number_format($overstay, 0)) : '',
        'car_fee' => $carFee > 0 ? ('$' . number_format($carFee, 0)) : '',
        'clearance_fee' => $clearanceFee > 0 ? ('$' . number_format($clearanceFee, 0)) : '',
        'usd' => $usdTotal
    ];
} else {
    $members = $invoice['members'] ?? [];
    $items = $invoice['group_data']['items'] ?? [];

    if (!empty($members)) {
        foreach ($members as $idx => $m) {
            $mName = $m['full_english_name'] ?? ($m['english_name'] ?? ('PASSENGER ' . ($idx + 1)));
            if (strpos($mName, '|') !== false) {
                $parts = explode('|', $mName);
                $mName = trim(end($parts));
            }

            $mVip = floatval($m['vip'] ?? 0);
            $mClear = floatval($m['clearance_fee'] ?? 0) + floatval($m['work_permit'] ?? 0);
            $mCar = floatval($m['car_fee'] ?? 0) + floatval($m['visa_fee'] ?? 0) + floatval($m['price'] ?? 0);
            $mEvisa = floatval($m['e_visa'] ?? 0);
            $mOverstay = floatval($m['overstay'] ?? 0);
            $mUsd = floatval($m['usd'] ?? ($mVip + $mClear + $mCar + $mEvisa + $mOverstay));

            $rowsData[] = [
                'no' => $idx + 1,
                'description' => $mName,
                'qty' => '1',
                'e_visa' => $mEvisa > 0 ? ('$' . number_format($mEvisa, 0)) : '',
                'vip' => $mVip > 0 ? ('$' . number_format($mVip, 0)) : '',
                'overstay' => $mOverstay > 0 ? ('$' . number_format($mOverstay, 0)) : '',
                'car_fee' => $mCar > 0 ? ('$' . number_format($mCar, 0)) : '',
                'clearance_fee' => $mClear > 0 ? ('$' . number_format($mClear, 0)) : '',
                'usd' => $mUsd
            ];
        }
    } elseif (!empty($items)) {
        foreach ($items as $idx => $it) {
            $rowsData[] = [
                'no' => $idx + 1,
                'description' => $it['description'] ?? ('Item ' . ($idx + 1)),
                'qty' => $it['qty'] ?? '1',
                'e_visa' => $it['e_visa'] ?? '',
                'vip' => $it['vip'] ?? '',
                'overstay' => $it['overstay'] ?? '',
                'car_fee' => $it['car_fee'] ?? ($it['visa'] ?? ''),
                'clearance_fee' => $it['clearance_fee'] ?? ($it['work_permit'] ?? ''),
                'usd' => floatval($it['usd'] ?? 0)
            ];
        }
    }
}

// Calculate Grand Totals
$grandUsd = 0;
foreach ($rowsData as $r) {
    $grandUsd += $r['usd'];
}
if ($grandUsd == 0) {
    $grandUsd = floatval($invoice['group_data']['totals']['usd'] ?? ($invoice['totals']['usd'] ?? 0));
}
$grandThb = floatval($invoice['group_data']['totals']['baht'] ?? ($invoice['totals']['baht'] ?? ($grandUsd * $exchangeRate)));

// 30 portrait table grid rows count matching official CMP format
$gridRowsCount = max(count($rowsData), 30);
?>
<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receipt - <?= htmlspecialchars($rNo) ?> - <?= COMPANY_NAME_EN ?></title>
    <link rel="stylesheet" href="assets/css/styles.css">
    <!-- html2canvas and jspdf CDN for image & PDF downloads -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
    .tg-modal-backdrop {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(8px);
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
    }
    .tg-modal-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 16px;
        width: 100%;
        max-width: 540px;
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
        overflow: hidden;
        color: #f8fafc;
        font-family: system-ui, -apple-system, sans-serif;
    }
    .tg-modal-header {
        background: #0f172a;
        padding: 16px 20px;
        border-bottom: 1px solid #334155;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .tg-modal-close {
        background: transparent;
        border: none;
        color: #94a3b8;
        font-size: 1.6rem;
        cursor: pointer;
        line-height: 1;
        padding: 0 4px;
    }
    .tg-modal-close:hover { color: #f43f5e; }
    .tg-modal-body {
        padding: 20px;
    }
    .tg-status-box {
        background: #0f172a;
        border: 1px solid #334155;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 0.85rem;
        color: #38bdf8;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .tg-options-grid {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 16px;
    }
    .tg-opt-btn {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 16px;
        border-radius: 12px;
        border: 1px solid transparent;
        cursor: pointer;
        text-align: left;
        transition: all 0.2s ease;
        width: 100%;
    }
    .tg-opt-icon {
        font-size: 1.5rem;
        flex-shrink: 0;
    }
    .tg-opt-content {
        flex-grow: 1;
    }
    .tg-opt-title {
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 2px;
    }
    .tg-opt-desc {
        font-size: 0.78rem;
        opacity: 0.85;
    }
    .tg-btn-primary { background: #0284c7; color: white; border-color: #38bdf8; }
    .tg-btn-primary:hover { background: #0369a1; }
    .tg-btn-indigo { background: #4f46e5; color: white; border-color: #818cf8; }
    .tg-btn-indigo:hover { background: #4338ca; }
    .tg-btn-emerald { background: #059669; color: white; border-color: #34d399; }
    .tg-btn-emerald:hover { background: #047857; }
    .tg-btn-slate { background: #334155; color: #e2e8f0; border-color: #475569; }
    .tg-btn-slate:hover { background: #475569; }
    .tg-config-section {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 12px 14px;
    }
    .tg-config-toggle-btn {
        background: transparent;
        border: none;
        color: #94a3b8;
        font-size: 0.88rem;
        font-weight: 600;
        cursor: pointer;
        width: 100%;
        text-align: left;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .tg-config-toggle-btn:hover { color: #f8fafc; }
    .tg-input-field {
        width: 100%;
        background: #1e293b;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 8px 10px;
        color: #f8fafc;
        font-size: 0.85rem;
        box-sizing: border-box;
    }
    .tg-input-field:focus { outline: none; border-color: #38bdf8; }
    .tg-toast {
        margin-top: 14px;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .tg-toast-success { background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; }
    .tg-toast-error { background: rgba(244, 63, 94, 0.2); border: 1px solid #f43f5e; color: #fb7185; }
    .tg-toast-info { background: rgba(56, 189, 248, 0.2); border: 1px solid #38bdf8; color: #38bdf8; }
    </style>
</head>
<body style="background: #0f172a; padding: 20px 0;">

    <!-- Action Toolbar (Hidden during printing) -->
    <div class="toolbar-print">
        <a href="index.php" class="btn btn-secondary">⬅️ ត្រឡប់ទៅផ្ទាំងគ្រប់គ្រង</a>
        
        <div style="display: flex; gap: 10px;">
            <button onclick="togglePaymentStatus('<?= urlencode($rNo) ?>', '<?= $status === 'PAID' ? 'UNPAID' : 'PAID' ?>')" class="btn <?= $status === 'PAID' ? 'btn-danger' : 'btn-success' ?>">
                <?= $status === 'PAID' ? '❌ ផ្លាស់ប្តូរទៅ UNPAID' : '✅ ផ្លាស់ប្តូរទៅ PAID' ?>
            </button>
            <button onclick="printReceipt()" class="btn btn-primary">🖨️ បោះពុម្ព (Print)</button>
            <button onclick="downloadReceiptImage()" class="btn btn-emerald">🖼️ ទាញយក PNG Image</button>
            <button onclick="openTelegramModal()" class="btn btn-primary" style="background: #0088cc;">✈️ Share Telegram</button>
        </div>
    </div>

    <!-- Official Golden Mekong Printable CMP Invoice Document -->
    <div class="cmp-receipt-paper" id="receiptContent">
        
        <!-- Status Stamp Badge -->
        <div class="stamp-badge-absolute">
            <?php if ($status === 'PAID'): ?>
                <div class="stamp-paid">✅ PAID</div>
            <?php else: ?>
                <div class="stamp-unpaid">❌ UNPAID</div>
            <?php endif; ?>
        </div>

        <!-- 1. Header with CMP Logo -->
        <div class="cmp-header-grid">
            <div class="cmp-logo-box">
                <img src="assets/images/cmp_logo.png" alt="CMP Logo" onerror="this.style.display='none'">
            </div>
            <div class="cmp-header-center">
                <div class="cmp-company-th">บริษัท โกลเด้น เมกง พาณิชย์ เซอร์วิส จำกัด</div>
                <div class="cmp-addr-line">Chamkar Dong, Dangkao, Phnom Penh, Cambodia</div>
                <div class="cmp-addr-line">Tel: 0888022656 / 081662083</div>
                <div class="cmp-title-invoice">INVOICE</div>

            </div>
            <div style="width: 85px;"></div>
        </div>

        <!-- 2. Subheader Customer & SCB Bank Info -->
        <div class="cmp-sub-grid">
            <div class="cmp-sub-left">
                <div><strong>Customer Name :</strong> <span style="font-weight: 700;"><?= htmlspecialchars($customerName) ?></span></div>
                <div><strong>Date:</strong> <?= htmlspecialchars($dateStr) ?></div>
                <div><strong>Invoice No :</strong> <u><?= htmlspecialchars($rNo) ?></u></div>
            </div>
            <div class="cmp-sub-right">
                <div style="font-weight: 700;">ไทยพาณิชย์</div>
                <div>หมายเลขบัญชี 6924007211</div>
                <div>ชื่อ Mr.KHLORNG ORN</div>
            </div>
        </div>

        <!-- 3. 10 Columns Official CMP Table Grid -->
        <table class="cmp-table">
            <thead>
                <tr>
                    <th style="width: 28px;">No.</th>
                    <th style="width: 220px;">DESCRIPTION</th>
                    <th style="width: 50px;">Quantly<br>/Pax</th>
                    <th style="width: 45px;">E<br>VISA</th>
                    <th style="width: 40px;">VIP</th>
                    <th style="width: 45px;">Over<br>Stay</th>
                    <th style="width: 50px;">Car<br>Fee</th>
                    <th style="width: 60px;">Clearance<br>Fee</th>
                    <th style="width: 60px;">อัตรา<br>แลกเงิน</th>
                    <th style="width: 100px;">Price In<br>Baht</th>
                </tr>
            </thead>
            <tbody>
                <?php for ($rIdx = 1; $rIdx <= $gridRowsCount; $rIdx++): ?>
                    <?php if ($rIdx <= count($rowsData)): 
                        $row = $rowsData[$rIdx - 1];
                        $rowBaht = $row['usd'] > 0 ? number_format($row['usd'] * $exchangeRate, 0) : '';
                    ?>
                    <tr>
                        <td style="text-align: center;"><?= $rIdx ?></td>
                        <td style="font-weight: 600; text-align: left; padding-left: 4px;"><?= htmlspecialchars($row['description']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['qty']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['e_visa']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['vip']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['overstay']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['car_fee']) ?></td>
                        <td style="text-align: center;"><?= htmlspecialchars($row['clearance_fee']) ?></td>
                        <td style="text-align: center;"></td>
                        <td style="text-align: right; font-weight: 600; padding-right: 6px;"><?= $rowBaht ?></td>
                    </tr>
                    <?php else: ?>
                    <tr>
                        <td style="text-align: center; color: #94a3b8;"><?= $rIdx ?></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td></td>
                    </tr>
                    <?php endif; ?>
                <?php endfor; ?>

                <!-- Summary Row -->
                <tr class="summary-row">
                    <td></td>
                    <td style="text-align: right; font-weight: 700; padding-right: 8px;">Total</td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td style="text-align: center; font-weight: 700;">$<?= number_format($grandUsd, 0) ?></td>
                    <td></td>
                    <td class="cmp-bg-blue" style="text-align: center; font-weight: 700;"><?= number_format($exchangeRate, 1) ?></td>
                    <td class="cmp-bg-grey" style="text-align: right; font-weight: 700; padding-right: 6px;">฿ <?= number_format($grandThb, 0) ?></td>
                </tr>
            </tbody>
        </table>

        <!-- 4. Footer & Signature Info -->
        <div class="cmp-footer-grid">
            <div class="cmp-footer-left">
                <div><strong>Prepared by</strong></div>
                <div style="margin-top: 10px; margin-bottom: 2px;"><i><u>hol sokha</u></i></div>
                <div style="font-weight: 700; font-size: 0.9rem;">ហុល សុខា</div>
            </div>
            <div class="cmp-footer-right">
                <div><strong>Account No. : 005 870 215</strong></div>
                <div><strong>Account Name: Hol Sokha</strong></div>
                <div><strong>Bank Name : ABA Bank</strong></div>

                <div style="margin-top: 4px;"><strong>CONTACT ME</strong></div>
                <div><strong>081662083</strong></div>
            </div>
        </div>

    </div>

    <!-- Telegram Share Modal Dialog -->
    <div id="telegramShareModal" class="tg-modal-backdrop" style="display: none;">
        <div class="tg-modal-card">
            <div class="tg-modal-header">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="font-size: 1.5rem;">✈️</div>
                    <div>
                        <h3 style="margin: 0; font-size: 1.15rem; color: #38bdf8;">ចែករំលែកវិក្កយបត្រទៅ Telegram</h3>
                        <div style="font-size: 0.8rem; color: #94a3b8;">រៀបចំ និងផ្ញើរូបភាពវិក្កយបត្រផ្លូវការ (Official Invoice Image)</div>
                    </div>
                </div>
                <button onclick="closeTelegramModal()" class="tg-modal-close">&times;</button>
            </div>

            <div class="tg-modal-body">
                <!-- Status Badge -->
                <div id="tgStatusBadge" class="tg-status-box">
                    <span>🔄 កំពុងពិនិត្យស្ថានភាព Telegram Bot...</span>
                </div>

                <div class="tg-options-grid">
                    <!-- Option 1: Direct 1-Click Bot Delivery -->
                    <button onclick="sendViaTelegramBot()" class="tg-opt-btn tg-btn-primary">
                        <div class="tg-opt-icon">⚡</div>
                        <div class="tg-opt-content">
                            <div class="tg-opt-title">១. ផ្ញើអូតូជា PNG Image ទៅ Telegram Bot</div>
                            <div class="tg-opt-desc">Render រូបភាពវិក្កយបត្ររួចផ្ញើចូល Telegram Channel/Group ដោយផ្ទាល់ 1-Click</div>
                        </div>
                    </button>

                    <!-- Option 2: Copy Image to Clipboard & Open Telegram -->
                    <button onclick="copyInvoiceImageAndOpenTelegram()" class="tg-opt-btn tg-btn-indigo">
                        <div class="tg-opt-icon">🖼️</div>
                        <div class="tg-opt-content">
                            <div class="tg-opt-title">២. Copy រូបភាពវិក័យប័ត្រចូល Clipboard + បើក Telegram</div>
                            <div class="tg-opt-desc">Copy រូបភាពវិក្កយបត្រចូល Clipboard រួចបើក Telegram (ចុច Ctrl + V ដើម្បី Paste ផ្ញើ)</div>
                        </div>
                    </button>

                    <!-- Option 3: Web / Mobile Native Share File -->
                    <button onclick="shareNativeImageFile()" class="tg-opt-btn tg-btn-emerald">
                        <div class="tg-opt-icon">📲</div>
                        <div class="tg-opt-content">
                            <div class="tg-opt-title">៣. ផ្ញើជា File រូបភាព (Mobile / Web Share)</div>
                            <div class="tg-opt-desc">ចែករំលែកជា File .png ទៅកាន់ Telegram ឬ App ផ្សេងៗតាមរយះ Share Sheet</div>
                        </div>
                    </button>

                    <!-- Option 4: Plain Text Link Share fallback -->
                    <button onclick="shareTextLink()" class="tg-opt-btn tg-btn-slate">
                        <div class="tg-opt-icon">🔗</div>
                        <div class="tg-opt-content">
                            <div class="tg-opt-title">៤. ផ្ញើជា Link និងព័ត៌មានសង្ខេប (Text Link)</div>
                            <div class="tg-opt-desc">ផ្ញើជាសារអក្សរ និង Link មើលវិក្កយបត្រតាម Telegram Share Link</div>
                        </div>
                    </button>
                </div>

                <!-- Telegram Bot Settings Collapse -->
                <div class="tg-config-section">
                    <button onclick="toggleTgConfigBox()" class="tg-config-toggle-btn">
                        ⚙️ កំណត់ Telegram Bot Token & Chat ID <span id="tgConfigArrow">▼</span>
                    </button>
                    <div id="tgConfigBox" style="display: none; margin-top: 10px;">
                        <div style="font-size: 0.82rem; color: #cbd5e1; margin-bottom: 8px;">
                            បញ្ចូល Bot Token និង Chat ID / Channel Username ដើម្បីប្រើប្រាស់មុខងារ 1-Click Bot Delivery៖
                        </div>
                        <div style="margin-bottom: 8px;">
                            <label style="display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 2px;">Bot Token:</label>
                            <input type="text" id="tgBotTokenInput" placeholder="7890123456:AAxxxxxx..." class="tg-input-field">
                        </div>
                        <div style="margin-bottom: 12px;">
                            <label style="display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 2px;">Chat ID / Channel ID:</label>
                            <input type="text" id="tgChatIdInput" placeholder="-100xxxxxxxxx ឬ @your_channel" class="tg-input-field">
                        </div>
                        <button onclick="saveTgConfig()" class="btn btn-emerald" style="width: 100%; justify-content: center;">💾 រក្សាទុក (Save Bot Config)</button>
                    </div>
                </div>

                <!-- Toast / Notice Container -->
                <div id="tgAlertToast" class="tg-toast" style="display: none;"></div>
            </div>
        </div>
    </div>

    <script>
    const currentTgNo = "<?= urlencode($rNo) ?>";
    const currentTgCust = "<?= urlencode($customerName) ?>";
    const currentTgUsd = "<?= $grandUsd ?>";

    function printReceipt() {
        window.print();
    }

    function downloadReceiptImage() {
        const element = document.getElementById('receiptContent');
        let tDate = '<?= htmlspecialchars($dateStr) ?>' || '';
        tDate = tDate.replace(/\//g, '-').replace(/[^a-zA-Z0-9\-]/g, '');
        if (!tDate || tDate === '-') {
            const today = new Date();
            const dd = String(today.getDate()).padStart(2, '0');
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const yyyy = today.getFullYear();
            tDate = `${dd}-${mm}-${yyyy}`;
        }
        html2canvas(element, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff'
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = `${tDate}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    }

    function togglePaymentStatus(no, status) {
        fetch(`api.php?action=toggle_status&no=${no}&status=${status}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Failed to update payment status'));
                }
            });
    }

    function openTelegramModal() {
        document.getElementById('telegramShareModal').style.display = 'flex';
        checkTgConfigStatus();
    }

    function closeTelegramModal() {
        document.getElementById('telegramShareModal').style.display = 'none';
    }

    function showTgToast(msg, type = 'info') {
        const toast = document.getElementById('tgAlertToast');
        toast.className = `tg-toast tg-toast-${type}`;
        toast.innerHTML = msg;
        toast.style.display = 'block';
    }

    function checkTgConfigStatus() {
        fetch('api.php?action=get_telegram_config')
            .then(r => r.json())
            .then(res => {
                const badge = document.getElementById('tgStatusBadge');
                if (res.success && res.config.bot_token && res.config.chat_id) {
                    badge.innerHTML = `<span>✅ Telegram Bot Configured: Chat ID (<b>${res.config.chat_id}</b>)</span>`;
                    badge.style.color = '#34d399';
                    document.getElementById('tgBotTokenInput').value = res.config.bot_token;
                    document.getElementById('tgChatIdInput').value = res.config.chat_id;
                } else {
                    badge.innerHTML = `<span>⚠️ Telegram Bot មិនទាន់កំណត់ Token / Chat ID ទេ (សូមកំណត់ខាងក្រោម)</span>`;
                    badge.style.color = '#fb7185';
                }
            }).catch(() => {});
    }

    function toggleTgConfigBox() {
        const box = document.getElementById('tgConfigBox');
        const arrow = document.getElementById('tgConfigArrow');
        if (box.style.display === 'none') {
            box.style.display = 'block';
            arrow.textContent = '▲';
        } else {
            box.style.display = 'none';
            arrow.textContent = '▼';
        }
    }

    function saveTgConfig() {
        const token = document.getElementById('tgBotTokenInput').value.trim();
        const chatId = document.getElementById('tgChatIdInput').value.trim();

        if (!token || !chatId) {
            showTgToast('⚠️ សូមបញ្ចូល Bot Token និង Chat ID ឱ្យបានត្រឹមត្រូវ', 'error');
            return;
        }

        fetch('api.php?action=save_telegram_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot_token: token, chat_id: chatId })
        })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showTgToast('✅ បានរក្សាទុក Telegram Bot Config រួចរាល់!', 'success');
                checkTgConfigStatus();
                document.getElementById('tgConfigBox').style.display = 'none';
            } else {
                showTgToast('❌ បរាជ័យក្នុងការរក្សាទុក Config', 'error');
            }
        });
    }

    function renderReceiptCanvas() {
        const element = document.getElementById('receiptContent');
        return html2canvas(element, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff'
        });
    }

    function sendViaTelegramBot() {
        showTgToast('🔄 កំពុង Render រូបភាពវិក្កយបត្រ & ផ្ញើទៅ Telegram Bot...', 'info');

        renderReceiptCanvas().then(canvas => {
            const b64Image = canvas.toDataURL('image/png');
            const rNoDec = decodeURIComponent(currentTgNo);
            const custDec = decodeURIComponent(currentTgCust);
            const caption = `🧾 Official Invoice: ${rNoDec}\n👤 Customer: ${custDec}\n💵 Total: $${currentTgUsd}\n\nGolden Mekong Commercial Service`;


            fetch('api.php?action=send_telegram_bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image: b64Image,
                    filename: `Receipt_${rNoDec}.png`,
                    caption: caption
                })
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    showTgToast('🚀 ' + (res.message || 'បានផ្ញើរូបភាពវិក្កយបត្រទៅ Telegram Bot រួចរាល់!'), 'success');
                } else {
                    showTgToast('❌ បរាជ័យ៖ ' + (res.error || 'សូមពិនិត្យមើល Bot Token & Chat ID'), 'error');
                    document.getElementById('tgConfigBox').style.display = 'block';
                }
            })
            .catch(err => {
                showTgToast('❌ បរាជ័យក្នុងការផ្ញើទៅ Telegram Server', 'error');
            });
        });
    }

    function copyInvoiceImageAndOpenTelegram() {
        showTgToast('🔄 កំពុង Copy រូបភាពវិក្កយបត្រចូល Clipboard...', 'info');

        renderReceiptCanvas().then(canvas => {
            canvas.toBlob(blob => {
                if (navigator.clipboard && window.ClipboardItem) {
                    const item = new ClipboardItem({ 'image/png': blob });
                    navigator.clipboard.write([item]).then(() => {
                        showTgToast('✅ <b>បាន Copy រូបភាពវិក័យប័ត្រចូល Clipboard!</b><br>សូមចុច <b>Ctrl + V</b> ក្នុង Telegram Chat ដើម្បី Paste ផ្ញើរូបភាព!', 'success');
                        const rNoDec = decodeURIComponent(currentTgNo);
                        const text = `🧾 Official Invoice: ${rNoDec}\n👤 Customer: ${decodeURIComponent(currentTgCust)}\n💵 Total: $${currentTgUsd}`;
                        window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${encodeURIComponent(text)}`, '_blank');
                    }).catch(err => {
                        downloadFallbackAndOpenTelegram(canvas);
                    });
                } else {
                    downloadFallbackAndOpenTelegram(canvas);
                }
            });
        });
    }

    function getSanitizedTravelDate() {
        let tDate = '<?= htmlspecialchars($dateStr) ?>' || '';
        tDate = tDate.replace(/\//g, '-').replace(/[^a-zA-Z0-9\-]/g, '');
        if (!tDate || tDate === '-') {
            const today = new Date();
            const dd = String(today.getDate()).padStart(2, '0');
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const yyyy = today.getFullYear();
            tDate = `${dd}-${mm}-${yyyy}`;
        }
        return tDate;
    }

    function downloadFallbackAndOpenTelegram(canvas) {
        const link = document.createElement('a');
        const tDate = getSanitizedTravelDate();
        link.download = `${tDate}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        showTgToast('📥 បានទាញយករូបភាពវិក័យប័ត្រ! លោកអ្នកអាច Drag/Upload រូបភាពនេះចូល Telegram Chat បាន!', 'info');
        const rNoDec = decodeURIComponent(currentTgNo);
        const text = `🧾 Official Invoice: ${rNoDec}\n👤 Customer: ${decodeURIComponent(currentTgCust)}\n💵 Total: $${currentTgUsd}`;
        window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${encodeURIComponent(text)}`, '_blank');
    }

    function shareNativeImageFile() {
        showTgToast('🔄 កំពុងរៀបចំ File រូបភាពសម្រាប់ Share...', 'info');
        const tDate = getSanitizedTravelDate();

        renderReceiptCanvas().then(canvas => {
            canvas.toBlob(blob => {
                const file = new File([blob], `${tDate}.png`, { type: 'image/png' });
                if (navigator.canShare && navigator.canShare({ files: [file] })) {
                    navigator.share({
                        files: [file],
                        title: `Invoice ${rNoDec}`,
                        text: `Official Invoice ${rNoDec}`
                    }).then(() => {
                        showTgToast('✅ បានចែករំលែករួចរាល់!', 'success');
                    }).catch(() => {});
                } else {
                    copyInvoiceImageAndOpenTelegram();
                }
            });
        });
    }

    function shareTextLink() {
        const rNoDec = decodeURIComponent(currentTgNo);
        const custDec = decodeURIComponent(currentTgCust);
        const text = `🧾 Official Invoice: ${rNoDec}\n👤 Customer: ${custDec}\n💵 Total: $${currentTgUsd}\n\nGolden Mekong Commercial Service`;

        window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.href)}&text=${encodeURIComponent(text)}`, '_blank');
    }

    window.addEventListener('DOMContentLoaded', () => {
        if (window.location.hash === '#share') {
            openTelegramModal();
        }
    });
    </script>
</body>
</html>


