<?php
require __DIR__ . '/bootstrap.php';
$in = jsonBody();
$email = trim((string)($in['email'] ?? ''));
$pass  = (string)($in['password'] ?? '');

$q = $pdo->prepare('SELECT id,password_hash FROM users WHERE email=? LIMIT 1');
$q->execute([$email]);
$u = $q->fetch();
if (!$u || !password_verify($pass, $u['password_hash'])) {
  json(['error'=>'invalid_credentials'], 401);
}
$_SESSION['uid'] = (int)$u['id'];
json(['ok'=>true]);
