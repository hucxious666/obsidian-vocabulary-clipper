from __future__ import annotations

from pathlib import Path
from typing import Callable

from .config import AppConfig, ConfigStore, SettingsValidationError
from .dictionary import DictionaryLookup, LookupNotFound
from .markdown_writer import (
    ConcurrentWriteError,
    DuplicateEntry,
    ensure_not_duplicate,
    find_chapters,
    write_entry_atomic,
)
from .meaning import normalize_ecdict_translation
from .selection import InvalidSelection, normalize_selection
from .translator import BaiduTranslateError, BaiduTranslator
from .youdao import YoudaoDictionaryClient, YoudaoDictionaryError


class ClipperService:
    ACTIONS = {
        "get_settings",
        "browse_file",
        "save_settings",
        "test_connection",
        "test_youdao_dictionary",
        "add_entry",
    }

    def __init__(
        self,
        config_store: ConfigStore,
        dictionary_path: Path,
        backup_root: Path,
        dictionary_factory: Callable = DictionaryLookup,
        translator_factory: Callable = BaiduTranslator,
        youdao_factory: Callable = YoudaoDictionaryClient,
        file_picker: Callable[[str], str] | None = None,
    ):
        self.config_store = config_store
        self.dictionary_path = Path(dictionary_path)
        self.backup_root = Path(backup_root)
        self.dictionary_factory = dictionary_factory
        self.translator_factory = translator_factory
        self.youdao_factory = youdao_factory
        self.file_picker = file_picker

    def handle(self, message: dict) -> dict:
        if not isinstance(message, dict) or message.get("action") not in self.ACTIONS:
            return self._error("invalid", "不支持的操作")
        try:
            action = message["action"]
            if action == "get_settings":
                return {"ok": True, "status": "ok", **self.config_store.public_settings()}
            if action == "browse_file":
                return self._browse_file(message)
            if action == "save_settings":
                return self._save_settings(message)
            if action == "test_connection":
                return self._test_connection()
            if action == "test_youdao_dictionary":
                return self._test_youdao_dictionary(message)
            return self._add_entry(message)
        except (SettingsValidationError, InvalidSelection, ValueError) as error:
            return self._error("invalid", str(error))
        except (LookupNotFound, BaiduTranslateError, YoudaoDictionaryError) as error:
            return self._error("lookup_failed", str(error))
        except Exception:
            return self._error("write_failed", "本地服务发生未预期错误")

    def _browse_file(self, message: dict) -> dict:
        if message.get("target") not in {"chapter", "news"} or self.file_picker is None:
            return self._error("invalid", "文件选择请求无效")
        initial = str(message.get("initialPath") or "")
        selected = self.file_picker(initial)
        if not selected:
            return {"ok": False, "status": "cancelled", "message": "已取消"}
        path = self.config_store.validate_path(selected)
        result = {"ok": True, "status": "ok", "path": str(path)}
        if message["target"] == "chapter":
            result["chapters"] = self._read_chapters(path)
        return result

    def _save_settings(self, message: dict) -> dict:
        try:
            existing = self.config_store.load()
        except SettingsValidationError:
            existing = None
        app_id = str(message.get("appId") or (existing.app_id if existing else ""))
        secret_key = str(message.get("secretKey") or (existing.secret_key if existing else ""))
        new_youdao_app_key = str(message.get("youdaoAppKey") or "").strip()
        new_youdao_secret_key = str(message.get("youdaoSecretKey") or "").strip()
        if bool(new_youdao_app_key) != bool(new_youdao_secret_key):
            raise SettingsValidationError("修改有道凭据时必须同时填写 App Key 和 App Secret")
        youdao_app_key = new_youdao_app_key or (existing.youdao_app_key if existing else "")
        youdao_secret_key = new_youdao_secret_key or (
            existing.youdao_secret_key if existing else ""
        )
        config = AppConfig(
            chapter_file=str(message.get("chapterFile") or ""),
            news_file=str(message.get("newsFile") or ""),
            selected_chapter=int(message.get("selectedChapter") or 0),
            app_id=app_id,
            secret_key=secret_key,
            youdao_app_key=youdao_app_key,
            youdao_secret_key=youdao_secret_key,
        )
        self.config_store.save(config)
        return {"ok": True, "status": "saved", **self.config_store.public_settings()}

    def _test_connection(self) -> dict:
        config = self.config_store.load()
        if not self.dictionary_path.is_file():
            return self._error("lookup_failed", "离线词典尚未安装")
        self.translator_factory(config.app_id, config.secret_key).translate("test")
        return {"ok": True, "status": "ok", "message": "词典、百度翻译和文件配置可用"}

    def _test_youdao_dictionary(self, message: dict) -> dict:
        word = normalize_selection(str(message.get("text") or ""))
        config = self.config_store.load()
        if not config.youdao_app_key or not config.youdao_secret_key:
            return self._error("invalid", "请先保存有道 App Key 和 App Secret")
        result = self.youdao_factory(
            config.youdao_app_key, config.youdao_secret_key
        ).lookup(word)
        return {
            "ok": True,
            "status": "ok",
            "message": "有道词典查询成功（结果仅预览，不会写入）",
            "preview": {
                "word": result.word,
                "phonetic": result.phonetic,
                "explains": result.explains,
            },
        }

    def _add_entry(self, message: dict) -> dict:
        target = message.get("target")
        if target not in {"chapter", "news"}:
            return self._error("invalid", "写入目标无效")
        word = normalize_selection(str(message.get("text") or ""))
        config = self.config_store.load()
        try:
            path = Path(config.chapter_file if target == "chapter" else config.news_file)
            chapter = config.selected_chapter if target == "chapter" else None
            ensure_not_duplicate(path, target, chapter, word)
            dictionary_entry = self.dictionary_factory(self.dictionary_path).lookup(word)
            meaning = normalize_ecdict_translation(dictionary_entry.translation)
            if not meaning:
                meaning = self.translator_factory(config.app_id, config.secret_key).translate(word)
            result = write_entry_atomic(
                path, target, chapter, word, dictionary_entry.phonetic, meaning, self.backup_root
            )
            label = f"Chapter {chapter}" if target == "chapter" else "NEWS"
            return {
                "ok": True,
                "status": "added",
                "word": word,
                "number": result.number,
                "targetLabel": label,
                "message": f"已加入 {label}",
            }
        except DuplicateEntry as error:
            return self._error("duplicate", str(error))
        except (LookupNotFound, BaiduTranslateError) as error:
            return self._error("lookup_failed", str(error))
        except ConcurrentWriteError as error:
            return self._error("conflict", str(error))
        except OSError:
            return self._error("write_failed", "Markdown 文件写入失败")

    def _read_chapters(self, path: Path) -> list[int]:
        data = path.read_bytes()
        text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
        return find_chapters(text)

    @staticmethod
    def _error(status: str, message: str) -> dict:
        return {"ok": False, "status": status, "message": message}
