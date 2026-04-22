from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import AppConfig
from .memory_store import UserMemory, render_memory_prompt
from .session_store import ChatSession


class LLMClientError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class ChatResult:
    assistant_text: str
    response_id: str
    model: str
    usage: dict | None


class ChatCompletionsClient:
    def __init__(self, config: AppConfig, instructions: str) -> None:
        self._config = config
        self._instructions = instructions
        self._http = requests.Session()

    def chat(self, session: ChatSession, memory: UserMemory | None = None) -> ChatResult:
        if not self._config.llm_api_key:
            raise LLMClientError(
                "缺少 LLM API Key。当前默认支持阿里云百炼（DASHSCOPE_API_KEY）或 DeepSeek（DEEPSEEK_API_KEY）。",
                status_code=503,
            )

        if not self._config.llm_base_url:
            raise LLMClientError("缺少 LLM_BASE_URL，当前无法发起模型请求。", status_code=503)

        payload = {
            "model": self._config.llm_model,
            "messages": build_messages(
                instructions=self._instructions,
                session=session,
                max_turns=self._config.llm_history_turns,
                memory_prompt=render_memory_prompt(memory or UserMemory()),
            ),
            "stream": False,
        }

        response = self._http.post(
            f"{self._config.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._config.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {"message": response.text}
            raise LLMClientError(f"模型请求失败: {error_payload}", status_code=response.status_code)

        data = response.json()
        assistant_text = extract_assistant_text(data)
        if not assistant_text:
            raise LLMClientError("模型返回成功，但没有解析到文本回复。", status_code=502)

        return ChatResult(
            assistant_text=assistant_text,
            response_id=data.get("id", ""),
            model=data.get("model", self._config.llm_model),
            usage=data.get("usage"),
        )


def build_messages(*, instructions: str, session: ChatSession, max_turns: int, memory_prompt: str = "") -> list[dict]:
    history = session.turns[-max_turns:] if max_turns > 0 else session.turns
    messages = [{"role": "system", "content": instructions}]
    if memory_prompt:
        messages.append({"role": "system", "content": memory_prompt})
    messages.extend({"role": turn.role, "content": turn.text} for turn in history)
    return messages


def extract_assistant_text(data: dict) -> str:
    choices = data.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    return ""
