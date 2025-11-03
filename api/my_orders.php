<?php
require _DIR_ . '/bootstrap.php';
$uid = requireAuth();

$stmt = $pdo->prepare(
  'SELECT o.id, o.total, o.status, o.created_at,
          JSON_ARRAYAGG(JSON_OBJECT("name", i.product_name, "qty", i.qty, "price", i.price)) AS items
   FROM orders o
   JOIN order_items i ON i.order_id = o.id
   WHERE o.user_id = ?
   GROUP BY o.id
   ORDER BY o.created_at DESC'
);
$stmt->execute([$uid]);
json(['orders' => $stmt->fetchAll()]);