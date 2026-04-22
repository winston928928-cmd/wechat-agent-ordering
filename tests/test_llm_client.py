import unittest

from src.app.llm_client import build_messages, extract_assistant_text
from src.app.session_store import ChatSession


class ExtractAssistantTextTests(unittest.TestCase):
    def test_extracts_string_content(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "你好，我在。",
                    }
                }
            ]
        }

        self.assertEqual(extract_assistant_text(payload), "你好，我在。")

    def test_extracts_list_content(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "第一句"},
                            {"type": "text", "text": "第二句"},
                        ],
                    }
                }
            ]
        }

        self.assertEqual(extract_assistant_text(payload), "第一句\n第二句")


class BuildMessagesTests(unittest.TestCase):
    def test_builds_message_window_with_system_prompt(self) -> None:
        session = ChatSession(
            session_id="s1",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        session.add_turn("user", "你好")
        session.add_turn("assistant", "你好呀")
        session.add_turn("user", "今天有点累")

        messages = build_messages(
            instructions="你是一个陪聊助手。",
            session=session,
            max_turns=2,
            memory_prompt="以下是长期记忆：用户喜欢热汤面。",
        )

        self.assertEqual(messages[0], {"role": "system", "content": "你是一个陪聊助手。"})
        self.assertEqual(messages[1], {"role": "system", "content": "以下是长期记忆：用户喜欢热汤面。"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "你好呀"})
        self.assertEqual(messages[3], {"role": "user", "content": "今天有点累"})


if __name__ == "__main__":
    unittest.main()
