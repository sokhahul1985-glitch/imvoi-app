<?php
/**
 * CMP Golden Mekong Commercial Service - PHP Web App Config
 */

define('APP_NAME', 'Golden Mekong Commercial Service');
define('APP_SUBTITLE', 'VIP Border Service & Customer Invoice Management');

// Base Paths
define('BASE_DIR', __DIR__);
define('DATA_DIR', dirname(__DIR__));
define('SAVED_CUSTOMERS_FILE', DATA_DIR . '/saved_customers.json');
define('INVOICE_COUNTER_FILE', DATA_DIR . '/invoice_counter.json');
define('UPLOADS_DIR', BASE_DIR . '/uploads');

// Ensure upload directory exists
if (!file_exists(UPLOADS_DIR)) {
    @mkdir(UPLOADS_DIR, 0777, true);
}

// Company Branding Details for Official Receipts
define('COMPANY_NAME_KH', 'ក្រុមហ៊ុន ហ្គោលដិន មេគង្គ ខមមើសល សឺវីស');
define('COMPANY_NAME_EN', 'GOLDEN MEKONG COMMERCIAL SERVICE CO., LTD.');

define('COMPANY_PHONE', '0888022656 / 081662083');
define('COMPANY_ADDRESS', 'Chamkar Dong, Dangkao, Phnom Penh, Kingdom of Cambodia');


// Default Fees Config
define('DEFAULT_VIP_FEE', 280.00);
define('DEFAULT_CLEARANCE_FEE', 40.00);
define('DEFAULT_WORK_PERMIT', 40.00);
define('DEFAULT_EXCHANGE_RATE', 33.90); // USD to THB rate

// Telegram Bot Settings
define('TELEGRAM_CONFIG_FILE', DATA_DIR . '/telegram_config.json');
define('TELEGRAM_BOT_TOKEN', '');
define('TELEGRAM_CHAT_ID', '');

function get_telegram_config() {
    $file = TELEGRAM_CONFIG_FILE;
    if (file_exists($file)) {
        $json = @json_decode(file_get_contents($file), true);
        if (is_array($json)) {
            return [
                'bot_token' => trim($json['bot_token'] ?? ''),
                'chat_id' => trim($json['chat_id'] ?? '')
            ];
        }
    }
    return [
        'bot_token' => defined('TELEGRAM_BOT_TOKEN') ? TELEGRAM_BOT_TOKEN : '',
        'chat_id' => defined('TELEGRAM_CHAT_ID') ? TELEGRAM_CHAT_ID : ''
    ];
}

function save_telegram_config($botToken, $chatId) {
    $file = TELEGRAM_CONFIG_FILE;
    $data = [
        'bot_token' => trim($botToken),
        'chat_id' => trim($chatId)
    ];
    return file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)) !== false;
}

function send_telegram_photo($botToken, $chatId, $imageBinary, $filename = 'receipt.png', $caption = '') {
    if (empty($botToken) || empty($chatId)) {
        return ['success' => false, 'error' => 'សូមកំណត់ Telegram Bot Token និង Chat ID នៅក្នុង Config ជាមុនសិន!'];
    }

    $url = "https://api.telegram.org/bot{$botToken}/sendPhoto";

    if (function_exists('curl_init')) {
        $tempFile = tempnam(sys_get_temp_dir(), 'tg_img_');
        file_put_contents($tempFile, $imageBinary);

        $postFields = [
            'chat_id' => $chatId,
            'caption' => $caption,
            'photo' => new CURLFile($tempFile, 'image/png', $filename)
        ];

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postFields);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);

        $response = curl_exec($ch);
        $err = curl_error($ch);
        curl_close($ch);
        @unlink($tempFile);

        if ($err) {
            return ['success' => false, 'error' => 'cURL Error: ' . $err];
        }

        $resData = json_decode($response, true);
        if ($resData && !empty($resData['ok'])) {
            return ['success' => true, 'message' => 'បានផ្ញើរូបភាពវិក្កយបត្រទៅ Telegram រួចរាល់!'];
        } else {
            $msg = $resData['description'] ?? 'Telegram Bot API error';
            return ['success' => false, 'error' => $msg];
        }
    } else {
        $boundary = '----WebKitFormBoundary' . md5(uniqid());
        $body = "";

        $body .= "--$boundary\r\n";
        $body .= "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n$chatId\r\n";

        if ($caption) {
            $body .= "--$boundary\r\n";
            $body .= "Content-Disposition: form-data; name=\"caption\"\r\n\r\n$caption\r\n";
        }

        $body .= "--$boundary\r\n";
        $body .= "Content-Disposition: form-data; name=\"photo\"; filename=\"$filename\"\r\n";
        $body .= "Content-Type: image/png\r\n\r\n";
        $body .= $imageBinary . "\r\n";
        $body .= "--$boundary--\r\n";

        $opts = [
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: multipart/form-data; boundary=$boundary\r\n",
                'content' => $body,
                'timeout' => 30
            ],
            'ssl' => [
                'verify_peer' => false,
                'verify_peer_name' => false
            ]
        ];

        $context = stream_context_create($opts);
        $result = @file_get_contents($url, false, $context);
        if ($result === false) {
            return ['success' => false, 'error' => 'មិនអាចតភ្ជាប់ទៅ Telegram Server បានទេ'];
        }

        $resData = json_decode($result, true);
        if ($resData && !empty($resData['ok'])) {
            return ['success' => true, 'message' => 'បានផ្ញើរូបភាពវិក្កយបត្រទៅ Telegram រួចរាល់!'];
        } else {
            $msg = $resData['description'] ?? 'Telegram API Error';
            return ['success' => false, 'error' => $msg];
        }
    }
}

