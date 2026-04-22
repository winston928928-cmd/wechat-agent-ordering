from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .channel_store import ChannelBindingStore
from .config import AppConfig
from .llm_client import ChatCompletionsClient, LLMClientError
from .memory_store import MemoryStore, render_memory_prompt
from .persona_prompt import build_agent_instructions
from .session_store import SessionStore
from .wechat_official import build_text_reply, is_subscribe_event, is_text_message, parse_message, verify_signature
from .wechat_official_api import WeChatOfficialApiClient, WeChatOfficialApiError


class AgentApplication:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.store = SessionStore(config.session_dir)
        self.memory_store = MemoryStore(config.memory_path)
        self.channel_bindings = ChannelBindingStore(config.channel_binding_path)
        self.instructions, self.persona_prompt_loaded = build_agent_instructions(
            base_prompt_path=config.prompt_path,
            persona_prompt_path=config.persona_prompt_path,
        )
        self.client = ChatCompletionsClient(config, self.instructions)
        self.wechat_official_api = WeChatOfficialApiClient(
            app_id=config.wechat_official_app_id,
            app_secret=config.wechat_official_app_secret,
            cache_path=config.wechat_official_token_cache_path,
        )
        self.index_html = (config.static_dir / "index.html").read_text(encoding="utf-8")
        self.admin_html = (config.static_dir / "admin.html").read_text(encoding="utf-8")

    @property
    def wechat_official_active_reply_enabled(self) -> bool:
        return self.config.wechat_official_reply_mode == "active" and self.wechat_official_api.enabled

    def handle_chat(self, *, message: str, session_id: str | None, memory_id: str | None = None) -> dict:
        session = self.store.get_or_create(session_id, memory_id=memory_id)
        memory_id = session.memory_id or self.memory_store.resolve_memory_id(memory_id)
        session.memory_id = memory_id
        session.add_turn("user", message)
        self.store.save(session)
        memory = self.memory_store.update_from_text(message, memory_id=memory_id)

        result = self.client.chat(session, memory=memory)
        session.latest_response_id = result.response_id
        session.add_turn("assistant", result.assistant_text)
        self.store.save(session)

        return {
            "session": session,
            "memory": memory,
            "result": result,
        }

    def handle_wechat_official_text(self, *, open_id: str, message: str) -> dict:
        session_id = self.channel_bindings.get_session_id("wechat_official", open_id)
        handled = self.handle_chat(
            message=message,
            session_id=session_id,
            memory_id=f"wechat_official:{open_id}",
        )
        session = handled["session"]
        self.channel_bindings.set_session_id("wechat_official", open_id, session.session_id)
        return handled

    def enqueue_wechat_official_reply(self, *, open_id: str, message: str) -> None:
        worker = threading.Thread(
            target=self._process_wechat_official_reply,
            kwargs={"open_id": open_id, "message": message},
            daemon=True,
        )
        worker.start()

    def _process_wechat_official_reply(self, *, open_id: str, message: str) -> None:
        reply_text = ""
        try:
            handled = self.handle_wechat_official_text(open_id=open_id, message=message)
            reply_text = handled["result"].assistant_text.strip()
        except LLMClientError as exc:
            print(f"[wechat_official] model request failed for {open_id}: {exc}")
            reply_text = "我刚刚有点忙，稍后你再发我一句，我继续接着聊。"
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[wechat_official] unexpected processing error for {open_id}: {exc}")
            reply_text = "我这边刚刚出了点小状况，你再发我一句，我们继续。"

        if not reply_text:
            reply_text = "我收到了，你再给我一点点时间，我马上接住你。"

        try:
            self.wechat_official_api.send_text_message(open_id=open_id, content=reply_text[:600])
            print(f"[wechat_official] active reply sent to {open_id}", flush=True)
        except WeChatOfficialApiError as exc:
            print(f"[wechat_official] active reply failed for {open_id}: {exc}", flush=True)


class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "WeChatAgentOrdering/0.1"

    @property
    def app(self) -> AgentApplication:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._write_html(self.app.index_html)
            return

        if parsed.path in {"/admin", "/admin.html"}:
            self._write_html(self.app.admin_html)
            return

        if parsed.path == self.app.config.wechat_official_path:
            query = parse_qs(parsed.query)
            signature = query.get("signature", [""])[0]
            timestamp = query.get("timestamp", [""])[0]
            nonce = query.get("nonce", [""])[0]
            echostr = query.get("echostr", [""])[0]

            if verify_signature(
                token=self.app.config.wechat_official_token,
                timestamp=timestamp,
                nonce=nonce,
                signature=signature,
            ):
                self._write_plain_text(HTTPStatus.OK, echostr)
                return

            self._write_plain_text(HTTPStatus.FORBIDDEN, "invalid signature")
            return

        if parsed.path == "/api/health":
            default_memory = self.app.memory_store.get("default")
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "agent_name": self.app.config.agent_name,
                    "provider": self.app.config.llm_provider,
                    "model": self.app.config.llm_model,
                    "api_key_configured": bool(self.app.config.llm_api_key),
                    "memory_enabled": True,
                    "memory_summary_available": bool(render_memory_prompt(default_memory)),
                    "persona_prompt_loaded": self.app.persona_prompt_loaded,
                    "wechat_official_configured": bool(self.app.config.wechat_official_token),
                    "wechat_official_active_reply_enabled": self.app.wechat_official_active_reply_enabled,
                    "wechat_official_reply_mode": self.app.config.wechat_official_reply_mode,
                    "wechat_official_path": self.app.config.wechat_official_path,
                },
            )
            return

        if parsed.path == "/api/admin/sessions":
            query = parse_qs(parsed.query).get("q", [""])[0]
            limit_text = parse_qs(parsed.query).get("limit", ["50"])[0]
            try:
                limit = max(1, min(200, int(limit_text)))
            except ValueError:
                limit = 50
            self._write_json(
                HTTPStatus.OK,
                {
                    "query": query,
                    "sessions": self.app.store.list_summaries(query=query, limit=limit),
                },
            )
            return

        if parsed.path == "/api/admin/memory":
            memory_id = self.app.memory_store.resolve_memory_id(parse_qs(parsed.query).get("memory_id", ["default"])[0])
            self._write_json(
                HTTPStatus.OK,
                {
                    "memory_id": memory_id,
                    "memory": self.app.memory_store.get(memory_id).to_dict(),
                },
            )
            return

        if parsed.path == "/api/admin/channel-bindings":
            channel_name = parse_qs(parsed.query).get("channel", [""])[0]
            self._write_json(
                HTTPStatus.OK,
                {
                    "channel": channel_name,
                    "bindings": self.app.channel_bindings.list_bindings(channel_name),
                },
            )
            return

        if parsed.path.startswith("/api/sessions/"):
            session_id = parsed.path.removeprefix("/api/sessions/").strip()
            session = self.app.store.get(session_id)
            if not session:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "session_not_found"})
                return
            self._write_json(HTTPStatus.OK, session.to_dict())
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/sessions":
            session = self.app.store.create()
            self._write_json(HTTPStatus.CREATED, session.to_dict())
            return

        if parsed.path == "/api/chat":
            body = self._read_json_body()
            message = (body.get("message") or "").strip()
            session_id = (body.get("session_id") or "").strip() or None
            memory_id = (body.get("memory_id") or "").strip() or None

            if not message:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "message_required"})
                return

            try:
                handled = self.app.handle_chat(message=message, session_id=session_id, memory_id=memory_id)
            except LLMClientError as exc:
                self._write_json(
                    exc.status_code,
                    {"error": "llm_request_failed", "message": str(exc), "session_id": session_id},
                )
                return

            session = handled["session"]
            memory = handled["memory"]
            result = handled["result"]

            self._write_json(
                HTTPStatus.OK,
                {
                    "session_id": session.session_id,
                    "memory_id": session.memory_id,
                    "assistant_message": result.assistant_text,
                    "response_id": result.response_id,
                    "model": result.model,
                    "usage": result.usage,
                    "turns": [asdict(turn) for turn in session.turns],
                    "memory": memory.to_dict(),
                },
            )
            return

        if parsed.path == "/api/admin/memory":
            body = self._read_json_body()
            memory_id = self.app.memory_store.resolve_memory_id(parse_qs(parsed.query).get("memory_id", ["default"])[0])
            self._write_json(
                HTTPStatus.OK,
                {
                    "memory_id": memory_id,
                    "memory": self.app.memory_store.replace(body, memory_id=memory_id).to_dict(),
                },
            )
            return

        if parsed.path == self.app.config.wechat_official_path:
            raw_body = self._read_text_body()
            query = parse_qs(parsed.query)
            signature = query.get("signature", [""])[0]
            timestamp = query.get("timestamp", [""])[0]
            nonce = query.get("nonce", [""])[0]

            if not verify_signature(
                token=self.app.config.wechat_official_token,
                timestamp=timestamp,
                nonce=nonce,
                signature=signature,
            ):
                self._write_plain_text(HTTPStatus.FORBIDDEN, "invalid signature")
                return

            try:
                payload = parse_message(raw_body)
            except Exception:
                self._write_plain_text(HTTPStatus.BAD_REQUEST, "invalid xml")
                return

            from_user = payload.get("FromUserName", "")
            to_user = payload.get("ToUserName", "")

            if not from_user or not to_user:
                self._write_plain_text(HTTPStatus.BAD_REQUEST, "missing user info")
                return

            if is_subscribe_event(payload):
                reply = build_text_reply(
                    to_user=from_user,
                    from_user=to_user,
                    content="你好，我在。直接给我发文字消息，我们就可以开始聊。",
                )
                self._write_xml(HTTPStatus.OK, reply)
                return

            if not is_text_message(payload):
                reply = build_text_reply(
                    to_user=from_user,
                    from_user=to_user,
                    content="当前这版先只支持文字消息，你直接发文字给我就行。",
                )
                self._write_xml(HTTPStatus.OK, reply)
                return

            user_message = payload.get("Content", "").strip()
            if not user_message:
                reply = build_text_reply(
                    to_user=from_user,
                    from_user=to_user,
                    content="我收到了空消息，重新发一句文字给我就好。",
                )
                self._write_xml(HTTPStatus.OK, reply)
                return

            print(f"[wechat_official] incoming text from {from_user}: {user_message[:80]!r}", flush=True)

            if self.app.wechat_official_active_reply_enabled:
                self.app.enqueue_wechat_official_reply(open_id=from_user, message=user_message)
                self._write_plain_text(HTTPStatus.OK, "success")
                return

            try:
                handled = self.app.handle_wechat_official_text(open_id=from_user, message=user_message)
            except LLMClientError:
                reply = build_text_reply(
                    to_user=from_user,
                    from_user=to_user,
                    content="我这边刚刚有点忙，稍后你再发我一句，我继续接着聊。",
                )
                self._write_xml(HTTPStatus.OK, reply)
                return

            reply = build_text_reply(
                to_user=from_user,
                from_user=to_user,
                content=handled["result"].assistant_text[:600],
            )
            print(f"[wechat_official] passive reply ready for {from_user}", flush=True)
            self._write_xml(HTTPStatus.OK, reply)
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json_body(self) -> dict:
        raw = self._read_raw_body(default=b"{}")
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _read_text_body(self) -> str:
        return self._read_raw_body(default=b"").decode("utf-8", errors="ignore")

    def _read_raw_body(self, default: bytes = b"") -> bytes:
        content_length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(content_length) if content_length > 0 else default

    def _write_json(self, status: HTTPStatus | int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_plain_text(self, status: HTTPStatus | int, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_xml(self, status: HTTPStatus | int, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    config = AppConfig.from_env()
    config.static_dir.mkdir(parents=True, exist_ok=True)
    config.session_dir.mkdir(parents=True, exist_ok=True)
    config.memory_path.parent.mkdir(parents=True, exist_ok=True)

    if not config.prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {config.prompt_path}")

    app = AgentApplication(config)
    server = ThreadingHTTPServer((config.agent_host, config.agent_port), AgentRequestHandler)
    server.app = app  # type: ignore[attr-defined]

    print(f"Agent running at http://{config.agent_host}:{config.agent_port}")
    print(f"Provider: {config.llm_provider}")
    print(f"Model: {config.llm_model}")
    print(f"LLM key configured: {bool(config.llm_api_key)}")
    print(f"Admin UI: http://{config.agent_host}:{config.agent_port}/admin")
    print(f"Persona prompt loaded: {app.persona_prompt_loaded}", flush=True)
    print(f"WeChat official callback path: {config.wechat_official_path}")
    print(f"WeChat official reply mode: {config.wechat_official_reply_mode}", flush=True)
    print(f"WeChat official active reply enabled: {app.wechat_official_active_reply_enabled}", flush=True)
    server.serve_forever()
