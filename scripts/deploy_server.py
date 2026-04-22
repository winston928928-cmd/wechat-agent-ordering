from __future__ import annotations

import argparse
import os
import posixpath
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REMOTE_ROOT = "/opt/wechat-agent-ordering"
DEFAULT_SERVICE_NAME = "wechat-agent.service"
DEFAULT_PASSWORD_ENV = "WECHAT_AGENT_SERVER_PASSWORD"
DEFAULT_STATUS_COMMANDS = [
    "systemctl is-active {service}",
    "curl -s http://127.0.0.1:8787/api/health",
    "ss -tlnp | grep -E ':80\\s|:8787\\s' || true",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="同步项目到云服务器并管理服务。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", required=True, help="服务器公网 IP 或域名")
    common.add_argument("--user", default="root", help="SSH 用户名，默认 root")
    common.add_argument("--password", default="", help="SSH 密码，不推荐直接写在命令里")
    common.add_argument(
        "--password-env",
        default=DEFAULT_PASSWORD_ENV,
        help=f"从环境变量读取 SSH 密码，默认 {DEFAULT_PASSWORD_ENV}",
    )
    common.add_argument("--port", type=int, default=22, help="SSH 端口，默认 22")
    common.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT, help="服务器项目目录")
    common.add_argument("--service-name", default=DEFAULT_SERVICE_NAME, help="systemd 服务名")

    sync_parser = subparsers.add_parser("sync", parents=[common], help="同步已跟踪文件并重启服务")
    sync_parser.add_argument("--skip-restart", action="store_true", help="同步后不重启服务")
    sync_parser.add_argument("--chown-user", default="wechatagent", help="同步后执行 chown 的用户")
    sync_parser.add_argument("--chown-group", default="wechatagent", help="同步后执行 chown 的组")

    subparsers.add_parser("status", parents=[common], help="查看服务器服务状态")
    return parser.parse_args()


def load_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    password = os.getenv(args.password_env, "").strip()
    if password:
        return password
    raise SystemExit(
        f"缺少 SSH 密码。可以用 --password 传入，或先设置环境变量 {args.password_env}。"
    )


def import_paramiko():
    try:
        import paramiko  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit("缺少 paramiko。先执行: python -m pip install paramiko") from exc
    return paramiko


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [PROJECT_ROOT / line for line in result.stdout.splitlines() if line.strip()]


def ensure_remote_dirs(sftp, remote_root: str, rel_path: Path) -> None:
    remote_parent = posixpath.dirname(posixpath.join(remote_root, *rel_path.parts))
    stack: list[str] = []
    while remote_parent and remote_parent not in ("", "/"):
        stack.append(remote_parent)
        remote_parent = posixpath.dirname(remote_parent)
    for directory in reversed(stack):
        try:
            sftp.mkdir(directory)
        except OSError:
            pass


def upload_files(sftp, remote_root: str) -> None:
    for file_path in tracked_files():
        rel_path = file_path.relative_to(PROJECT_ROOT)
        remote_path = posixpath.join(remote_root, *rel_path.parts)
        ensure_remote_dirs(sftp, remote_root, rel_path)
        sftp.put(str(file_path), remote_path)
        print(f"uploaded {rel_path.as_posix()}")


def exec_remote(client, command: str, *, timeout: int = 120) -> tuple[str, str, int]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out_text = stdout.read().decode("utf-8", errors="ignore")
    err_text = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    return out_text, err_text, code


def connect(args: argparse.Namespace):
    paramiko = import_paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=args.host,
        port=args.port,
        username=args.user,
        password=load_password(args),
        timeout=15,
        banner_timeout=15,
        auth_timeout=15,
    )
    return client


def run_sync(args: argparse.Namespace) -> None:
    client = connect(args)
    try:
        sftp = client.open_sftp()
        try:
            for directory in [
                args.remote_root,
                f"{args.remote_root}/data",
                f"{args.remote_root}/data/sessions",
                f"{args.remote_root}/data/memory",
                f"{args.remote_root}/data/channels",
            ]:
                try:
                    sftp.mkdir(directory)
                except OSError:
                    pass
            upload_files(sftp, args.remote_root)
        finally:
            sftp.close()

        chown_cmd = (
            f"chown -R {args.chown_user}:{args.chown_group} {args.remote_root}"
            if args.chown_user and args.chown_group
            else "true"
        )
        out_text, err_text, code = exec_remote(client, chown_cmd, timeout=120)
        if code != 0:
            raise SystemExit(f"远程 chown 失败:\n{out_text}{err_text}")

        if not args.skip_restart:
            restart_cmd = f"systemctl restart {args.service_name} && systemctl is-active {args.service_name}"
            out_text, err_text, code = exec_remote(client, restart_cmd, timeout=120)
            if code != 0:
                raise SystemExit(f"远程重启服务失败:\n{out_text}{err_text}")
            print(out_text.strip())
    finally:
        client.close()


def run_status(args: argparse.Namespace) -> None:
    client = connect(args)
    try:
        for command in DEFAULT_STATUS_COMMANDS:
            command = command.format(service=args.service_name)
            out_text, err_text, code = exec_remote(client, command, timeout=120)
            print(f"=== {command} ===")
            print(out_text.strip() or "<no stdout>")
            if err_text.strip():
                print("--- STDERR ---")
                print(err_text.strip())
            if code != 0 and "grep -E" not in command:
                print(f"[exit_code={code}]")
    finally:
        client.close()


def main() -> None:
    args = parse_args()
    if args.command == "sync":
        run_sync(args)
        return
    if args.command == "status":
        run_status(args)
        return
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
