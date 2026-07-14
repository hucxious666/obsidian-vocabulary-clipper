from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .dictionary_catalog import CatalogPack, load_catalog
from .dictionary_download import install_pack
from .dictionary_lock import DictionaryBusyError, installation_lock
from .dictionary_repository import DictionaryRepository


def _size_label(value: object) -> str:
    size = int(value or 0)
    return f"{size / 1024 / 1024:.0f} MB" if size else "大小未知"


class DictionaryManagerApp:
    def __init__(self, root: tk.Tk, catalog_path: Path, dictionary_root: Path):
        self.root = root
        self.catalog_path = Path(catalog_path)
        self.dictionary_root = Path(dictionary_root)
        self.packs = load_catalog(self.catalog_path)
        self.events: queue.Queue = queue.Queue()
        self.statuses: dict[str, tk.StringVar] = {}
        self.buttons: dict[str, ttk.Button] = {}
        self.active_job = ""
        self.progress = ttk.Progressbar(root, maximum=100)
        self.message = tk.StringVar(value="请选择需要安装或更新的词典。")
        self._build_ui()
        self.refresh()
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        self.root.title("Obsidian 词汇采集器 - 离线词典")
        self.root.geometry("660x360")
        self.root.minsize(620, 320)
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="离线词典", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="词典下载后保存在本机，不会写入 Git 仓库。").pack(anchor="w", pady=(4, 16))
        for pack in self.packs:
            self._pack_row(frame, pack)
        self.progress.pack(in_=frame, fill="x", pady=(18, 6))
        ttk.Label(frame, textvariable=self.message, wraplength=610).pack(anchor="w")
        ttk.Button(frame, text="关闭", command=self.root.destroy).pack(anchor="e", pady=(18, 0))

    def _pack_row(self, parent: ttk.Frame, pack: CatalogPack) -> None:
        row = ttk.Frame(parent, padding=(12, 10))
        row.pack(fill="x", pady=4)
        details = ttk.Frame(row)
        details.pack(side="left", fill="x", expand=True)
        ttk.Label(details, text=pack.name, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        size = _size_label(pack.source.get("downloadBytes"))
        ttk.Label(details, text=f"下载约 {size} · {pack.source.get('license', '')}").pack(anchor="w")
        if pack.source.get("note"):
            ttk.Label(details, text=str(pack.source["note"]), wraplength=430).pack(anchor="w")
        status = tk.StringVar()
        ttk.Label(row, textvariable=status, width=10).pack(side="left", padx=10)
        button = ttk.Button(row, text="安装/更新", command=lambda: self.install(pack.id))
        button.pack(side="right")
        self.statuses[pack.id] = status
        self.buttons[pack.id] = button

    def refresh(self) -> None:
        states = {item["id"]: item["installed"] for item in DictionaryRepository(
            self.dictionary_root, self.catalog_path
        ).list_packs()}
        for pack in self.packs:
            self.statuses[pack.id].set("已安装" if states.get(pack.id) else "未安装")

    def install(self, pack_id: str) -> None:
        if self.active_job:
            return
        self.active_job = pack_id
        self.progress.configure(mode="determinate", value=0)
        self.message.set("正在准备下载…")
        for button in self.buttons.values():
            button.configure(state="disabled")
        threading.Thread(target=self._install_worker, args=(pack_id,), daemon=True).start()

    def _install_worker(self, pack_id: str) -> None:
        try:
            install_pack(
                pack_id, self.catalog_path, self.dictionary_root,
                progress=lambda *event: self.events.put(("progress", *event)),
            )
            self.events.put(("done", pack_id))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: tuple) -> None:
        if event[0] == "progress":
            self._show_progress(str(event[1]), int(event[2]), int(event[3]))
            return
        self.active_job = ""
        for button in self.buttons.values():
            button.configure(state="normal")
        if event[0] == "done":
            self.refresh()
            self.progress.configure(mode="determinate", value=100)
            self.message.set("词典安装完成。返回 Chrome 设置页刷新后即可切换。")
        else:
            self.message.set(event[1] or "词典安装失败")
            messagebox.showerror("词典安装失败", self.message.get())

    def _show_progress(self, phase: str, current: int, total: int) -> None:
        if phase == "download":
            if total:
                self.progress.configure(mode="determinate", value=current * 100 / total)
            self.message.set(f"正在下载：{_size_label(current)} / {_size_label(total)}")
        elif phase == "build":
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            self.message.set("正在构建 SQLite 词典，请保持窗口打开…")
        elif phase == "complete":
            self.progress.stop()


def main() -> int:
    app_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=app_root / "dictionary-catalog.json")
    parser.add_argument("--target", type=Path, default=app_root / "data" / "dictionaries")
    args = parser.parse_args()
    try:
        with installation_lock("dictionary-manager-gui"):
            root = tk.Tk()
            DictionaryManagerApp(root, args.catalog, args.target)
            root.mainloop()
    except DictionaryBusyError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
