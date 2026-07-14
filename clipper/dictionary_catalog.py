from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CatalogPack:
    id: str
    name: str
    filename: str
    source: dict[str, object]


def load_catalog(path: Path) -> tuple[CatalogPack, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("packs"), list):
        raise ValueError("词典清单版本不兼容")
    packs = []
    for value in payload["packs"]:
        pack_id = str(value.get("id") or "").strip()
        filename = str(value.get("filename") or "").strip()
        if not pack_id or Path(filename).name != filename or not filename.endswith(".sqlite3"):
            raise ValueError("词典清单包含无效条目")
        packs.append(CatalogPack(pack_id, str(value.get("name") or pack_id), filename, value))
    if len({pack.id for pack in packs}) != len(packs):
        raise ValueError("词典清单包含重复标识")
    return tuple(packs)
