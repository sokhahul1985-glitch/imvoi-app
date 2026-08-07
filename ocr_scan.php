<?php
/**
 * CMP Golden Mekong Commercial Service - AI OCR Processing Handler
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'error' => 'Invalid request method']);
    exit;
}

$uploadedFiles = [];

// Handle single file 'passport_file' or 'image'
if (isset($_FILES['passport_file']) && $_FILES['passport_file']['error'] === UPLOAD_ERR_OK) {
    $uploadedFiles[] = $_FILES['passport_file'];
} elseif (isset($_FILES['image']) && $_FILES['image']['error'] === UPLOAD_ERR_OK) {
    $uploadedFiles[] = $_FILES['image'];
}

// Handle multiple files 'images' or 'passport_files'
if (isset($_FILES['images']) && is_array($_FILES['images']['name'])) {
    foreach ($_FILES['images']['name'] as $idx => $name) {
        if ($_FILES['images']['error'][$idx] === UPLOAD_ERR_OK) {
            $uploadedFiles[] = [
                'name' => $name,
                'tmp_name' => $_FILES['images']['tmp_name'][$idx],
                'type' => $_FILES['images']['type'][$idx],
                'error' => $_FILES['images']['error'][$idx],
                'size' => $_FILES['images']['size'][$idx]
            ];
        }
    }
}

set_time_limit(180);

if (empty($uploadedFiles)) {
    echo json_encode(['success' => false, 'error' => 'No image uploaded']);
    exit;
}

$workspaceDir = dirname(__DIR__);
$pythonVenv = $workspaceDir . '/.venv/Scripts/python.exe';
if (!file_exists($pythonVenv)) {
    $pythonVenv = 'python';
}

$savedFiles = [];
foreach ($uploadedFiles as $idx => $file) {
    $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, ['jpg', 'jpeg', 'png', 'webp', 'pdf', 'bmp'])) {
        $ext = 'jpg';
    }
    $newName = 'passport_' . time() . '_' . rand(100, 999) . '_' . $idx . '.' . $ext;
    $targetPath = UPLOADS_DIR . '/' . $newName;

    if (move_uploaded_file($file['tmp_name'], $targetPath)) {
        $savedFiles[] = [
            'targetPath' => $targetPath,
            'newName' => $newName,
            'name' => $file['name'],
            'type' => $file['type']
        ];
    }
}

if (empty($savedFiles)) {
    echo json_encode(['success' => false, 'error' => 'Failed to save uploaded files']);
    exit;
}

$results = [];

// Method A: Single HTTP Batch Call to local Python Web Server (tries port 8000 then 8001)
if (function_exists('curl_init')) {
    foreach ([8000, 8001] as $port) {
        $ch = curl_init("http://127.0.0.1:{$port}/api/ocr_scan");
        if ($ch) {
            $postFields = [];
            foreach ($savedFiles as $i => $sf) {
                $postFields["images[{$i}]"] = new CURLFile($sf['targetPath'], $sf['type'], $sf['name']);
            }
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postFields);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_TIMEOUT, 60);
            $response = curl_exec($ch);
            curl_close($ch);

            if ($response) {
                $json = json_decode($response, true);
                if (!empty($json['results']) && is_array($json['results'])) {
                    foreach ($json['results'] as $idx => $item) {
                        if (isset($savedFiles[$idx])) {
                            $results[] = [
                                'file_path' => 'uploads/' . $savedFiles[$idx]['newName'],
                                'full_english_name' => $item['full_english_name'] ?? '',
                                'passport_no' => $item['passport_no'] ?? '',
                                'nationality' => $item['nationality'] ?? 'THAI',
                                'dob' => $item['dob'] ?? '',
                                'sex' => $item['sex'] ?? ''
                            ];
                        }
                    }
                    if (count($results) >= count($savedFiles)) {
                        break;
                    }
                }
            }
        }
    }
}

// Method B: Single-Invocation Batch CLI Fallback for all files at once
if (count($results) < count($savedFiles) && function_exists('shell_exec')) {
    $results = [];
    $paths = [];
    foreach ($savedFiles as $sf) {
        $paths[] = str_replace('\\', '/', $sf['targetPath']);
    }
    $pathsJson = json_encode($paths);

    $pyScript = sprintf(
        "import sys, json; sys.path.insert(0, '%s'); from ocr_engine import DocumentAIEngine; engine = DocumentAIEngine(); paths = json.loads('%s'); res = [];\nfor p in paths:\n    try:\n        data, _ = engine.process_image(p)\n        name = (data.get('full_english_name') or data.get('thai_name') or data.get('khmer_name') or '').strip()\n        res.append({'full_english_name': name, 'passport_no': data.get('passport_no', ''), 'nationality': data.get('nationality', 'THAI'), 'dob': data.get('dob', ''), 'sex': data.get('sex', '')})\n    except Exception as e:\n        res.append({'full_english_name': '', 'passport_no': ''})\nprint(json.dumps(res))",
        str_replace('\\', '/', $workspaceDir),
        addslashes($pathsJson)
    );

    $cmd = sprintf('"%s" -c %s', $pythonVenv, escapeshellarg($pyScript));
    $output = @shell_exec($cmd);
    $pyResList = $output ? @json_decode(trim($output), true) : null;

    if (is_array($pyResList)) {
        foreach ($pyResList as $idx => $pyRes) {
            if (isset($savedFiles[$idx])) {
                $name = is_array($pyRes) ? ($pyRes['full_english_name'] ?? '') : '';
                if (empty($name)) {
                    $num = $idx + 1;
                    $name = "PASSPORT CUSTOMER {$num}";
                }
                $results[] = [
                    'file_path' => 'uploads/' . $savedFiles[$idx]['newName'],
                    'full_english_name' => $name,
                    'passport_no' => is_array($pyRes) ? ($pyRes['passport_no'] ?? '') : '',
                    'nationality' => is_array($pyRes) ? ($pyRes['nationality'] ?? 'THAI') : 'THAI',
                    'dob' => is_array($pyRes) ? ($pyRes['dob'] ?? '') : '',
                    'sex' => is_array($pyRes) ? ($pyRes['sex'] ?? '') : ''
                ];
            }
        }
    }
}

// Fallback placeholder fill if any remain
foreach ($savedFiles as $idx => $sf) {
    if (!isset($results[$idx])) {
        $num = $idx + 1;
        $results[] = [
            'file_path' => 'uploads/' . $sf['newName'],
            'full_english_name' => "PASSPORT CUSTOMER {$num}",
            'passport_no' => '',
            'nationality' => 'THAI',
            'dob' => '',
            'sex' => ''
        ];
    }
}

echo json_encode([
    'success' => true,
    'results' => $results
]);
exit;
