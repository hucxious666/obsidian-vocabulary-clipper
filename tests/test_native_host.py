import io
import unittest

from clipper.protocol import read_message, write_message
from native_host import ALLOWED_ORIGIN, is_allowed_origin, serve_messages


class NativeHostOriginTests(unittest.TestCase):
    def test_accepts_only_the_fixed_extension_origin(self):
        self.assertTrue(is_allowed_origin(ALLOWED_ORIGIN))
        self.assertFalse(is_allowed_origin("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"))
        self.assertFalse(is_allowed_origin(""))

    def test_serves_multiple_messages_and_echoes_request_ids(self):
        incoming = io.BytesIO()
        write_message(incoming, {"requestId": "first", "action": "lookup_definition"})
        write_message(incoming, {"requestId": "second", "action": "get_settings"})
        incoming.seek(0)
        outgoing = io.BytesIO()

        class FakeService:
            def handle(self, message):
                return {"ok": True, "status": message["action"]}

        serve_messages(incoming, outgoing, FakeService())

        outgoing.seek(0)
        self.assertEqual(
            {"ok": True, "status": "lookup_definition", "requestId": "first"},
            read_message(outgoing),
        )
        self.assertEqual(
            {"ok": True, "status": "get_settings", "requestId": "second"},
            read_message(outgoing),
        )
        self.assertIsNone(read_message(outgoing))


if __name__ == "__main__":
    unittest.main()
