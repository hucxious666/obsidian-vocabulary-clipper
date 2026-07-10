import os
import unittest

from clipper.dpapi import DpapiProtector


@unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
class DpapiProtectorTests(unittest.TestCase):
    def test_round_trip_does_not_expose_plaintext(self):
        protector = DpapiProtector()
        encrypted = protector.protect("sensitive-value")
        self.assertNotIn("sensitive-value", encrypted)
        self.assertEqual("sensitive-value", protector.unprotect(encrypted))


if __name__ == "__main__":
    unittest.main()
