<?php
require _DIR_ . '/bootstrap.php';

$in = jsonBody();
$email = trim((string)($in['email'] ?? ''));
$pass  = (string)($in['password'] ?? '');
$name  = trim((string)($in['name'] ?? ''));

if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($pass) < 6) {
  json(['error'=>'invalid_input'], 422);
}

// Проверка существования
$stmt = $pdo->prepare('SELECT id FROM users WHERE email = ? LIMIT 1');
$stmt->execute([$email]);
if ($stmt->fetch()) json(['error'=>'email_taken'], 409);

// Хеш пароля
$hash = password_hash($pass, PASSWORD_BCRYPT);

// Вставка
$stmt = $pdo->prepare('INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)');
$stmt->execute([$email, $hash, $name ?: null]);

$_SESSION['uid'] = (int)$pdo->lastInsertId();
json(['ok'=>true]);