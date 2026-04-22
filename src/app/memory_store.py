from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .session_store import utc_now_iso


NAME_PATTERNS = [
    re.compile(r"(?:我叫|叫我|你可以叫我)([A-Za-z0-9\u4e00-\u9fa5·]{1,20})"),
]
IDENTITY_PATTERNS = [
    re.compile(r"我是(?:一名|一个|做)?([^，。！？,.!?]{1,20})"),
    re.compile(r"我现在是([^，。！？,.!?]{1,20})"),
]
LOCATION_PATTERNS = [
    re.compile(r"我在([^，。！？,.!?]{1,20})"),
    re.compile(r"我住在([^，。！？,.!?]{1,20})"),
]
LIKE_PATTERNS = [
    re.compile(r"(?:我喜欢|我爱|我爱吃|我平时喜欢)([^，。！？,.!?]{1,30})"),
]
DISLIKE_PATTERNS = [
    re.compile(r"(?:我不喜欢|我讨厌|我不吃|我不爱吃)([^，。！？,.!?]{1,30})"),
    re.compile(r"(?:也不喜欢|也不吃|也不爱吃)([^，。！？,.!?]{1,30})"),
]
IDENTITY_STOP_WORDS = ("想", "要", "会", "在", "得", "也", "就", "不是", "不会", "准备", "有点")
SPLIT_PATTERN = re.compile(r"[、，,和及]+")


@dataclass(slots=True)
class UserMemory:
    preferred_name: str = ""
    identities: list[str] = field(default_factory=list)
    likes: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    custom_notes: list[str] = field(default_factory=list)
    last_updated_at: str = ""

    def touch(self) -> None:
        self.last_updated_at = utc_now_iso()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserMemory":
        return cls(
            preferred_name=data.get("preferred_name", ""),
            identities=list(data.get("identities", [])),
            likes=list(data.get("likes", [])),
            dislikes=list(data.get("dislikes", [])),
            locations=list(data.get("locations", [])),
            custom_notes=list(data.get("custom_notes", [])),
            last_updated_at=data.get("last_updated_at", ""),
        )


class MemoryStore:
    def __init__(self, memory_path: Path) -> None:
        self._default_path = memory_path
        self._profiles_dir = memory_path.parent / "profiles"
        self._default_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    def get(self, memory_id: str = "default") -> UserMemory:
        path = self._path_for(memory_id)
        if not path.exists():
            return UserMemory()
        return UserMemory.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, memory: UserMemory, *, memory_id: str = "default") -> None:
        path = self._path_for(memory_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(memory.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_from_text(self, text: str, *, memory_id: str = "default") -> UserMemory:
        memory = self.get(memory_id)
        changed = False

        preferred_name = first_match(NAME_PATTERNS, text)
        if preferred_name and preferred_name != memory.preferred_name:
            memory.preferred_name = preferred_name
            changed = True

        changed |= merge_unique(memory.identities, extract_identity(text))
        changed |= merge_unique(memory.locations, extract_values(LOCATION_PATTERNS, text))
        changed |= merge_unique(memory.likes, extract_values(LIKE_PATTERNS, text))
        changed |= merge_unique(memory.dislikes, extract_values(DISLIKE_PATTERNS, text))

        if changed:
            memory.touch()
            self.save(memory, memory_id=memory_id)
        return memory

    def replace(self, payload: dict, *, memory_id: str = "default") -> UserMemory:
        memory = UserMemory(
            preferred_name=str(payload.get("preferred_name", "")).strip(),
            identities=normalize_items(payload.get("identities")),
            likes=normalize_items(payload.get("likes")),
            dislikes=normalize_items(payload.get("dislikes")),
            locations=normalize_items(payload.get("locations")),
            custom_notes=normalize_items(payload.get("custom_notes")),
            last_updated_at=utc_now_iso(),
        )
        self.save(memory, memory_id=memory_id)
        return memory

    def resolve_memory_id(self, memory_id: str | None) -> str:
        normalized = (memory_id or "").strip()
        return normalized or "default"

    def _path_for(self, memory_id: str) -> Path:
        normalized = self.resolve_memory_id(memory_id)
        if normalized == "default":
            return self._default_path

        safe_memory_id = (
            normalized.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace(" ", "_")
        )
        return self._profiles_dir / f"{safe_memory_id}.json"


def render_memory_prompt(memory: UserMemory) -> str:
    lines: list[str] = []
    if memory.preferred_name:
        lines.append(f"- 用户偏好称呼：{memory.preferred_name}")
    if memory.identities:
        lines.append(f"- 用户身份/角色：{', '.join(memory.identities)}")
    if memory.locations:
        lines.append(f"- 用户地点线索：{', '.join(memory.locations)}")
    if memory.likes:
        lines.append(f"- 用户偏好：{', '.join(memory.likes)}")
    if memory.dislikes:
        lines.append(f"- 用户不喜欢/忌口：{', '.join(memory.dislikes)}")
    if memory.custom_notes:
        lines.append(f"- 额外备注：{'; '.join(memory.custom_notes)}")

    if not lines:
        return ""

    return "\n".join(
        [
            "以下是该用户的长期记忆，请只在相关时自然使用，不要每次都机械重复：",
            *lines,
        ]
    )


def first_match(patterns: list[re.Pattern[str]], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return clean_fragment(match.group(1))
    return ""


def extract_identity(text: str) -> list[str]:
    values = extract_values(IDENTITY_PATTERNS, text)
    result: list[str] = []
    for value in values:
        if value.startswith(IDENTITY_STOP_WORDS):
            continue
        result.append(value)
    return result


def extract_values(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    values: list[str] = []
    for pattern in patterns:
        for match in pattern.findall(text):
            values.extend(split_values(clean_fragment(match)))
    return dedupe(values)


def split_values(text: str) -> list[str]:
    return [clean_fragment(part) for part in SPLIT_PATTERN.split(text) if clean_fragment(part)]


def clean_fragment(text: str) -> str:
    return text.strip().strip("，。,.!?！？；;:： ")


def normalize_items(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return dedupe(clean_fragment(str(item)) for item in value if clean_fragment(str(item)))
    if isinstance(value, str):
        parts = [segment for chunk in value.splitlines() for segment in SPLIT_PATTERN.split(chunk)]
        return dedupe(clean_fragment(part) for part in parts if clean_fragment(part))
    return []


def merge_unique(target: list[str], incoming: list[str]) -> bool:
    changed = False
    for item in incoming:
        if item and item not in target:
            target.append(item)
            changed = True
    return changed


def dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
