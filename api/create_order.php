<?php
require _DIR_ . '/bootstrap.php';
$uid = requireAuth();
$in = jsonBody();

$items = $in['items'] ?? [];
if (!is_array($items) || !count($items)) json(['error'=>'empty_cart'], 422);

// Считаем total и нормализуем данные
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
  $stmt = $pdo->prepare('INSERT INTO orders (user_id, total, status) VALUES (?, ?, "new")');
  $stmt->execute([$uid, $total]);
  $orderId = (int)$pdo->lastInsertId();

  $stmtIt = $pdo->prepare('INSERT INTO order_items (order_id, product_name, price, qty) VALUES (?, ?, ?, ?)');
  foreach ($rows as $r) {
    $stmtIt->execute([$orderId, $r['name'], $r['price'], $r['qty']]);
  }

  $pdo->commit();
  json(['ok'=>true, 'order_id'=>$orderId, 'total'=>$total]);
} catch (Throwable $e) {
  $pdo->rollBack();
  json(['error'=>'db_error'], 500);
}