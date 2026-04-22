from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROVIDER = "dashscope"
DEFAULT_PROVIDER_BASE_URLS = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com",
}
DEFAULT_PROVIDER_MODELS = {
    "dashscope": "qwen-plus",
    "deepseek": "deepseek-chat",
}


@dataclass(slots=True)
class AppConfig:
    project_root: Path
    llm_provider: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str
    llm_history_turns: int
    agent_host: str
    agent_port: int
    agent_name: str
    session_dir: Path
    memory_path: Path
    channel_binding_path: Path
    wechat_official_token_cache_path: Path
    prompt_path: Path
    static_dir: Path
    wechat_official_token: str
    wechat_official_path: str
    wechat_official_app_id: str
    wechat_official_app_secret: str
    wechat_official_reply_mode: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        project_root = Path(__file__).resolve().parents[2]
        session_dir = project_root / "data" / "sessions"
        memory_path = project_root / "data" / "memory" / "profile.json"
        channel_binding_path = project_root / "data" / "channels" / "bindings.json"
        wechat_official_token_cache_path = project_root / "data" / "channels" / "wechat_official_token.json"
        prompt_path = project_root / "prompts" / "chat_agent.md"
        static_dir = project_root / "static"
        llm_provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
        llm_base_url = (os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_PROVIDER_BASE_URLS.get(llm_provider, "")).rstrip("/")
        llm_model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_PROVIDER_MODELS.get(llm_provider, "qwen-plus")

        return cls(
            project_root=project_root,
            llm_provider=llm_provider,
            llm_api_key=resolve_api_key(llm_provider),
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            llm_history_turns=int(os.getenv("LLM_HISTORY_TURNS", "24")),
            agent_host=os.getenv("AGENT_HOST", "127.0.0.1").strip(),
            agent_port=int(os.getenv("AGENT_PORT", "8787")),
            agent_name=os.getenv("AGENT_NAME", "陪伴型助手").strip(),
            session_dir=session_dir,
            memory_path=memory_path,
            channel_binding_path=channel_binding_path,
            wechat_official_token_cache_path=wechat_official_token_cache_path,
            prompt_path=prompt_path,
            static_dir=static_dir,
            wechat_official_token=os.getenv("WECHAT_OFFICIAL_TOKEN", "").strip(),
            wechat_official_path=os.getenv("WECHAT_OFFICIAL_PATH", "/wechat/official/callback").strip()
            or "/wechat/official/callback",
            wechat_official_app_id=os.getenv("WECHAT_OFFICIAL_APP_ID", "").strip(),
            wechat_official_app_secret=os.getenv("WECHAT_OFFICIAL_APP_SECRET", "").strip(),
            wechat_official_reply_mode=normalize_wechat_reply_mode(
                os.getenv("WECHAT_OFFICIAL_REPLY_MODE", "passive")
            ),
        )


def resolve_api_key(provider: str) -> str:
    explicit = os.getenv("LLM_API_KEY", "").strip()
    if explicit:
        return explicit

    provider_key_env = {
        "dashscope": "DASHSCOPE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }.get(provider)

    if provider_key_env:
        return os.getenv(provider_key_env, "").strip()

    return ""


def normalize_wechat_reply_mode(value: str) -> str:
    mode = value.strip().lower()
    return mode if mode in {"passive", "active"} else "passive"
