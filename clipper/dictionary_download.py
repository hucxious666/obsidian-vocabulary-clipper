from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .dictionary_builder import build_database as build_ecdict
from .dictionary_catalog import CatalogPack, load_catalog
from .dictionary_lock import installation_lock
from .dictionary_schema import PackValidationError, validate_pack, write_pack_metadata
from .kaikki_builder import build_database as build_kaikki


Progress = Callable[[str, int, int], None]
Downloader = Callable[[str, Path, int, Progress, Mapping[str, str]], Mapping[str, str]]
ALLOWED_REQUEST_HEADERS = {"accept", "x-github-api-version"}


class DownloadError(RuntimeError):
    pass


def download_file(
    url: str,
    destination: Path,
    maximum: int,
    progress: Progress,
    request_headers: Mapping[str, str],
) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise DownloadError("词典来源必须使用 HTTPS")
    headers = {"User-Agent": "ObsidianVocabularyClipper/1.6"}
    headers.update(request_headers)
    if _windows_curl_available():
        return _download_curl(url, destination, maximum, progress, headers)
    try:
        return _download_urllib(url, destination, maximum, progress, headers)
    except DownloadError:
        raise
    except Exception:
        return _download_curl(url, destination, maximum, progress, headers)


def _windows_curl_available() -> bool:
    return os.name == "nt" and bool(shutil.which("curl.exe"))


def _download_urllib(
    url: str, destination: Path, maximum: int, progress: Progress, headers: Mapping[str, str],
) -> dict[str, str]:
    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        if total and total > maximum:
            raise DownloadError("词典下载大小超过清单限制")
        current = 0
        while chunk := response.read(1024 * 1024):
            current += len(chunk)
            if current > maximum:
                raise DownloadError("词典下载大小超过清单限制")
            handle.write(chunk)
            progress("download", current, total)
        return {key.casefold(): value for key, value in response.headers.items()}


def _curl_headers(path: Path) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in path.read_text(encoding="iso-8859-1", errors="replace").splitlines():
        if line.startswith("HTTP/"):
            headers = {}
        elif ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().casefold()] = value.strip()
    return headers


def _curl_command(
    executable: str, url: str, destination: Path, header_path: Path,
    maximum: int, headers: Mapping[str, str],
) -> list[str]:
    command = [
        executable, "--fail", "--location", "--silent", "--show-error",
        "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "30",
        "--max-time", "3600", "--retry", "2", "--retry-all-errors",
        "--max-filesize", str(maximum), "--dump-header", str(header_path),
        "--output", str(destination),
    ]
    for key, value in headers.items():
        command.extend(("--header", f"{key}: {value}"))
    return [*command, url]


def _download_curl(
    url: str, destination: Path, maximum: int, progress: Progress, headers: Mapping[str, str],
) -> dict[str, str]:
    executable = shutil.which("curl.exe")
    if not executable:
        raise DownloadError("词典下载失败，请检查网络后重试")
    header_path = destination.with_suffix(destination.suffix + ".headers")
    header_path.unlink(missing_ok=True)
    process = subprocess.Popen(
        _curl_command(executable, url, destination, header_path, maximum, headers),
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        while process.poll() is None:
            current = destination.stat().st_size if destination.exists() else 0
            if current > maximum:
                process.kill()
                raise DownloadError("词典下载大小超过清单限制")
            progress("download", current, 0)
            time.sleep(0.25)
        _stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise DownloadError("词典下载失败，请检查网络后重试") from RuntimeError(stderr.strip())
        progress("download", destination.stat().st_size, destination.stat().st_size)
        return _curl_headers(header_path)
    finally:
        header_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _find_pack(catalog_path: Path, pack_id: str) -> CatalogPack:
    pack = next((item for item in load_catalog(catalog_path) if item.id == pack_id), None)
    if pack is None:
        raise DownloadError("未知的离线词典")
    return pack


def _request_headers(source: Mapping[str, object]) -> dict[str, str]:
    configured = source.get("requestHeaders") or {}
    if not isinstance(configured, dict):
        raise DownloadError("词典清单包含无效请求头")
    headers: dict[str, str] = {}
    for key, value in configured.items():
        name = str(key).strip()
        content = str(value).strip()
        if name.casefold() not in ALLOWED_REQUEST_HEADERS:
            raise DownloadError("词典清单包含不允许的请求头")
        if not content or len(content) > 200 or "\r" in content or "\n" in content:
            raise DownloadError("词典清单包含无效请求头")
        headers[name] = content
    return headers


def _record_source(path: Path, pack: CatalogPack, digest: str, headers: Mapping[str, str]) -> None:
    connection = sqlite3.connect(path)
    write_pack_metadata(connection, {
        "source_url": str(pack.source.get("url") or ""),
        "source_sha256": digest,
        "source_etag": headers.get("etag", ""),
        "source_last_modified": headers.get("last-modified", ""),
        "installed_at": datetime.now(timezone.utc).isoformat(),
    })
    connection.commit()
    connection.close()


def install_pack(
    pack_id: str,
    catalog_path: Path,
    dictionary_root: Path,
    *,
    downloader: Downloader = download_file,
    progress: Progress | None = None,
    builders: Mapping[str, Callable[[Path, Path], int]] | None = None,
) -> dict[str, str]:
    pack = _find_pack(Path(catalog_path), pack_id)
    with installation_lock(pack.id):
        return _install_pack(pack, dictionary_root, downloader, progress, builders)


def _install_pack(
    pack: CatalogPack,
    dictionary_root: Path,
    downloader: Downloader,
    progress: Progress | None,
    builders: Mapping[str, Callable[[Path, Path], int]] | None,
) -> dict[str, str]:
    notify = progress or (lambda _phase, _current, _total: None)
    source = pack.source
    url = str(source.get("url") or "")
    maximum = int(source.get("maxDownloadBytes") or 0)
    expected_hash = str(source.get("sha256") or "").casefold()
    available = dict(builders or {"ecdict_csv": build_ecdict, "kaikki_jsonl_gzip": build_kaikki})
    builder = available.get(str(source.get("builder") or ""))
    if not url or maximum <= 0 or builder is None:
        raise DownloadError("词典清单缺少下载或构建信息")
    dictionary_root = Path(dictionary_root)
    dictionary_root.mkdir(parents=True, exist_ok=True)
    installing = dictionary_root / f"{pack.filename}.installing"
    installing.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="obsidian-vocabulary-dictionary-") as temp_dir:
            suffix = ".jsonl.gz" if url.casefold().endswith(".gz") else ".csv"
            downloaded = Path(temp_dir) / f"source{suffix}"
            headers = downloader(url, downloaded, maximum, notify, _request_headers(source))
            digest = _sha256(downloaded)
            if expected_hash and digest != expected_hash:
                raise DownloadError("词典文件 SHA-256 校验失败")
            notify("build", 0, 0)
            try:
                builder(downloaded, installing)
                validate_pack(installing, pack.id)
            except (PackValidationError, Exception) as error:
                if isinstance(error, DownloadError):
                    raise
                raise DownloadError("词典构建失败，原有词典未被修改") from error
            _record_source(installing, pack, digest, headers)
            os.replace(installing, dictionary_root / pack.filename)
            notify("complete", 1, 1)
            return validate_pack(dictionary_root / pack.filename, pack.id)
    finally:
        installing.unlink(missing_ok=True)
