<?php
// Всегда одной строкой в начале:
declare(strict_types=1);

// Загружаем конфиг
$config = require _DIR_ . '/config.php';

// Подключаемся к БД (PDO + utf8mb4 + исключения)
$dsn = "mysql:host={$config['db_host']};dbname={$config['db_name']};charset=utf8mb4";
$options = [
  PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
  PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
  PDO::ATTR_EMULATE_PREPARES => false,
];
$pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], $options);

// Сессии (кука httpOnly, sameSite=Lax)
session_set_cookie_params([
  'lifetime' => 60*60*24*7,
  'path'     => '/',
  'domain'   => $config['cookie_domain'],
  'secure'   => isset($_SERVER['HTTPS']),
  'httponly' => true,
  'samesite' => 'Lax'
]);
session_start();

// Ответ JSON хелпер
function json($data, int $code = 200): void {
  http_response_code($code);
  header('Content-Type: application/json; charset=utf-8');
  echo json_encode($data, JSON_UNESCAPED_UNICODE);
  exit;
}

// Чтение тела запроса в JSON
function jsonBody(): array {
  $raw = file_get_contents('php://input');
  $data = json_decode($raw ?: '[]', true);
  return is_array($data) ? $data : [];
}

function requireAuth(): int {
  if (!isset($_SESSION['uid'])) json(['error' => 'unauthorized'], 401);
  return (int)$_SESSION['uid'];
}