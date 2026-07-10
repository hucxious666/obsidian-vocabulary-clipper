import unittest

from native_host import ALLOWED_ORIGIN, is_allowed_origin


class NativeHostOriginTests(unittest.TestCase):
    def test_accepts_only_the_fixed_extension_origin(self):
        self.assertTrue(is_allowed_origin(ALLOWED_ORIGIN))
        self.assertFalse(is_allowed_origin("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"))
        self.assertFalse(is_allowed_origin(""))


if __name__ == "__main__":
    unittest.main()
