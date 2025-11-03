<?php
require _DIR_ . '/bootstrap.php';
$uid = requireAuth();

$stmt = $pdo->prepare('SELECT id, email, name, created_at FROM users WHERE id = ?');
$stmt->execute([$uid]);
json(['user' => $stmt->fetch()]);