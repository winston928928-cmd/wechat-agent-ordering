import tempfile
import unittest
from pathlib import Path

from src.app.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_save_and_reload_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir))
            session = store.create(memory_id="wechat_official:user_1")
            session.add_turn("user", "你好")
            session.add_turn("assistant", "你好呀")
            session.latest_response_id = "resp_123"
            store.save(session)

            loaded = store.get(session.session_id)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.session_id, session.session_id)
            self.assertEqual(loaded.memory_id, "wechat_official:user_1")
            self.assertEqual(loaded.latest_response_id, "resp_123")
            self.assertEqual(len(loaded.turns), 2)
            self.assertEqual(loaded.turns[0].text, "你好")
            self.assertEqual(loaded.turns[1].text, "你好呀")

    def test_get_or_create_backfills_memory_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir))
            session = store.create(memory_id="")

            loaded = store.get_or_create(session.session_id, memory_id="session:fixed")

            self.assertEqual(loaded.memory_id, "session:fixed")

    def test_lists_and_filters_session_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(Path(temp_dir))

            session_a = store.create(memory_id="session:a")
            session_a.add_turn("user", "今天有点累")
            session_a.add_turn("assistant", "抱抱你")
            store.save(session_a)

            session_b = store.create(memory_id="wechat_official:user_b")
            session_b.add_turn("user", "想吃热汤面")
            store.save(session_b)

            summaries = store.list_summaries(query="热汤面", limit=10)

            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["session_id"], session_b.session_id)
            self.assertEqual(summaries[0]["memory_id"], "wechat_official:user_b")
            self.assertEqual(summaries[0]["last_user_text"], "想吃热汤面")


if __name__ == "__main__":
    unittest.main()
