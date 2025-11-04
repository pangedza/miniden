<?php
require __DIR__ . '/bootstrap.php';
$uid = requireAuth();
$q = $pdo->prepare('SELECT id,email,name,created_at FROM users WHERE id=?');
$q->execute([$uid]);
json(['user'=>$q->fetch()]);
