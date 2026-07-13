from __future__ import annotations

import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable


class YoudaoTranslateError(RuntimeError):
    pass


def _request_json(url: str, payload: dict[str, str], timeout: float) -> dict:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise YoudaoTranslateError("有道文本翻译网络请求失败") from error


class YoudaoTranslator:
    ENDPOINT = "https://openapi.youdao.com/api"

    def __init__(
        self,
        app_key: str,
        secret_key: str,
        requester: Callable[[str, dict[str, str], float], dict] = _request_json,
        salt_factory: Callable[[], str] = lambda: secrets.token_hex(8),
        time_factory: Callable[[], int] = lambda: int(time.time()),
    ):
        self._app_key = app_key
        self._secret_key = secret_key
        self._requester = requester
        self._salt_factory = salt_factory
        self._time_factory = time_factory

    def translate(self, text: str) -> str:
        salt = self._salt_factory()
        current_time = str(self._time_factory())
        signature_source = (
            f"{self._app_key}{_sign_input(text)}{salt}{current_time}{self._secret_key}"
        )
        payload = {
            "q": text,
            "from": "en",
            "to": "zh-CHS",
            "appKey": self._app_key,
            "salt": salt,
            "sign": hashlib.sha256(signature_source.encode("utf-8")).hexdigest(),
            "signType": "v3",
            "curtime": current_time,
        }
        response = self._requester(self.ENDPOINT, payload, 10.0)
        code = str(response.get("errorCode", "0"))
        if code not in {"0", ""}:
            raise YoudaoTranslateError(f"有道文本翻译错误 {code}")
        translations = [
            str(item).strip() for item in response.get("translation") or [] if str(item).strip()
        ]
        if not translations:
            raise YoudaoTranslateError("有道文本翻译未返回结果")
        return "；".join(translations)


def _sign_input(text: str) -> str:
    return text if len(text) <= 20 else f"{text[:10]}{len(text)}{text[-10:]}"
