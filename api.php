<?php
/**
 * CMP Golden Mekong Commercial Service - API Handler
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Detect action from query param, POST param, or URI path (e.g., /api/next_no -> next_no)
$action = $_GET['action'] ?? $_POST['action'] ?? '';

if (empty($action)) {
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    $path = parse_url($uri, PHP_URL_PATH);
    if (strpos($path, '/api/') !== false) {
        $sub = substr($path, strpos($path, '/api/') + 5);
        $action = trim($sub, '/');
    }
}

$rawInput = file_get_contents('php://input');
$jsonInput = @json_decode($rawInput, true) ?: [];

switch ($action) {

    case 'next_no':
        $nextNo = get_next_invoice_no();
        echo json_encode(['success' => true, 'next_no' => $nextNo]);
        exit;

    case 'invoices':
        $list = load_saved_customers();
        echo json_encode(['success' => true, 'invoices' => $list]);
        exit;

    case 'get_invoice':
    case 'receipt':
        $no = $_GET['no'] ?? ($_POST['no'] ?? ($jsonInput['no'] ?? ''));
        if (empty($no)) {
            echo json_encode(['success' => false, 'error' => 'Missing receipt number']);
            exit;
        }
        $inv = get_invoice_by_no($no);
        if ($inv) {
            echo json_encode(['success' => true, 'invoice' => $inv, 'data' => $inv]);
        } else {
            echo json_encode(['success' => false, 'error' => 'Invoice not found']);
        }
        exit;

    case 'toggle_status':
        $no = $_GET['no'] ?? ($_POST['no'] ?? ($jsonInput['no'] ?? ''));
        $status = strtoupper($_GET['status'] ?? ($_POST['status'] ?? ($jsonInput['status'] ?? 'UNPAID')));
        if (empty($no)) {
            echo json_encode(['success' => false, 'error' => 'Missing receipt number']);
            exit;
        }
        $ok = update_invoice_payment_status($no, $status);
        echo json_encode(['success' => $ok]);
        exit;

    case 'delete':
        $no = $_GET['no'] ?? ($_POST['no'] ?? ($jsonInput['no'] ?? ''));
        if (empty($no)) {
            echo json_encode(['success' => false, 'error' => 'Missing receipt number']);
            exit;
        }
        $ok = delete_invoice_by_no($no);
        echo json_encode(['success' => $ok]);
        exit;

    case 'delete_member':
        $no = $_GET['no'] ?? ($_POST['no'] ?? ($jsonInput['no'] ?? ''));
        $idx = intval($_GET['index'] ?? ($_POST['index'] ?? ($jsonInput['index'] ?? -1)));
        if (empty($no) || $idx < 0) {
            echo json_encode(['success' => false, 'error' => 'Missing receipt number or member index']);
            exit;
        }
        $ok = delete_member_by_index($no, $idx);
        echo json_encode(['success' => $ok]);
        exit;

    case 'save_group':
        // Accept JSON input or Form POST
        $receiptNo = trim($_POST['receipt_no'] ?? ($jsonInput['receipt_no'] ?? ''));
        $groupName = trim($_POST['group_name'] ?? ($jsonInput['group_name'] ?? 'VIP Group'));
        $customerName = trim($_POST['customer_name'] ?? ($jsonInput['customer_name'] ?? ''));
        $agencyCompany = trim($_POST['agency_company'] ?? ($jsonInput['agency_company'] ?? ''));
        $travelDate = trim($_POST['travel_date'] ?? ($jsonInput['travel_date'] ?? date('d-m-Y')));
        $exchangeRate = floatval($_POST['exchange_rate'] ?? ($jsonInput['exchange_rate'] ?? 33.90));
        $paymentStatus = strtoupper($_POST['payment_status'] ?? ($jsonInput['payment_status'] ?? 'UNPAID'));

        $members = [];
        $items = [];
        $grandUsd = 0;

        if (!empty($jsonInput['members']) && is_array($jsonInput['members'])) {
            foreach ($jsonInput['members'] as $idx => $m) {
                $name = trim($m['name'] ?? ($m['full_english_name'] ?? ($m['english_name'] ?? '')));
                if (empty($name)) continue;

                $pass = trim($m['passport_no'] ?? '');
                $nat = trim($m['nationality'] ?? 'THAI');
                $vip = floatval($m['vip'] ?? 0);
                $clearance = floatval($m['clearance'] ?? ($m['clearance_fee'] ?? 0));
                $permit = floatval($m['work_permit'] ?? 0);
                $car = floatval($m['car_fee'] ?? 0);
                $visa = floatval($m['visa_fee'] ?? 0);
                $evisa = floatval($m['evisa'] ?? ($m['e_visa'] ?? 0));

                $rowUsd = floatval($m['usd'] ?? ($vip + $clearance + $permit + $car + $visa + $evisa));
                $grandUsd += $rowUsd;

                $members[] = [
                    'full_english_name' => $name,
                    'english_name' => $name,
                    'passport_no' => $pass,
                    'nationality' => $nat,
                    'car_fee' => $car,
                    'visa_fee' => $visa,
                    'price' => 0.0,
                    'e_visa' => $evisa,
                    'vip' => $vip,
                    'clearance_fee' => $clearance,
                    'work_permit' => $permit,
                    'usd' => $rowUsd,
                    'qty' => '1'
                ];

                $items[] = [
                    'no' => $idx + 1,
                    'description' => $name,
                    'qty' => '1',
                    'e_visa' => $evisa > 0 ? ('$' . $evisa) : '',
                    'vip' => $vip > 0 ? ('$' . $vip) : '',
                    'overstay' => '',
                    'car_fee' => $car > 0 ? ('$' . $car) : '',
                    'visa' => $visa > 0 ? ('$' . $visa) : '',
                    'clearance_fee' => $clearance > 0 ? ('$' . $clearance) : '',
                    'work_permit' => $permit > 0 ? ('$' . $permit) : '',
                    'usd' => $rowUsd
                ];
            }
        } else {
            $mNames = $_POST['member_name'] ?? [];
            $mPassports = $_POST['member_passport'] ?? [];
            $mNationalities = $_POST['member_nationality'] ?? [];
            $mVips = $_POST['member_vip'] ?? [];
            $mClearances = $_POST['member_clearance'] ?? [];
            $mPermits = $_POST['member_work_permit'] ?? [];
            $mCars = $_POST['member_car_fee'] ?? [];
            $mVisas = $_POST['member_visa_fee'] ?? [];
            $mEvisas = $_POST['member_evisa'] ?? [];

            foreach ($mNames as $idx => $name) {
                if (empty(trim($name))) continue;
                
                $pass = trim($mPassports[$idx] ?? '');
                $nat = trim($mNationalities[$idx] ?? 'THAI');
                $vip = floatval($mVips[$idx] ?? 0);
                $clearance = floatval($mClearances[$idx] ?? 0);
                $permit = floatval($mPermits[$idx] ?? 0);
                $car = floatval($mCars[$idx] ?? 0);
                $visa = floatval($mVisas[$idx] ?? 0);
                $evisa = floatval($mEvisas[$idx] ?? 0);

                $rowUsd = $vip + $clearance + $permit + $car + $visa + $evisa;
                $grandUsd += $rowUsd;

                $members[] = [
                    'full_english_name' => $name,
                    'english_name' => $name,
                    'passport_no' => $pass,
                    'nationality' => $nat,
                    'car_fee' => $car,
                    'visa_fee' => $visa,
                    'price' => 0.0,
                    'e_visa' => $evisa,
                    'vip' => $vip,
                    'clearance_fee' => $clearance,
                    'work_permit' => $permit,
                    'usd' => $rowUsd,
                    'qty' => '1'
                ];

                $items[] = [
                    'no' => $idx + 1,
                    'description' => $name,
                    'qty' => '1',
                    'e_visa' => $evisa > 0 ? ('$' . $evisa) : '',
                    'vip' => $vip > 0 ? ('$' . $vip) : '',
                    'overstay' => '',
                    'car_fee' => $car > 0 ? ('$' . $car) : '',
                    'visa' => $visa > 0 ? ('$' . $visa) : '',
                    'clearance_fee' => $clearance > 0 ? ('$' . $clearance) : '',
                    'work_permit' => $permit > 0 ? ('$' . $permit) : '',
                    'usd' => $rowUsd
                ];
            }
        }

        $paxCount = count($members);
        $grandThb = $grandUsd * $exchangeRate;

        // Increment Invoice Number if not assigned
        if (empty($receiptNo) || $receiptNo === get_next_invoice_no()) {
            $receiptNo = increment_and_get_invoice_no();
        }

        $dateSaved = $_POST['date_saved'] ?? ($jsonInput['date_saved'] ?? date('d/m/Y H:i'));

        $newInvoice = [
            'date_saved' => urldecode($dateSaved),
            'customer' => [
                'full_english_name' => "GROUP: {$groupName} ({$paxCount} Pax)",
                'nationality' => 'GROUP',
                'sex' => "{$paxCount} Pax",
                'receipt_no' => $receiptNo
            ],
            'payment_status' => $paymentStatus,
            'group_info' => [
                'group_name' => $groupName,
                'sender_name' => $groupName,
                'customer_name' => $customerName ?: ($members[0]['full_english_name'] ?? $groupName),
                'agency_company' => $agencyCompany,
                'travel_date' => $travelDate
            ],
            'members' => $members,
            'group_data' => [
                'customer_name' => $groupName,
                'sender_name' => $groupName,
                'group_customer_name' => $customerName ?: ($members[0]['full_english_name'] ?? $groupName),
                'agency_company' => $agencyCompany,
                'date_str' => $travelDate,
                'receipt_no' => $receiptNo,
                'exchange_rate' => $exchangeRate,
                'items' => $items,
                'totals' => [
                    'usd' => $grandUsd,
                    'baht' => $grandThb
                ]
            ],
            'totals' => [
                'usd' => $grandUsd,
                'baht' => $grandThb
            ]
        ];

        $ok = add_or_update_invoice($newInvoice);

        if (!empty($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'application/json') !== false || !empty($rawInput)) {
            echo json_encode(['success' => $ok, 'receipt_no' => $receiptNo]);
            exit;
        }

        header("Location: view_receipt.php?no=" . urlencode($receiptNo));
        exit;

    case 'save_single':
        $receiptNo = trim($_POST['receipt_no'] ?? ($jsonInput['receipt_no'] ?? ''));
        $name = trim($_POST['full_english_name'] ?? ($jsonInput['full_english_name'] ?? 'Guest'));
        $passport = trim($_POST['passport_no'] ?? ($jsonInput['passport_no'] ?? ''));
        $nationality = trim($_POST['nationality'] ?? ($jsonInput['nationality'] ?? 'THAI'));
        $dob = trim($_POST['dob'] ?? ($jsonInput['dob'] ?? ''));
        $travelDate = trim($_POST['travel_date'] ?? ($jsonInput['travel_date'] ?? date('d-m-Y')));

        $vip = floatval($_POST['vip_fee'] ?? ($jsonInput['vip_fee'] ?? 0));
        $clearance = floatval($_POST['clearance_fee'] ?? ($jsonInput['clearance_fee'] ?? 0));
        $permit = floatval($_POST['work_permit'] ?? ($jsonInput['work_permit'] ?? 0));
        $car = floatval($_POST['car_fee'] ?? ($jsonInput['car_fee'] ?? 0));
        $visa = floatval($_POST['visa_fee'] ?? ($jsonInput['visa_fee'] ?? 0));
        $evisa = floatval($_POST['e_visa'] ?? ($jsonInput['e_visa'] ?? 0));
        $paymentStatus = strtoupper($_POST['payment_status'] ?? ($jsonInput['payment_status'] ?? 'UNPAID'));

        $totalUsd = $vip + $clearance + $permit + $car + $visa + $evisa;
        $totalThb = $totalUsd * DEFAULT_EXCHANGE_RATE;

        if (empty($receiptNo) || $receiptNo === get_next_invoice_no()) {
            $receiptNo = increment_and_get_invoice_no();
        }

        $newSingle = [
            'date_saved' => date('d/m/Y H:i'),
            'customer' => [
                'full_english_name' => $name,
                'passport_number' => $passport,
                'nationality' => $nationality,
                'date_of_birth' => $dob,
                'receipt_no' => $receiptNo
            ],
            'fees' => [
                'vip_fee' => $vip,
                'clearance_fee' => $clearance,
                'work_permit' => $permit,
                'car_fee' => $car,
                'visa_fee' => $visa,
                'e_visa' => $evisa,
                'exchange_rate' => DEFAULT_EXCHANGE_RATE
            ],
            'totals' => [
                'usd' => $totalUsd,
                'baht' => $totalThb
            ],
            'payment_status' => $paymentStatus
        ];

        $ok = add_or_update_invoice($newSingle);

        if (!empty($rawInput)) {
            echo json_encode(['success' => $ok, 'receipt_no' => $receiptNo]);
            exit;
        }

        header("Location: view_receipt.php?no=" . urlencode($receiptNo));
        exit;

    case 'get_telegram_config':
        $cfg = get_telegram_config();
        echo json_encode(['success' => true, 'config' => $cfg]);
        exit;

    case 'save_telegram_config':
        $token = trim($_POST['bot_token'] ?? ($jsonInput['bot_token'] ?? ''));
        $chatId = trim($_POST['chat_id'] ?? ($jsonInput['chat_id'] ?? ''));
        $ok = save_telegram_config($token, $chatId);
        echo json_encode(['success' => $ok]);
        exit;

    case 'send_telegram_bot':
        $b64 = $_POST['image'] ?? ($jsonInput['image'] ?? '');
        $caption = $_POST['caption'] ?? ($jsonInput['caption'] ?? '');
        $filename = $_POST['filename'] ?? ($jsonInput['filename'] ?? 'receipt.png');

        if (empty($b64)) {
            echo json_encode(['success' => false, 'error' => 'មិនមានទិន្នន័យរូបភាពវិក្កយបត្រទេ']);
            exit;
        }

        if (strpos($b64, ',') !== false) {
            $b64 = explode(',', $b64, 2)[1];
        }

        $imageBinary = base64_decode($b64);
        if (!$imageBinary) {
            echo json_encode(['success' => false, 'error' => 'ទិន្នន័យរូបភាពមិនត្រឹមត្រូវ']);
            exit;
        }

        $cfg = get_telegram_config();
        $res = send_telegram_photo($cfg['bot_token'], $cfg['chat_id'], $imageBinary, $filename, $caption);
        echo json_encode($res);
        exit;

    case 'ocr_scan':
        require_once __DIR__ . '/ocr_scan.php';
        exit;

    case 'clear_all':
        $ok = save_saved_customers([]);
        echo json_encode(['success' => $ok]);
        exit;

    default:
        echo json_encode(['error' => 'Invalid action']);
        exit;
}
