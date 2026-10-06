"""Эмулятор оболочки с виртуальной файловой системой в памяти."""

from __future__ import annotations

import argparse
import base64
import hashlib
import shlex
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


COMMAND_ARGUMENT_COUNT = 2
MOVE_ARGUMENT_COUNT = 3
HISTORY_START_NUMBER = 1
ROOT_PATH = "/"
MEMORY_SOURCE = "<память>"


class VfsError(Exception):
    """Ошибка работы с виртуальной файловой системой."""


@dataclass
class Node:
    """Узел каталога или файла VFS."""

    name: str
    is_dir: bool
    content: bytes = b""
    parent: Node | None = None
    children: dict[str, Node] = field(default_factory=dict)


class VirtualFileSystem:
    """Хранит структуру VFS исключительно в памяти."""

    def __init__(self) -> None:
        self.root = Node("", True)

    @classmethod
    def from_xml(cls, path: str) -> VirtualFileSystem:
        """Загружает описание VFS из XML-файла."""
        try:
            root = element_tree.parse(path).getroot()
        except (OSError, element_tree.ParseError) as exc:
            raise VfsError(f"не удалось загрузить VFS: {exc}") from exc
        if root.tag != "vfs":
            raise VfsError("корневой элемент VFS должен быть <vfs>")
        vfs = cls()
        for item in root:
            vfs._load_item(item, vfs.root)
        return vfs

    def _load_item(self, item: element_tree.Element, parent: Node) -> None:
        """Добавляет один XML-элемент и его потомков в VFS."""
        name = self._validate_name(item.get("name"))
        if name in parent.children:
            raise VfsError(f"повторяющееся имя: {name}")
        if item.tag == "directory":
            self._load_directory(item, parent, name)
            return
        if item.tag == "file":
            parent.children[name] = self._file_node(item, parent, name)
            return
        raise VfsError(f"неизвестный элемент VFS: {item.tag}")

    @staticmethod
    def _validate_name(name: str | None) -> str:
        if not name or name in {".", ".."} or "/" in name:
            raise VfsError("некорректное имя узла VFS")
        return name

    def _load_directory(
        self,
        item: element_tree.Element,
        parent: Node,
        name: str,
    ) -> None:
        directory = Node(name, True, parent=parent)
        parent.children[name] = directory
        for child in item:
            self._load_item(child, directory)

    def _file_node(
        self,
        item: element_tree.Element,
        parent: Node,
        name: str,
    ) -> Node:
        encoding = item.get("encoding", "text")
        content = self._decode_content(item.text or "", encoding, name)
        return Node(name, False, content, parent)

    @staticmethod
    def _decode_content(raw: str, encoding: str, name: str) -> bytes:
        if encoding == "text":
            return raw.encode("utf-8")
        if encoding == "base64":
            try:
                return base64.b64decode("".join(raw.split()), validate=True)
            except ValueError as exc:
                message = f"некорректный base64 в файле {name}"
                raise VfsError(message) from exc
        raise VfsError("неподдерживаемая кодировка файла")

    def resolve(self, path: str, cwd: Node) -> Node:
        """Разрешает абсолютный либо относительный путь VFS."""
        current = self.root if path.startswith(ROOT_PATH) else cwd
        for part in PurePosixPath(path).parts:
            current = self._resolve_part(current, part, path)
        return current

    @staticmethod
    def _resolve_part(current: Node, part: str, original_path: str) -> Node:
        if part in {ROOT_PATH, "."}:
            return current
        if part == "..":
            return current.parent or current
        if not current.is_dir or part not in current.children:
            raise VfsError(f"путь не найден: {original_path}")
        return current.children[part]

    def reset(self) -> None:
        """Создаёт пустую VFS в памяти."""
        self.root = Node("", True)


class Shell:
    """Выполняет команды пользователя в загруженной VFS."""

    def __init__(self, vfs: VirtualFileSystem, source: str) -> None:
        self.vfs = vfs
        self.source = source
        self.cwd = vfs.root
        self.history: list[str] = []
        self.commands = {
            "pwd": self._command_pwd,
            "ls": self._command_ls,
            "cd": self._command_cd,
            "cat": self._command_cat,
            "history": self._command_history,
            "mv": self._command_mv,
            "vfs-init": self._command_vfs_init,
            "vfs-info": self._command_vfs_info,
        }

    def _path(self, node: Node) -> str:
        names: list[str] = []
        while node is not self.vfs.root:
            names.append(node.name)
            if node.parent is None:
                raise VfsError("нарушена структура VFS")
            node = node.parent
        return ROOT_PATH + "/".join(reversed(names))

    def run_script(self, path: str) -> None:
        """Исполняет команды TXT-сценария, пропуская комментарии."""
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"ошибка сценария: {exc}")
            return
        for line in lines:
            if not self._is_command_line(line):
                continue
            print(f"$ {line}")
            if not self.execute(line):
                return

    @staticmethod
    def _is_command_line(line: str) -> bool:
        return bool(line.strip()) and not line.lstrip().startswith("#")

    def execute(self, line: str) -> bool:
        """Выполняет команду; False означает завершение REPL."""
        args = self._parse(line)
        if not args:
            return True
        self.history.append(line.strip())
        if args[0] == "exit":
            return False
        handler = self.commands.get(args[0])
        if handler is None:
            print(f"неизвестная команда: {args[0]}")
            return True
        handler(args)
        return True

    @staticmethod
    def _parse(line: str) -> list[str]:
        try:
            return shlex.split(line)
        except ValueError as exc:
            print(f"ошибка разбора: {exc}")
            return []

    def _command_pwd(self, args: list[str]) -> None:
        self._require_count(args, HISTORY_START_NUMBER, "pwd")
        print(self._path(self.cwd))

    def _command_ls(self, args: list[str]) -> None:
        if len(args) > COMMAND_ARGUMENT_COUNT:
            print("ошибка: использование: ls [путь]")
            return
        target = self._target_or_cwd(args)
        if target is None:
            return
        if target.is_dir:
            print("  ".join(sorted(target.children)))
        else:
            print(target.name)

    def _command_cd(self, args: list[str]) -> None:
        if len(args) > COMMAND_ARGUMENT_COUNT:
            print("ошибка: использование: cd [путь]")
            return
        target = self._target_or_root(args)
        if target is None:
            return
        if not target.is_dir:
            print("ошибка: это не каталог")
            return
        self.cwd = target

    def _command_cat(self, args: list[str]) -> None:
        if not self._require_count(args, COMMAND_ARGUMENT_COUNT, "cat <путь>"):
            return
        target = self._resolve(args[HISTORY_START_NUMBER])
        if target is None:
            return
        if target.is_dir:
            print("ошибка: это каталог")
            return
        try:
            print(target.content.decode("utf-8"), end="")
        except UnicodeDecodeError:
            print("ошибка: файл содержит двоичные данные")

    def _command_history(self, args: list[str]) -> None:
        if not self._require_count(args, HISTORY_START_NUMBER, "history"):
            return
        for number, command in enumerate(self.history, HISTORY_START_NUMBER):
            print(f"{number:4}  {command}")

    def _command_mv(self, args: list[str]) -> None:
        usage = "mv <источник> <назначение>"
        if not self._require_count(args, MOVE_ARGUMENT_COUNT, usage):
            return
        source = self._resolve(args[HISTORY_START_NUMBER])
        if source is None:
            return
        try:
            self._move(source, args[COMMAND_ARGUMENT_COUNT])
        except VfsError as exc:
            print(f"ошибка: {exc}")

    def _command_vfs_init(self, args: list[str]) -> None:
        if not self._require_count(args, HISTORY_START_NUMBER, "vfs-init"):
            return
        self.vfs.reset()
        self.cwd = self.vfs.root
        self.source = MEMORY_SOURCE
        print("VFS инициализирована в памяти")

    def _command_vfs_info(self, args: list[str]) -> None:
        if not self._require_count(args, HISTORY_START_NUMBER, "vfs-info"):
            return
        print(f"источник: {self.source}")
        print(f"sha-256: {self._source_digest()}")

    def _source_digest(self) -> str:
        if self.source == MEMORY_SOURCE:
            return "недоступно"
        try:
            return hashlib.sha256(Path(self.source).read_bytes()).hexdigest()
        except OSError as exc:
            return f"ошибка чтения: {exc}"

    def _target_or_cwd(self, args: list[str]) -> Node | None:
        if len(args) == HISTORY_START_NUMBER:
            return self.cwd
        return self._resolve(args[HISTORY_START_NUMBER])

    def _target_or_root(self, args: list[str]) -> Node | None:
        if len(args) == HISTORY_START_NUMBER:
            return self.vfs.root
        return self._resolve(args[HISTORY_START_NUMBER])

    def _resolve(self, path: str) -> Node | None:
        try:
            return self.vfs.resolve(path, self.cwd)
        except VfsError as exc:
            print(f"ошибка: {exc}")
            return None

    @staticmethod
    def _require_count(args: list[str], count: int, usage: str) -> bool:
        if len(args) == count:
            return True
        print(f"ошибка: использование: {usage}")
        return False

    def _move(self, source: Node, destination: str) -> None:
        if source is self.vfs.root:
            raise VfsError("нельзя переместить корень VFS")
        target = self._resolve_destination(destination)
        if target.is_dir:
            self._move_to_directory(source, target)
            return
        self._rename(source, target)

    def _resolve_destination(self, path: str) -> Node:
        try:
            return self.vfs.resolve(path, self.cwd)
        except VfsError:
            return self._new_destination(path)

    def _new_destination(self, path: str) -> Node:
        parent_path, _, name = path.rpartition(ROOT_PATH)
        if not name or name in {".", ".."}:
            raise VfsError("некорректное имя назначения")
        parent = self.vfs.resolve(parent_path or ".", self.cwd)
        if not parent.is_dir:
            raise VfsError("родитель назначения не является каталогом")
        if name in parent.children:
            raise VfsError("объект назначения уже существует")
        return Node(name, False, parent=parent)

    def _move_to_directory(self, source: Node, destination: Node) -> None:
        self._ensure_not_descendant(destination, source)
        if source.name in destination.children:
            message = "в каталоге назначения уже есть объект с таким именем"
            raise VfsError(message)
        self._reparent(source, destination)

    @staticmethod
    def _ensure_not_descendant(destination: Node, source: Node) -> None:
        current: Node | None = destination
        while current is not None:
            if current is source:
                raise VfsError("нельзя переместить каталог внутрь самого себя")
            current = current.parent

    def _rename(self, source: Node, destination: Node) -> None:
        parent = destination.parent
        if parent is None:
            raise VfsError("некорректное назначение")
        source_parent = source.parent
        if source_parent is None:
            raise VfsError("нельзя переместить корень VFS")
        del source_parent.children[source.name]
        source.name = destination.name
        source.parent = parent
        parent.children[source.name] = source

    @staticmethod
    def _reparent(source: Node, destination: Node) -> None:
        if source.parent is None:
            raise VfsError("нельзя переместить корень VFS")
        del source.parent.children[source.name]
        source.parent = destination
        destination.children[source.name] = source


def build_parser() -> argparse.ArgumentParser:
    """Создаёт обработчик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Эмулятор UNIX-подобной оболочки",
    )
    parser.add_argument(
        "--vfs",
        required=True,
        help="XML-файл виртуальной файловой системы",
    )
    parser.add_argument("--script", help="TXT-сценарий стартовых команд")
    parser.add_argument("--no-interactive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Загружает VFS, выполняет сценарий и запускает REPL."""
    args = build_parser().parse_args(argv)
    try:
        shell = Shell(VirtualFileSystem.from_xml(args.vfs), args.vfs)
    except VfsError as exc:
        print(f"ошибка: {exc}")
        return HISTORY_START_NUMBER
    print(f"VFS загружена: {args.vfs}")
    if args.script:
        shell.run_script(args.script)
    if not args.no_interactive:
        run_repl(shell)
    return 0


def run_repl(shell: Shell) -> None:
    """Выполняет интерактивный цикл без завершения программы по ошибке."""
    while True:
        try:
            if not shell.execute(input("vfs:/$ ")):
                return
        except (EOFError, KeyboardInterrupt):
            print()
            return


if __name__ == "__main__":
    raise SystemExit(main())
