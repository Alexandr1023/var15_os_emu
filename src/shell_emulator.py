"""REPL, параметры запуска и стартовые сценарии."""

from __future__ import annotations

import argparse
import getpass
import json
import shlex
import socket
from pathlib import Path


class Shell:
    def __init__(self) -> None:
        self.running = True

    def prompt(self) -> str:
        return f"{getpass.getuser()}@{socket.gethostname()}:/$ "

    def execute(self, line: str) -> bool:
        try:
            args = shlex.split(line)
        except ValueError as exc:
            print(f"ошибка разбора команды: {exc}")
            return True
        if not args:
            return True
        if args[0] == "exit":
            self.running = False
            return False
        print(f"неизвестная команда: {args[0]}")
        return True

    def run_script(self, path: str) -> None:
        try:
            for line in Path(path).read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                print(f"$ {line}")
                if not self.execute(line):
                    break
        except OSError as exc:
            print(f"ошибка чтения стартового сценария: {exc}")

    def repl(self) -> None:
        while self.running:
            try:
                self.execute(input(self.prompt()))
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Эмулятор UNIX-подобной оболочки")
    parser.add_argument("--config", default="config.json", help="путь к JSON-конфигурации")
    parser.add_argument("--script", help="путь к стартовому TXT-сценарию")
    parser.add_argument("--no-interactive", action="store_true", help="не запускать REPL")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ошибка конфигурации: {exc}")
        return 1
    shell = Shell()
    script = args.script or config.get("startup_script")
    if script:
        shell.run_script(script)
    if not args.no_interactive and shell.running:
        shell.repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
