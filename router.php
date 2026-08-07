<?php
/**
 * Router script for PHP Built-in Server
 */

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

if (strpos($uri, '/api/') === 0 || $uri === '/api') {
    require __DIR__ . '/api.php';
    exit;
}

if ($uri !== '/' && file_exists(__DIR__ . $uri)) {
    return false; // serve static file
}

require __DIR__ . '/index.php';
