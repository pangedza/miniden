<?php
require _DIR_ . '/bootstrap.php';

$in = jsonBody();
$email = trim((string)($in['email'] ?? ''));
$pass  = (string)($in['password'] ?? '');

$stmt = $pdo->prepare('SELECT id, password_hash FROM users WHERE email = ? LIMIT 1');
$stmt->execute([$email]);
$u = $stmt->fetch();

if (!$u || !password_verify($pass, $u['password_hash'])) {
  json(['error'=>'invalid_credentials'], 401);
}

$_SESSION['uid'] = (int)$u['id'];
json(['ok'=>true]);