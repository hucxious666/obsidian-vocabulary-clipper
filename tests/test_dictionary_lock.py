import os
import threading
import unittest

from clipper.dictionary_lock import DictionaryBusyError, installation_lock


@unittest.skipUnless(os.name == "nt", "Windows named mutex test")
class DictionaryLockTests(unittest.TestCase):
    def test_rejects_second_process_or_thread_for_same_pack(self):
        acquired = threading.Event()
        release = threading.Event()

        def hold_lock():
            with installation_lock("unit-test-pack"):
                acquired.set()
                release.wait(5)

        thread = threading.Thread(target=hold_lock)
        thread.start()
        self.assertTrue(acquired.wait(2))
        try:
            with self.assertRaisesRegex(DictionaryBusyError, "正在安装"):
                with installation_lock("unit-test-pack"):
                    pass
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
