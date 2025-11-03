<?php
require _DIR_ . '/bootstrap.php';
session_destroy();
json(['ok'=>true]);