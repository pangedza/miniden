<?php
declare(strict_types=1);
$cfg = require __DIR__ . '/config.php';

$dsn = "mysql:host={$cfg['db_host']};dbname={$cfg['db_name']};charset=utf8mb4";
$opt = [
  PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
  PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
  PDO::ATTR_EMULATE_PREPARES => false,
];
$pdo = new PDO($dsn, $cfg['db_user'], $cfg['db_pass'], $opt);

session_set_cookie_params([
  'lifetime' => 60*60*24*7,
  'path'     => '/',
  'domain'   => $cfg['cookie_domain'],
  'secure'   => !empty($_SERVER['HTTPS']),
  'httponly' => true,
  'samesite' => 'Lax',
]);
session_start();

function json($data, int $code=200): void {
  http_response_code($code);
  header('Content-Type: application/json; charset=utf-8');
  echo json_encode($data, JSON_UNESCAPED_UNICODE);
  exit;
}
function jsonBody(): array {
  $raw = file_get_contents('php://input');
  $data = json_decode($raw ?: '[]', true);
  return is_array($data) ? $data : [];
}
function requireAuth(): int {
  if (!isset($_SESSION['uid'])) json(['error'=>'unauthorized'], 401);
  return (int)$_SESSION['uid'];
}
