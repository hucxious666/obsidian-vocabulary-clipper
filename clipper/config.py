from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .markdown_writer import find_chapters


class SettingsValidationError(ValueError):
    pass


class Protector(Protocol):
    def protect(self, value: str) -> str: ...
    def unprotect(self, value: str) -> str: ...


@dataclass(frozen=True)
class AppConfig:
    chapter_file: str
    news_file: str
    selected_chapter: int
    app_id: str
    secret_key: str
    youdao_app_key: str = ""
    youdao_secret_key: str = ""


class ConfigStore:
    def __init__(self, path: Path, protector: Protector):
        self.path = Path(path)
        self.protector = protector

    def validate_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute() or path.suffix.casefold() != ".md" or not path.is_file():
            raise SettingsValidationError("请选择现有的 Markdown 文件")
        return path.resolve()

    def _chapters(self, path: Path) -> list[int]:
        try:
            data = path.read_bytes()
            text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
        except UnicodeError as error:
            raise SettingsValidationError("Markdown 文件必须使用 UTF-8 编码") from error
        return find_chapters(text)

    def save(self, config: AppConfig) -> None:
        chapter_file = self.validate_path(config.chapter_file)
        news_file = self.validate_path(config.news_file)
        chapters = self._chapters(chapter_file)
        if int(config.selected_chapter) not in chapters:
            raise SettingsValidationError("所选 Chapter 不存在")
        if not config.app_id.strip() or not config.secret_key.strip():
            raise SettingsValidationError("百度 APP ID 和密钥不能为空")
        if bool(config.youdao_app_key.strip()) != bool(config.youdao_secret_key.strip()):
            raise SettingsValidationError("有道 App Key 和 App Secret 必须同时填写")
        payload = {
            "chapter_file": str(chapter_file),
            "news_file": str(news_file),
            "selected_chapter": int(config.selected_chapter),
            "credentials": {
                "id": self.protector.protect(config.app_id.strip()),
                "key": self.protector.protect(config.secret_key.strip()),
            },
        }
        if config.youdao_app_key.strip():
            payload["youdao_credentials"] = {
                "id": self.protector.protect(config.youdao_app_key.strip()),
                "key": self.protector.protect(config.youdao_secret_key.strip()),
            }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> AppConfig:
        if not self.path.is_file():
            raise SettingsValidationError("请先完成扩展设置")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        credentials = payload.get("credentials") or {}
        youdao_credentials = payload.get("youdao_credentials") or {}
        return AppConfig(
            chapter_file=str(self.validate_path(payload.get("chapter_file", ""))),
            news_file=str(self.validate_path(payload.get("news_file", ""))),
            selected_chapter=int(payload.get("selected_chapter", 0)),
            app_id=self.protector.unprotect(credentials.get("id", "")),
            secret_key=self.protector.unprotect(credentials.get("key", "")),
            youdao_app_key=self._unprotect_optional(youdao_credentials.get("id", "")),
            youdao_secret_key=self._unprotect_optional(youdao_credentials.get("key", "")),
        )

    def public_settings(self) -> dict:
        config = self.load()
        chapter_path = Path(config.chapter_file)
        chapters = self._chapters(chapter_path)
        return {
            "chapterFile": config.chapter_file,
            "newsFile": config.news_file,
            "selectedChapter": config.selected_chapter,
            "chapters": chapters,
            "credentialsConfigured": bool(config.app_id and config.secret_key),
            "youdaoCredentialsConfigured": bool(
                config.youdao_app_key and config.youdao_secret_key
            ),
        }

    def _unprotect_optional(self, value: str) -> str:
        return self.protector.unprotect(value) if value else ""
