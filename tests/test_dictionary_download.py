import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clipper.dictionary_download import DownloadError, download_file, install_pack
from clipper.dictionary_schema import create_pack_schema, validate_pack, write_pack_metadata


def _catalog(
    path: Path, source: Path, digest: str, request_headers: dict[str, str] | None = None,
) -> Path:
    catalog = path / "catalog.json"
    catalog.write_text(json.dumps({
        "schemaVersion": 1,
        "packs": [{
            "id": "ecdict", "name": "ECDICT", "filename": "ecdict.sqlite3",
            "url": "https://example.invalid/ecdict.csv", "builder": "ecdict_csv",
            "sha256": digest, "maxDownloadBytes": 1_000_000,
            "requestHeaders": request_headers or {},
        }],
    }), encoding="utf-8")
    return catalog


def _write_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "word", "phonetic", "definition", "translation", "pos", "exchange",
        ])
        writer.writeheader()
        writer.writerow({
            "word": "word", "phonetic": "wɜːd", "definition": "unit of language",
            "translation": "n. 单词", "pos": "n:100", "exchange": "s:words",
        })


class DictionaryDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.csv"
        _write_csv(self.source)
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.catalog = _catalog(self.root, self.source, self.digest)
        self.target = self.root / "dictionaries"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _copy_download(self, _url, destination, _maximum, progress, _headers):
        destination.write_bytes(self.source.read_bytes())
        progress("download", destination.stat().st_size, destination.stat().st_size)
        return {}

    def test_installs_valid_pack_atomically_and_reports_progress(self):
        events = []
        result = install_pack(
            "ecdict", self.catalog, self.target,
            downloader=self._copy_download, progress=lambda *event: events.append(event),
        )

        self.assertEqual("ecdict", result["id"])
        self.assertEqual("ecdict", validate_pack(self.target / "ecdict.sqlite3")["id"])
        connection = sqlite3.connect(self.target / "ecdict.sqlite3")
        self.assertEqual(("unit of language",), connection.execute(
            "SELECT definition FROM entries WHERE word='word'"
        ).fetchone())
        connection.close()
        self.assertTrue(any(event[0] == "download" for event in events))
        self.assertTrue(any(event[0] == "build" for event in events))

    def test_passes_catalog_request_headers_to_downloader(self):
        catalog = _catalog(
            self.root, self.source, self.digest,
            {"Accept": "application/vnd.github.raw+json"},
        )
        received = {}

        def download(url, destination, maximum, progress, headers):
            received.update(headers)
            return self._copy_download(url, destination, maximum, progress, headers)

        install_pack("ecdict", catalog, self.target, downloader=download)

        self.assertEqual(
            "application/vnd.github.raw+json",
            received["Accept"],
        )

    def test_download_prefers_windows_curl_to_avoid_openssl_incompatibility(self):
        destination = self.root / "fallback.csv"
        with (
            patch(
                "clipper.dictionary_download._windows_curl_available", return_value=True,
            ),
            patch("clipper.dictionary_download._download_urllib") as urllib_download,
            patch(
                "clipper.dictionary_download._download_curl",
                return_value={"etag": "fallback"},
            ) as fallback,
        ):
            result = download_file(
                "https://example.invalid/dictionary.csv",
                destination,
                1_000,
                lambda *_event: None,
                {},
            )

        self.assertEqual("fallback", result["etag"])
        fallback.assert_called_once()
        urllib_download.assert_not_called()

    def test_hash_failure_does_not_replace_existing_pack(self):
        self.target.mkdir()
        existing = self.target / "ecdict.sqlite3"
        connection = sqlite3.connect(existing)
        create_pack_schema(connection)
        write_pack_metadata(connection, {"id": "ecdict", "name": "Old"})
        connection.commit()
        connection.close()
        before = existing.read_bytes()
        wrong_catalog = _catalog(self.root, self.source, "0" * 64)

        with self.assertRaisesRegex(DownloadError, "SHA-256"):
            install_pack("ecdict", wrong_catalog, self.target, downloader=self._copy_download)

        self.assertEqual(before, existing.read_bytes())
        self.assertFalse(any(self.target.glob("*.installing")))

    def test_builder_failure_does_not_replace_existing_pack(self):
        self.target.mkdir()
        existing = self.target / "ecdict.sqlite3"
        existing.write_bytes(b"old dictionary")

        def fail_builder(_source, _target):
            raise RuntimeError("fixture build failed")

        with self.assertRaisesRegex(DownloadError, "构建失败"):
            install_pack(
                "ecdict", self.catalog, self.target, downloader=self._copy_download,
                builders={"ecdict_csv": fail_builder},
            )

        self.assertEqual(b"old dictionary", existing.read_bytes())
        self.assertFalse(any(self.target.glob("*.installing")))


if __name__ == "__main__":
    unittest.main()
