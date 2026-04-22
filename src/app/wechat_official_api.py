from __future__ import annotations

import json
import time
from pathlib import Path

import requests


class WeChatOfficialApiError(RuntimeError):
    pass


class WeChatOfficialApiClient:
    def __init__(self, *, app_id: str, app_secret: str, cache_path: Path) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._cache_path = cache_path
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._http = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def send_text_message(self, *, open_id: str, content: str) -> None:
        if not self.enabled:
            raise WeChatOfficialApiError("微信公众号主动回复未启用，缺少 AppID 或 AppSecret。")

        payload = {
            "touser": open_id,
            "msgtype": "text",
            "text": {"content": content},
        }

        response = self._http.post(
            self._custom_send_url(self._get_access_token()),
            json=payload,
            timeout=20,
        )
        data = self._decode_json(response)

        if data.get("errcode") in {40001, 42001, 40014}:
            response = self._http.post(
                self._custom_send_url(self._get_access_token(force_refresh=True)),
                json=payload,
                timeout=20,
            )
            data = self._decode_json(response)

        if data.get("errcode", 0) != 0:
            raise WeChatOfficialApiError(f"客服消息发送失败: {data}")

    def _get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            cached = self._read_cache()
            now = time.time()
            if cached and cached.get("access_token") and cached.get("expires_at", 0) - now > 120:
                return cached["access_token"]

        response = self._http.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self._app_id,
                "secret": self._app_secret,
            },
            timeout=20,
        )
        data = self._decode_json(response)
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 0))

        if not access_token or not expires_in:
            raise WeChatOfficialApiError(f"获取 access_token 失败: {data}")

        payload = {
            "access_token": access_token,
            "expires_at": time.time() + expires_in,
        }
        self._cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return access_token

    def _read_cache(self) -> dict:
        if not self._cache_path.exists():
            return {}
        return json.loads(self._cache_path.read_text(encoding="utf-8"))

    @staticmethod
    def _decode_json(response) -> dict:
        try:
            return response.json()
        except ValueError as exc:
            raise WeChatOfficialApiError(f"微信公众号接口返回了非 JSON 内容: {response.text}") from exc

    @staticmethod
    def _custom_send_url(access_token: str) -> str:
        return f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
