import base64
import hashlib
import json
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_EXTENSION_ID = "mmjlnnjlmoladaommpnekimbpfmfdnmj"


class InstallLayoutTests(unittest.TestCase):
    def test_manifest_key_produces_registered_extension_id(self):
        manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256(base64.b64decode(manifest["key"])).digest()[:16]
        extension_id = "".join(chr(ord("a") + nibble) for byte in digest for nibble in (byte >> 4, byte & 15))
        self.assertEqual(EXPECTED_EXTENSION_ID, extension_id)

    def test_native_host_template_allows_only_registered_extension(self):
        manifest = json.loads((ROOT / "native-host-manifest.json.template").read_text(encoding="utf-8"))
        self.assertEqual("com.local.obsidian_vocabulary_clipper", manifest["name"])
        self.assertEqual([f"chrome-extension://{EXPECTED_EXTENSION_ID}/"], manifest["allowed_origins"])
        self.assertEqual("__HOST_PATH__", manifest["path"])

    def test_extension_has_a_real_png_icon(self):
        icon = (ROOT / "extension" / "icon.png").read_bytes()
        self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual((128, 128), struct.unpack(">II", icon[16:24]))
        self.assertGreater(len(icon), 100)

    def test_version_and_youdao_preview_controls_are_packaged(self):
        manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        options = (ROOT / "extension" / "options.html").read_text(encoding="utf-8")
        self.assertEqual("1.1.0", manifest["version"])
        self.assertIn('id="youdao-app-key"', options)
        self.assertIn('id="youdao-secret-key"', options)
        self.assertIn('id="youdao-test-word"', options)
        self.assertIn('id="youdao-preview"', options)

    def test_install_and_uninstall_scripts_are_idempotent_by_design(self):
        install = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
        uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8-sig")
        self.assertRegex(install, re.compile(r"New-Item[^\n]+-Force"))
        self.assertRegex(install, re.compile(r"Copy-Item[^\n]+-Force"))
        self.assertIn("Remove-Item -ErrorAction SilentlyContinue", uninstall)
        self.assertRegex(install, re.compile(r"EXPECTED_ECDICT_SHA256\s*=\s*'[0-9a-f]{64}'"))


if __name__ == "__main__":
    unittest.main()
