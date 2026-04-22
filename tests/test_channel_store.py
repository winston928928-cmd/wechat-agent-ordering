import tempfile
import unittest
from pathlib import Path

from src.app.channel_store import ChannelBindingStore


class ChannelBindingStoreTests(unittest.TestCase):
    def test_sets_and_gets_session_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ChannelBindingStore(Path(temp_dir) / "bindings.json")
            store.set_session_id("wechat_official", "user_1", "session_1")

            self.assertEqual(store.get_session_id("wechat_official", "user_1"), "session_1")
            self.assertIsNone(store.get_session_id("wechat_official", "user_2"))


if __name__ == "__main__":
    unittest.main()
