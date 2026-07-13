from __future__ import annotations

import html


MEANING_STYLES = frozenset({"covered", "plain"})


def normalize_meaning_style(value: object = None) -> str:
    style = str(value or "covered")
    if style not in MEANING_STYLES:
        raise ValueError("释义写入方式无效")
    return style


def format_entry(
    number: int,
    word: str,
    *,
    phonetic: str,
    meaning: str,
    meaning_style: str = "covered",
) -> str:
    clean_phonetic = phonetic.strip().strip("/").strip()
    clean_meaning = " ".join(meaning.split())
    escaped_meaning = html.escape(clean_meaning, quote=False)
    rendered_meaning = (
        escaped_meaning
        if normalize_meaning_style(meaning_style) == "plain"
        else f'<span class="meaning">{escaped_meaning}</span>'
    )
    return (
        f"{number}. {html.escape(word, quote=False)} /{html.escape(clean_phonetic, quote=False)}/: "
        f"{rendered_meaning}"
    )


def added_response(
    word: str,
    number: int,
    label: str,
    *,
    meaning_style: str,
    created: bool = False,
) -> dict:
    style = normalize_meaning_style(meaning_style)
    if created:
        message = f"已创建并{'以明文' if style == 'plain' else ''}加入 {label}"
    else:
        message = f"已{'以明文' if style == 'plain' else ''}加入 {label}"
    return {
        "ok": True,
        "status": "added",
        "word": word,
        "number": number,
        "targetLabel": label,
        "meaningStyle": style,
        "message": message,
    }
