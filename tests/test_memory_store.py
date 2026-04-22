import tempfile
import unittest
from pathlib import Path

from src.app.memory_store import MemoryStore, UserMemory, render_memory_prompt


class MemoryStoreTests(unittest.TestCase):
    def test_extracts_basic_memory_from_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MemoryStore(Path(temp_dir) / "profile.json")
            memory = store.update_from_text("你可以叫我小周，我喜欢热汤面，也不吃太甜的，我在上海。")

            self.assertEqual(memory.preferred_name, "小周")
            self.assertIn("热汤面", memory.likes)
            self.assertIn("太甜的", memory.dislikes)
            self.assertIn("上海", memory.locations)

    def test_replace_manual_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MemoryStore(Path(temp_dir) / "profile.json")
            memory = store.replace(
                {
                    "preferred_name": "小周",
                    "identities": ["项目经理"],
                    "likes": ["热汤面"],
                    "custom_notes": ["先陪聊，再给建议"],
                }
            )

            self.assertEqual(memory.preferred_name, "小周")
            self.assertEqual(memory.identities, ["项目经理"])
            self.assertEqual(memory.custom_notes, ["先陪聊，再给建议"])

    def test_renders_memory_prompt(self) -> None:
        memory = UserMemory(
            preferred_name="小周",
            likes=["热汤面"],
            custom_notes=["最近压力大时先陪聊"],
        )

        prompt = render_memory_prompt(memory)

        self.assertIn("用户偏好称呼：小周", prompt)
        self.assertIn("用户偏好：热汤面", prompt)
        self.assertIn("额外备注：最近压力大时先陪聊", prompt)


if __name__ == "__main__":
    unittest.main()
