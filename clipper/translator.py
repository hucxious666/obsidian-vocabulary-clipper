from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable


class BaiduTranslateError(RuntimeError):
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
        raise BaiduTranslateError("百度翻译网络请求失败") from error


class BaiduTranslator:
    ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"

    def __init__(
        self,
        app_id: str,
        secret_key: str,
        requester: Callable[[str, dict[str, str], float], dict] = _request_json,
        salt_factory: Callable[[], str] = lambda: secrets.token_hex(8),
    ):
        self._app_id = app_id
        self._secret_key = secret_key
        self._requester = requester
        self._salt_factory = salt_factory

    def translate(self, text: str) -> str:
        salt = self._salt_factory()
        signature = hashlib.md5(
            f"{self._app_id}{text}{salt}{self._secret_key}".encode("utf-8")
        ).hexdigest()
        payload = {
            "q": text,
            "from": "en",
            "to": "zh",
            "appid": self._app_id,
            "salt": salt,
            "sign": signature,
        }
        response = self._requester(self.ENDPOINT, payload, 10.0)
        if "error_code" in response:
            raise BaiduTranslateError(f"百度翻译错误 {response.get('error_code', 'unknown')}")
        results = response.get("trans_result") or []
        translations = [str(item.get("dst", "")).strip() for item in results if item.get("dst")]
        if not translations:
            raise BaiduTranslateError("百度翻译未返回释义")
        return "；".join(translations)

