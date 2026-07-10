from __future__ import annotations

import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass


class YoudaoDictionaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class YoudaoDictionaryResult:
    word: str
    phonetic: str
    explains: list[str]


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
        raise YoudaoDictionaryError("有道词典网络请求失败") from error


class YoudaoDictionaryClient:
    ENDPOINT = "https://openapi.youdao.com/v2/dict"

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

    def lookup(self, word: str) -> YoudaoDictionaryResult:
        salt = self._salt_factory()
        current_time = str(self._time_factory())
        signature_source = f"{self._app_key}{_sign_input(word)}{salt}{current_time}{self._secret_key}"
        payload = {
            "q": word,
            "langType": "en",
            "appKey": self._app_key,
            "salt": salt,
            "sign": hashlib.sha256(signature_source.encode("utf-8")).hexdigest(),
            "signType": "v3",
            "curtime": current_time,
            "dicts": "ec",
            "docType": "json",
        }
        response = self._requester(self.ENDPOINT, payload, 10.0)
        self._raise_for_error(response)
        basic = _find_basic(response)
        explains = [str(item).strip() for item in basic.get("explains") or [] if str(item).strip()]
        phonetic = _first_value(
            basic, "us-phonetic", "usPhonetic", "phonetic", "uk-phonetic", "ukPhonetic"
        )
        if not explains:
            raise YoudaoDictionaryError("有道词典未返回完整释义")
        return YoudaoDictionaryResult(word, phonetic, explains)

    @staticmethod
    def _raise_for_error(response: dict) -> None:
        code = str(response.get("errorCode", "0"))
        if code in {"0", ""}:
            return
        if code == "110":
            raise YoudaoDictionaryError("有道应用未开通有道词典服务（错误 110）")
        raise YoudaoDictionaryError(f"有道词典错误 {code}")


def _sign_input(text: str) -> str:
    return text if len(text) <= 20 else f"{text[:10]}{len(text)}{text[-10:]}"


def _first_value(values: dict, *keys: str) -> str:
    for key in keys:
        value = str(values.get(key) or "").strip().strip("/")
        if value:
            return value
    return ""


def _find_basic(response: dict) -> dict:
    direct = response.get("basic")
    if isinstance(direct, dict):
        return direct
    results = response.get("result") or []
    if isinstance(results, dict):
        results = [results]
    for result in results:
        if not isinstance(result, dict):
            continue
        nested = result.get("basic")
        if isinstance(nested, dict):
            return nested
        for dictionary in result.values():
            if isinstance(dictionary, dict) and isinstance(dictionary.get("basic"), dict):
                return dictionary["basic"]
    return {}
