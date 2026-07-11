from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from .config import AppConfig, ConfigStore, SettingsValidationError
from .dictionary import DictionaryLookup, LookupNotFound
from .markdown_writer import (
    ConcurrentWriteError,
    DuplicateEntry,
    create_section_atomic,
    ensure_not_duplicate,
    find_sections,
    normalize_section_name,
    restore_bytes_atomic,
    write_entry_atomic,
)
from .meaning import normalize_ecdict_translation, parse_definition_groups
from .selection import InvalidSelection, normalize_selection, normalize_translation_selection
from .translator import BaiduTranslateError, BaiduTranslator
from .youdao import YoudaoTranslateError, YoudaoTranslator


class ClipperService:
    ACTIONS = {
        "get_settings",
        "browse_file",
        "save_settings",
        "test_connection",
        "test_youdao_translation",
        "lookup_definition",
        "translate_selection",
        "add_entry",
        "select_section",
        "create_section",
        "create_section_and_add_entry",
    }

    def __init__(
        self,
        config_store: ConfigStore,
        dictionary_path: Path,
        backup_root: Path,
        dictionary_factory: Callable = DictionaryLookup,
        translator_factory: Callable = BaiduTranslator,
        youdao_factory: Callable = YoudaoTranslator,
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
            if action == "test_youdao_translation":
                return self._test_youdao_translation(message)
            if action == "lookup_definition":
                return self._lookup_definition(message)
            if action == "translate_selection":
                return self._translate_selection(message)
            if action == "select_section":
                return self._select_section(message)
            if action in {"create_section", "create_section_and_add_entry"}:
                return self._create_section(message, action == "create_section_and_add_entry")
            return self._add_entry(message)
        except (SettingsValidationError, InvalidSelection, ValueError) as error:
            return self._error("invalid", str(error))
        except (LookupNotFound, BaiduTranslateError, YoudaoTranslateError) as error:
            return self._error("lookup_failed", str(error))
        except Exception:
            return self._error("write_failed", "本地服务发生未预期错误")

    def _browse_file(self, message: dict) -> dict:
        targets = {"chapter": "section", "news": "append", "section": "section", "append": "append"}
        target = targets.get(message.get("target"))
        if target is None or self.file_picker is None:
            return self._error("invalid", "文件选择请求无效")
        initial = str(message.get("initialPath") or "")
        selected = self.file_picker(initial)
        if not selected:
            return {"ok": False, "status": "cancelled", "message": "已取消"}
        path = self.config_store.validate_path(selected)
        result = {"ok": True, "status": "ok", "path": str(path)}
        if target == "section":
            result["sections"] = self._read_sections(path)
            result["chapters"] = [
                int(name.removeprefix("Chapter "))
                for name in result["sections"]
                if name.startswith("Chapter ") and name.removeprefix("Chapter ").isdigit()
            ]
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
            section_file=str(message.get("sectionFile") or message.get("chapterFile") or ""),
            append_file=str(message.get("appendFile") or message.get("newsFile") or ""),
            selected_section=str(
                message.get("selectedSection")
                or f"Chapter {int(message.get('selectedChapter') or 0)}"
            ),
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

    def _test_youdao_translation(self, message: dict) -> dict:
        text = normalize_translation_selection(str(message.get("text") or ""))
        config = self.config_store.load()
        if not config.youdao_app_key or not config.youdao_secret_key:
            return self._error("invalid", "请先保存有道 App Key 和 App Secret")
        translated = self.youdao_factory(
            config.youdao_app_key, config.youdao_secret_key
        ).translate(text)
        return {
            "ok": True,
            "status": "ok",
            "message": "有道文本翻译成功（结果仅预览，不会写入）",
            "preview": {
                "sourceText": text,
                "translatedText": translated,
                "source": "youdao",
            },
        }

    def _lookup_definition(self, message: dict) -> dict:
        word = normalize_selection(str(message.get("text") or ""))
        entry = self.dictionary_factory(self.dictionary_path).lookup(word)
        groups = parse_definition_groups(entry.translation)
        source = "ecdict"
        if not groups:
            config = self.config_store.load()
            translation = self.translator_factory(config.app_id, config.secret_key).translate(word)
            groups = [{"partOfSpeech": "释义", "definitions": [translation]}]
            source = "baidu"
        return {
            "ok": True,
            "status": "ok",
            "definition": {
                "word": word,
                "phonetic": entry.phonetic,
                "source": source,
                "groups": groups,
            },
        }

    def _translate_selection(self, message: dict) -> dict:
        text = normalize_translation_selection(str(message.get("text") or ""))
        config = self.config_store.load()
        source = "baidu"
        try:
            translated = self.translator_factory(config.app_id, config.secret_key).translate(text)
        except BaiduTranslateError as baidu_error:
            if not config.youdao_app_key or not config.youdao_secret_key:
                raise BaiduTranslateError(
                    f"{baidu_error}；未配置有道翻译后备"
                ) from baidu_error
            try:
                translated = self.youdao_factory(
                    config.youdao_app_key, config.youdao_secret_key
                ).translate(text)
            except YoudaoTranslateError as youdao_error:
                raise YoudaoTranslateError(
                    f"百度和有道翻译均失败：{baidu_error}；{youdao_error}"
                ) from youdao_error
            source = "youdao"
        return {
            "ok": True,
            "status": "ok",
            "translation": {
                "sourceText": text,
                "translatedText": translated,
                "source": source,
            },
        }

    def _add_entry(self, message: dict) -> dict:
        target = {"chapter": "section", "news": "append"}.get(
            message.get("target"), message.get("target")
        )
        if target not in {"section", "append"}:
            return self._error("invalid", "写入目标无效")
        word = normalize_selection(str(message.get("text") or ""))
        config = self.config_store.load()
        try:
            path = Path(config.section_file if target == "section" else config.append_file)
            section = str(message.get("sectionName") or config.selected_section) if target == "section" else None
            ensure_not_duplicate(path, target, section, word)
            dictionary_entry = self.dictionary_factory(self.dictionary_path).lookup(word)
            meaning = normalize_ecdict_translation(dictionary_entry.translation)
            if not meaning:
                meaning = self.translator_factory(config.app_id, config.secret_key).translate(word)
            result = write_entry_atomic(
                path, target, section, word, dictionary_entry.phonetic, meaning, self.backup_root
            )
            label = section if target == "section" else "笔记末尾"
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

    def _select_section(self, message: dict) -> dict:
        config = self.config_store.load()
        name = normalize_section_name(str(message.get("sectionName") or ""))
        self.config_store.save(replace(config, selected_section=name))
        return {"ok": True, "status": "selected", **self.config_store.public_settings()}

    def _create_section(self, message: dict, add_entry: bool) -> dict:
        config = self.config_store.load()
        name = normalize_section_name(str(message.get("sectionName") or ""))
        path = Path(config.section_file)
        original = path.read_bytes()
        entry = None
        word = ""
        if add_entry:
            word = normalize_selection(str(message.get("text") or ""))
            dictionary_entry = self.dictionary_factory(self.dictionary_path).lookup(word)
            meaning = normalize_ecdict_translation(dictionary_entry.translation)
            if not meaning:
                meaning = self.translator_factory(config.app_id, config.secret_key).translate(word)
            entry = (word, dictionary_entry.phonetic, meaning)
        result = create_section_atomic(path, name, self.backup_root, entry)
        try:
            self.config_store.save(replace(config, selected_section=name))
        except Exception:
            restore_bytes_atomic(path, original)
            raise
        return {
            "ok": True,
            "status": "added" if add_entry else "created",
            "word": word or None,
            "number": result.number,
            "targetLabel": name,
            "message": f"已创建并加入 {name}" if add_entry else f"已创建 {name}",
            **self.config_store.public_settings(),
        }

    def _read_sections(self, path: Path) -> list[str]:
        data = path.read_bytes()
        text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
        return find_sections(text)

    @staticmethod
    def _error(status: str, message: str) -> dict:
        return {"ok": False, "status": status, "message": message}
