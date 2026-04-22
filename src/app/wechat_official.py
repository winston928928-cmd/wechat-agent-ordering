from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET


def verify_signature(*, token: str, timestamp: str, nonce: str, signature: str) -> bool:
    if not token or not timestamp or not nonce or not signature:
        return False
    parts = sorted([token, timestamp, nonce])
    candidate = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    return candidate == signature


def parse_message(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    payload: dict[str, str] = {}
    for child in root:
        payload[child.tag] = child.text or ""
    return payload


def build_text_reply(*, to_user: str, from_user: str, content: str) -> str:
    safe_content = content.replace("]]>", "]]]]><![CDATA[>")
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{safe_content}]]></Content>"
        "</xml>"
    )


def is_text_message(payload: dict) -> bool:
    return payload.get("MsgType") == "text"


def is_subscribe_event(payload: dict) -> bool:
    return payload.get("MsgType") == "event" and payload.get("Event", "").lower() == "subscribe"
