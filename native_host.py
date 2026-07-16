from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from clipper.config import ConfigStore
from clipper.dpapi import DpapiProtector
from clipper.dictionary_repository import DictionaryRepository
from clipper.protocol import read_message, write_message
from clipper.service import ClipperService


EXTENSION_ID = "mmjlnnjlmoladaommpnekimbpfmfdnmj"
ALLOWED_ORIGIN = f"chrome-extension://{EXTENSION_ID}/"


def is_allowed_origin(origin: str) -> bool:
    return origin == ALLOWED_ORIGIN


def choose_markdown_file(initial_path: str) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    initial = Path(initial_path) if initial_path else None
    selected = filedialog.askopenfilename(
        title="选择 Obsidian Markdown 文件",
        initialdir=str(initial.parent if initial and initial.is_file() else initial or Path.home()),
        filetypes=[("Markdown", "*.md")],
    )
    root.destroy()
    return selected


def create_service() -> ClipperService:
    app_root = Path(__file__).resolve().parent
    data_root = Path(os.environ.get("LOCALAPPDATA", app_root)) / "ObsidianVocabularyClipper"
    return ClipperService(
        ConfigStore(data_root / "config.json", DpapiProtector()),
        app_root / "data" / "ecdict.sqlite3",
        data_root / "backups",
        file_picker=choose_markdown_file,
        dictionary_repository=DictionaryRepository(
            app_root / "data" / "dictionaries", app_root / "dictionary-catalog.json"
        ),
        dictionary_manager_launcher=lambda: open_dictionary_manager(app_root),
    )


def _manager_python() -> Path:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return pythonw if pythonw.is_file() else Path(sys.executable)


def open_dictionary_manager(app_root: Path) -> None:
    subprocess.Popen(
        [
            str(_manager_python()), "-m", "clipper.dictionary_manager_gui",
            "--catalog", str(app_root / "dictionary-catalog.json"),
            "--target", str(app_root / "data" / "dictionaries"),
        ],
        cwd=app_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )


def _enable_binary_stdio() -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


def serve_messages(input_stream, output_stream, service: ClipperService) -> None:
    while True:
        message = read_message(input_stream)
        if message is None:
            return
        response = service.handle(message)
        if "requestId" in message:
            response = {**response, "requestId": message["requestId"]}
        write_message(output_stream, response)


def main() -> int:
    _enable_binary_stdio()
    origin = sys.argv[1] if len(sys.argv) > 1 else ""
    if not is_allowed_origin(origin):
        write_message(sys.stdout.buffer, {"ok": False, "status": "invalid", "message": "扩展来源未授权"})
        return 2
    try:
        serve_messages(sys.stdin.buffer, sys.stdout.buffer, create_service())
        return 0
    except Exception:
        write_message(
            sys.stdout.buffer,
            {"ok": False, "status": "write_failed", "message": "本地服务处理请求失败"},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
