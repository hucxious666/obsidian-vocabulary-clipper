from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .markdown_writer import find_sections, normalize_section_name


class SettingsValidationError(ValueError):
    pass


class Protector(Protocol):
    def protect(self, value: str) -> str: ...
    def unprotect(self, value: str) -> str: ...


@dataclass(frozen=True)
class AppConfig:
    section_file: str
    append_file: str
    selected_section: str
    app_id: str
    secret_key: str
    youdao_app_key: str = ""
    youdao_secret_key: str = ""

    def __post_init__(self) -> None:
        selected = (
            f"Chapter {int(self.selected_section)}"
            if isinstance(self.selected_section, int)
            else normalize_section_name(self.selected_section)
        )
        object.__setattr__(self, "selected_section", selected)

    @property
    def chapter_file(self) -> str:
        return self.section_file

    @property
    def news_file(self) -> str:
        return self.append_file

    @property
    def selected_chapter(self) -> int:
        prefix = "Chapter "
        return int(self.selected_section[len(prefix):]) if self.selected_section.startswith(prefix) else 0


class ConfigStore:
    def __init__(self, path: Path, protector: Protector):
        self.path = Path(path)
        self.protector = protector

    def validate_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute() or path.suffix.casefold() != ".md" or not path.is_file():
            raise SettingsValidationError("请选择现有的 Markdown 文件")
        return path.resolve()

    def _sections(self, path: Path) -> list[str]:
        try:
            data = path.read_bytes()
            text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8")
        except UnicodeError as error:
            raise SettingsValidationError("Markdown 文件必须使用 UTF-8 编码") from error
        return find_sections(text)

    def _chapters(self, path: Path) -> list[int]:
        return [
            int(name.removeprefix("Chapter "))
            for name in self._sections(path)
            if name.startswith("Chapter ") and name.removeprefix("Chapter ").isdigit()
        ]

    def save(self, config: AppConfig) -> None:
        section_file = self.validate_path(config.section_file)
        append_file = self.validate_path(config.append_file)
        sections = self._sections(section_file)
        selected = next(
            (name for name in sections if name.casefold() == config.selected_section.casefold()),
            None,
        )
        if selected is None:
            raise SettingsValidationError("所选章节不存在")
        if not config.app_id.strip() or not config.secret_key.strip():
            raise SettingsValidationError("百度 APP ID 和密钥不能为空")
        if bool(config.youdao_app_key.strip()) != bool(config.youdao_secret_key.strip()):
            raise SettingsValidationError("有道 App Key 和 App Secret 必须同时填写")
        payload = {
            "section_file": str(section_file),
            "append_file": str(append_file),
            "selected_section": selected,
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
        selected = payload.get("selected_section")
        if not selected:
            selected = f"Chapter {int(payload.get('selected_chapter', 0))}"
        return AppConfig(
            section_file=str(
                self.validate_path(payload.get("section_file") or payload.get("chapter_file", ""))
            ),
            append_file=str(
                self.validate_path(payload.get("append_file") or payload.get("news_file", ""))
            ),
            selected_section=str(selected),
            app_id=self.protector.unprotect(credentials.get("id", "")),
            secret_key=self.protector.unprotect(credentials.get("key", "")),
            youdao_app_key=self._unprotect_optional(youdao_credentials.get("id", "")),
            youdao_secret_key=self._unprotect_optional(youdao_credentials.get("key", "")),
        )

    def public_settings(self) -> dict:
        config = self.load()
        section_path = Path(config.section_file)
        sections = self._sections(section_path)
        return {
            "sectionFile": config.section_file,
            "appendFile": config.append_file,
            "selectedSection": config.selected_section,
            "sections": sections,
            "chapterFile": config.section_file,
            "newsFile": config.append_file,
            "selectedChapter": config.selected_chapter,
            "chapters": self._chapters(section_path),
            "credentialsConfigured": bool(config.app_id and config.secret_key),
            "youdaoCredentialsConfigured": bool(
                config.youdao_app_key and config.youdao_secret_key
            ),
        }

    def _unprotect_optional(self, value: str) -> str:
        return self.protector.unprotect(value) if value else ""
