from __future__ import annotations

from typing import Callable

from .config import AppConfig
from .selection import normalize_translation_selection
from .translator import BaiduTranslateError
from .youdao import YoudaoTranslateError


def preview_youdao(
    text: str,
    config: AppConfig,
    youdao_factory: Callable,
) -> dict:
    normalized = normalize_translation_selection(text)
    if not config.youdao_app_key or not config.youdao_secret_key:
        raise ValueError("请先保存有道 App Key 和 App Secret")
    translated = youdao_factory(
        config.youdao_app_key, config.youdao_secret_key
    ).translate(normalized)
    return {
        "ok": True,
        "status": "ok",
        "message": "有道文本翻译成功（结果仅预览，不会写入）",
        "preview": {
            "sourceText": normalized,
            "translatedText": translated,
            "source": "youdao",
        },
    }


def translate_selection(
    text: str,
    config: AppConfig,
    translator_factory: Callable,
    youdao_factory: Callable,
) -> dict:
    normalized = normalize_translation_selection(text)
    source = "baidu"
    try:
        translated = translator_factory(config.app_id, config.secret_key).translate(normalized)
    except BaiduTranslateError as baidu_error:
        if not config.youdao_app_key or not config.youdao_secret_key:
            raise BaiduTranslateError(f"{baidu_error}；未配置有道翻译后备") from baidu_error
        try:
            translated = youdao_factory(
                config.youdao_app_key, config.youdao_secret_key
            ).translate(normalized)
        except YoudaoTranslateError as youdao_error:
            raise YoudaoTranslateError(
                f"百度和有道翻译均失败：{baidu_error}；{youdao_error}"
            ) from youdao_error
        source = "youdao"
    return {
        "ok": True,
        "status": "ok",
        "translation": {
            "sourceText": normalized,
            "translatedText": translated,
            "source": source,
        },
    }
