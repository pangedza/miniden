"""Тесты совместимости хеширования паролей админки."""

import unittest

from services.passwords import hash_password, verify_password


class PasswordsTestCase(unittest.TestCase):
    def test_hash_and_verify_admin_password(self) -> None:
        raw_password = "admin"
        password_hash = hash_password(raw_password)

        self.assertNotEqual(password_hash, raw_password)
        self.assertTrue(verify_password(raw_password, password_hash))


if __name__ == "__main__":
    unittest.main()
