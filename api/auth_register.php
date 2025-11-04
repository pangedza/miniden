<?php
require __DIR__ . '/bootstrap.php';
$in = jsonBody();
$email = trim((string)($in['email'] ?? ''));
$pass  = (string)($in['password'] ?? '');
$name  = trim((string)($in['name'] ?? ''));

if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($pass) < 6) {
  json(['error'=>'invalid_input'], 422);
}
$q = $pdo->prepare('SELECT id FROM users WHERE email=? LIMIT 1');
$q->execute([$email]);
if ($q->fetch()) json(['error'=>'email_taken'], 409);

$hash = password_hash($pass, PASSWORD_BCRYPT);
$i = $pdo->prepare('INSERT INTO users (email,password_hash,name) VALUES (?,?,?)');
$i->execute([$email,$hash,$name ?: null]);

$_SESSION['uid'] = (int)$pdo->lastInsertId();
json(['ok'=>true]);
