from __future__ import annotations

import json
from pathlib import Path


class ChannelBindingStore:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    def get_session_id(self, channel_name: str, user_id: str) -> str | None:
        data = self._read()
        return data.get(channel_name, {}).get(user_id)

    def set_session_id(self, channel_name: str, user_id: str, session_id: str) -> None:
        data = self._read()
        channel_map = data.setdefault(channel_name, {})
        channel_map[user_id] = session_id
        self._write(data)

    def list_bindings(self, channel_name: str = "") -> dict:
        data = self._read()
        if channel_name:
            return data.get(channel_name, {})
        return data

    def _read(self) -> dict:
        if not self._storage_path.exists():
            return {}
        return json.loads(self._storage_path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self._storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
