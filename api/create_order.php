<?php
require __DIR__ . '/bootstrap.php';
$uid = requireAuth();
$in = jsonBody();
$items = $in['items'] ?? [];
if (!is_array($items) || !count($items)) json(['error'=>'empty_cart'], 422);

$total = 0.0; $rows = [];
foreach ($items as $it) {
  $name = trim((string)($it['name'] ?? ''));
  $qty  = max(1, (int)($it['qty'] ?? 1));
  $price= (float)($it['price'] ?? 0);
  if ($name === '' || $price <= 0) continue;
  $rows[] = ['name'=>$name,'qty'=>$qty,'price'=>$price];
  $total += $price * $qty;
}
if (!$rows) json(['error'=>'invalid_items'], 422);

$pdo->beginTransaction();
try {
  $o = $pdo->prepare('INSERT INTO orders (user_id,total,status) VALUES (?,?, "new")');
  $o->execute([$uid,$total]);
  $oid = (int)$pdo->lastInsertId();

  $oi = $pdo->prepare('INSERT INTO order_items (order_id,product_name,price,qty) VALUES (?,?,?,?)');
  foreach ($rows as $r) $oi->execute([$oid,$r['name'],$r['price'],$r['qty']]);

  $pdo->commit();
  json(['ok'=>true,'order_id'=>$oid,'total'=>$total]);
} catch (Throwable $e) {
  $pdo->rollBack();
  json(['error'=>'db_error'], 500);
}
