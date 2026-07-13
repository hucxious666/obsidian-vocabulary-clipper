from __future__ import annotations

from pathlib import Path
from typing import Callable

from .dictionary import DictionaryLookup, LookupNotFound
from .dictionary_catalog import CatalogPack, load_catalog
from .dictionary_schema import PackValidationError, validate_pack


class DictionaryRepository:
    def __init__(
        self,
        dictionary_root: Path,
        catalog_path: Path,
        lookup_factory: Callable[[Path], DictionaryLookup] = DictionaryLookup,
    ):
        self.dictionary_root = Path(dictionary_root)
        self.packs = load_catalog(catalog_path)
        self.lookup_factory = lookup_factory

    def list_packs(self) -> list[dict[str, object]]:
        return [
            {"id": pack.id, "name": pack.name, "installed": self._is_installed(pack)}
            for pack in self.packs
        ]

    def lookup(self, pack_id: str, word: str):
        path = self.require_installed(pack_id)
        return self.lookup_factory(path).lookup(word)

    def require_installed(self, pack_id: str) -> Path:
        pack = self._find(pack_id)
        path = self.dictionary_root / pack.filename
        try:
            validate_pack(path, pack.id)
        except PackValidationError as error:
            raise LookupNotFound(str(error)) from error
        return path

    def _find(self, pack_id: str) -> CatalogPack:
        match = next((pack for pack in self.packs if pack.id == pack_id), None)
        if match is None:
            raise LookupNotFound("未知的离线词典")
        return match

    def _is_installed(self, pack: CatalogPack) -> bool:
        try:
            validate_pack(self.dictionary_root / pack.filename, pack.id)
            return True
        except PackValidationError:
            return False
