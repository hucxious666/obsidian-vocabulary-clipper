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

    def test_version_lookup_permissions_and_controls_are_packaged(self):
        manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        options = (ROOT / "extension" / "options.html").read_text(encoding="utf-8")
        self.assertEqual("1.6.1", manifest["version"])
        self.assertEqual(["http://*/*", "https://*/*", "file:///*"], manifest["host_permissions"])
        scripts = manifest["content_scripts"][0]
        self.assertEqual(
            ["lib.js", "lookup-details.js", "lookup-popover.js", "content.js"], scripts["js"]
        )
        resources = manifest["web_accessible_resources"][0]["resources"]
        self.assertIn("lookup-popover.css", resources)
        self.assertNotIn("viewer.html", resources)
        content_script = (ROOT / "extension" / "content.js").read_text(encoding="utf-8")
        background = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
        self.assertIn('kind: "open_pdf_viewer"', content_script)
        self.assertIn('message.kind === "open_pdf_viewer"', background)
        self.assertIn('id="youdao-app-key"', options)
        self.assertIn('id="youdao-secret-key"', options)
        self.assertNotIn('id="youdao-test-word"', options)
        self.assertIn('id="youdao-preview"', options)
        self.assertIn('id="double-click-lookup"', options)
        self.assertIn('id="auto-open-pdf"', options)
        self.assertIn('id="section-select"', options)
        self.assertIn('id="new-section"', options)
        self.assertIn('id="create-section"', options)
        self.assertIn("有道文本翻译", options)
        self.assertIn('id="youdao-test-text"', options)
        self.assertIn('id="dictionary-select"', options)
        self.assertIn('id="dictionary-status"', options)
        self.assertIn('id="manage-dictionaries"', options)
        self.assertIn('id="refresh-dictionaries"', options)
        options_script = (ROOT / "extension" / "options.js").read_text(encoding="utf-8")
        self.assertIn('action: "test_youdao_translation"', options_script)
        self.assertIn('action: "open_dictionary_manager"', options_script)
        self.assertIn('activeDictionary: elements.dictionary.value', options_script)
        self.assertIn('action: "select_dictionary"', options_script)
        self.assertIn('elements.dictionary.addEventListener("change", selectDictionary)', options_script)
        self.assertIn("chrome.runtime.reload()", options_script)
        self.assertIn("ClipperUi.canForwardNativeAction", background)
        self.assertNotIn('action: "test_youdao_dictionary"', options_script)
        viewer = (ROOT / "extension" / "viewer.html").read_text(encoding="utf-8")
        self.assertIn('<script src="lookup-details.js"></script>', viewer)

    def test_dictionary_catalog_and_visual_manager_are_packaged(self):
        catalog = json.loads((ROOT / "dictionary-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(["ecdict", "kaikki-en"], [pack["id"] for pack in catalog["packs"]])
        self.assertTrue((ROOT / "dictionary-manager.ps1").is_file())
        self.assertTrue((ROOT / "clipper" / "dictionary_manager_gui.py").is_file())
        manager = (ROOT / "clipper" / "dictionary_manager_gui.py").read_text(encoding="utf-8")
        native_host = (ROOT / "native_host.py").read_text(encoding="utf-8")
        manager_script = (ROOT / "dictionary-manager.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('installation_lock("dictionary-manager-gui-v2")', manager)
        self.assertIn("focus_existing_manager()", manager)
        self.assertIn("pythonw.exe", native_host)
        self.assertIn("pythonw.exe", manager_script)
        self.assertNotIn('"-WindowStyle", "Hidden"', native_host)

    def test_toolbar_popup_exposes_persistent_meaning_style_control(self):
        manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
        popup = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
        popup_script = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

        self.assertEqual("popup.html", manifest["action"]["default_popup"])
        self.assertIn('name="meaning-style"', popup)
        self.assertIn('value="covered"', popup)
        self.assertIn('value="plain"', popup)
        self.assertIn('id="current-section"', popup)
        self.assertIn('chrome.storage.local.set({ meaningStyle:', popup_script)
        self.assertIn("chrome.runtime.openOptionsPage()", popup_script)

    def test_lookup_popover_uses_visible_standard_host_element(self):
        popover = (ROOT / "extension" / "lookup-popover.js").read_text(encoding="utf-8")
        self.assertIn('document.createElement("div")', popover)
        self.assertIn('this.host.id = "obsidian-vocabulary-lookup"', popover)
        self.assertIn('this.host.dataset.ovcVersion = chrome.runtime.getManifest().version', popover)
        self.assertIn('"visibility", "visible", "important"', popover)
        self.assertNotIn('document.createElement("obsidian-vocabulary-lookup")', popover)

    def test_web_and_pdf_selection_routes_include_translation(self):
        popover = (ROOT / "extension" / "lookup-popover.js").read_text(encoding="utf-8")
        content = (ROOT / "extension" / "content.js").read_text(encoding="utf-8")
        viewer = (ROOT / "extension" / "viewer.js").read_text(encoding="utf-8")
        self.assertIn('action: "translate_selection"', popover)
        self.assertIn('action: "create_section_and_add_entry"', popover)
        self.assertIn('action: "select_section"', popover)
        self.assertIn('action.mode === "translation"', content)
        self.assertIn('action.mode === "translation"', viewer)
        self.assertIn('document.addEventListener("selectionchange"', viewer)
        self.assertIn('window.addEventListener("mouseup"', viewer)

    def test_install_and_uninstall_scripts_are_idempotent_by_design(self):
        install = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
        uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8-sig")
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertRegex(install, re.compile(r"New-Item[^\n]+-Force"))
        self.assertRegex(install, re.compile(r"Copy-Item[^\n]+-Force"))
        self.assertIn("Remove-Item -ErrorAction SilentlyContinue", uninstall)
        self.assertIn("dictionary-catalog.json", install)
        self.assertIn("dictionary-manager.ps1", install)
        self.assertIn("data\\dictionaries", install)
        self.assertNotIn("EXPECTED_ECDICT_SHA256", install)
        self.assertNotRegex(install, re.compile(r"Copy-Item[^\n]+data\\ecdict\.sqlite3"))
        self.assertIn("data/**/*.sqlite3", ignore)
        self.assertIn("data/dictionaries/", ignore)

    def test_pdf_reader_and_pinned_pdfjs_runtime_are_packaged(self):
        vendor = ROOT / "extension" / "vendor" / "pdfjs"
        for relative in (
            "build/pdf.min.js",
            "build/pdf.worker.min.js",
            "web/pdf_viewer.js",
            "web/pdf_viewer.css",
            "cmaps/LICENSE",
            "standard_fonts/LICENSE_FOXIT",
            "LICENSE",
            "VERSION",
        ):
            self.assertTrue((vendor / relative).is_file(), relative)
        self.assertEqual("6.1.200", (vendor / "VERSION").read_text(encoding="utf-8").strip())
        viewer = (ROOT / "extension" / "viewer.html").read_text(encoding="utf-8")
        self.assertIn('<div id="viewer-container" role="main"', viewer)
        for control in ("page-number", "zoom-out", "zoom-in", "fit-width", "download", "open-native"):
            self.assertIn(f'id="{control}"', viewer)


if __name__ == "__main__":
    unittest.main()
