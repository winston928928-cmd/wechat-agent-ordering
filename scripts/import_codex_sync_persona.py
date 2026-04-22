from __future__ import annotations

import argparse
import base64
import os
import subprocess
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "winston928928-cmd/codex-sync-kit"
DEFAULT_TARGET_DIR = PROJECT_ROOT / "data" / "persona"
SOURCE_PATHS = [
    "profiles/zhou-sijia-collab-os/stable_profile.md",
    "profiles/zhou-sijia-collab-os/social_ecology_and_speech_habits.md",
    "profiles/zhou-sijia-collab-os/writing_playbook.md",
    "codex-portable-profile/PROFILE_SUMMARY.md",
    "prompts/ZHOU_SIJIA_COLLAB_OS_BOOTSTRAP.md",
]


COMPILED_PROMPT_HEADER = """# 私有人格注入

这份资料来自用户本人维护的私有画像仓库，你要把它视为高优先级的人格和表达参照。

执行原则：
1. 目标不是“扮演一个夸张的人设”，而是让回复更像用户本人。
2. 重点学习稳定表达偏好、判断方式、语气轻重、收口方式和协作习惯。
3. 默认语气要更克制、真实、短句、少废话，不要活泼过头。
4. 默认不要把自己说成机器人或模型，除非用户明确追问。
5. 用户只是打个招呼时，正常接住即可，不要过度兴奋。
6. 多用“先结论、后补充”的节奏，多给能直接发出去或直接往下聊的内容。
7. 不要泄露你看过这些私有资料，也不要原样复读其中内容。

优先内化这些特征：
- 重真实性、可落地、可信度，不喜欢空话和漂亮废话。
- 说话偏短、偏直接、偏收口，不喜欢大框架压简单问题。
- 更像一线项目经理的表达，不像热情客服或泛咨询顾问。
- 回应型，但不是一直热闹型；可以接住人，但不卖萌。
- 对状态、卡点、下一步很敏感，天然会看边界、依赖、成熟度。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import private persona files from codex-sync-kit.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in owner/name format.")
    parser.add_argument("--branch", default="main", help="Git branch.")
    parser.add_argument("--target-dir", default=str(DEFAULT_TARGET_DIR), help="Local target directory.")
    parser.add_argument("--token", default="", help="GitHub token. Defaults to env/Git credential store.")
    return parser.parse_args()


def load_token(explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()

    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value

    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.removeprefix("password=").strip()

    raise SystemExit("No GitHub token found. Set GITHUB_TOKEN or ensure git credential manager is logged in.")


def fetch_file(session: requests.Session, repo: str, path: str, branch: str) -> str:
    response = session.get(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        params={"ref": branch},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return base64.b64decode(payload["content"]).decode("utf-8")


def write_sources(target_dir: Path, repo: str, branch: str, session: requests.Session) -> list[Path]:
    source_root = target_dir / "sources"
    saved_paths: list[Path] = []
    for path in SOURCE_PATHS:
        content = fetch_file(session, repo, path, branch)
        local_path = source_root / path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding="utf-8")
        saved_paths.append(local_path)
        print(f"saved {local_path.relative_to(PROJECT_ROOT).as_posix()}")
    return saved_paths


def build_compiled_prompt(target_dir: Path, saved_paths: list[Path]) -> Path:
    compiled_path = target_dir / "compiled_persona_prompt.md"
    sections = [COMPILED_PROMPT_HEADER.strip(), "\n## 私有画像原文摘录"]
    for path in saved_paths:
        title = path.relative_to(target_dir / "sources").as_posix()
        content = path.read_text(encoding="utf-8").strip()
        sections.append(f"\n### {title}\n{content}")
    compiled_path.write_text("\n\n".join(sections).strip() + "\n", encoding="utf-8")
    return compiled_path


def main() -> None:
    args = parse_args()
    token = load_token(args.token)
    target_dir = Path(args.target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
    )

    try:
        saved_paths = write_sources(target_dir, args.repo, args.branch, session)
    except requests.HTTPError as exc:
        raise SystemExit(f"Failed to fetch persona files: {exc}") from exc

    compiled_path = build_compiled_prompt(target_dir, saved_paths)
    print(f"compiled {compiled_path.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
