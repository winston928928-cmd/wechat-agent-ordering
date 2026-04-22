import tempfile
import unittest
from pathlib import Path

from src.app.persona_prompt import PERSONA_HEADER, build_agent_instructions


class PersonaPromptTests(unittest.TestCase):
    def test_builds_without_private_persona(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.md"
            base.write_text("base prompt", encoding="utf-8")

            content, loaded = build_agent_instructions(
                base_prompt_path=base,
                persona_prompt_path=root / "missing.md",
            )

            self.assertEqual(content, "base prompt")
            self.assertFalse(loaded)

    def test_builds_with_private_persona(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.md"
            persona = root / "persona.md"
            base.write_text("base prompt", encoding="utf-8")
            persona.write_text("persona prompt", encoding="utf-8")

            content, loaded = build_agent_instructions(
                base_prompt_path=base,
                persona_prompt_path=persona,
            )

            self.assertTrue(loaded)
            self.assertIn("base prompt", content)
            self.assertIn(PERSONA_HEADER, content)
            self.assertIn("persona prompt", content)


if __name__ == "__main__":
    unittest.main()
