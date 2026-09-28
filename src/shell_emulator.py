"""Базовый REPL эмулятора UNIX-подобной оболочки."""

from __future__ import annotations

import getpass
import shlex
import socket


class Shell:
    """Разбирает и выполняет базовые команды оболочки."""

    def __init__(self) -> None:
        self.running = True

    def prompt(self) -> str:
        """Возвращает приглашение в UNIX-подобном виде."""
        return f"{getpass.getuser()}@{socket.gethostname()}:/$ "

    def parse(self, line: str) -> list[str]:
        """Разбирает строку команды с поддержкой кавычек."""
        try:
            return shlex.split(line)
        except ValueError as exc:
            print(f"ошибка разбора команды: {exc}")
            return []

    def execute(self, line: str) -> bool:
        """Выполняет одну команду и сообщает, нужно ли продолжать REPL."""
        args = self.parse(line)
        if not args:
            return self.running
        if args[0] == "exit":
            if len(args) != 1:
                print("ошибка: команда exit не принимает аргументы")
                return True
            self.running = False
            return False
        print(f"неизвестная команда: {args[0]}")
        return True

    def repl(self) -> None:
        """Запускает интерактивный цикл чтения и выполнения команд."""
        while self.running:
            try:
                line = input(self.prompt())
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            self.execute(line)


def main() -> int:
    Shell().repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
