"""Эмулятор оболочки с файловой системой, существующей только в памяти."""
from __future__ import annotations
import argparse
import base64
import hashlib
import shlex
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import PurePosixPath


class VfsError(Exception): pass

@dataclass
class Node:
    name: str
    is_dir: bool
    content: bytes = b""
    parent: "Node | None" = None
    children: dict[str, "Node"] = field(default_factory=dict)

class VirtualFileSystem:
    def __init__(self): self.root = Node("", True)
    @classmethod
    def from_xml(cls, path: str):
        vfs = cls()
        try: root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc: raise VfsError(f"не удалось загрузить VFS: {exc}") from exc
        if root.tag != "vfs": raise VfsError("корневой элемент VFS должен быть <vfs>")
        for item in root: vfs._load(item, vfs.root)
        return vfs
    def _load(self, item, parent):
        name = item.get("name")
        if not name or name in {".", ".."} or "/" in name: raise VfsError("некорректное имя узла VFS")
        if name in parent.children: raise VfsError(f"повторящееся имя: {name}")
        if item.tag == "directory":
            node = Node(name, True, parent=parent); parent.children[name] = node
            for child in item: self._load(child, node)
        elif item.tag == "file":
            raw = item.text or ""; encoding = item.get("encoding", "text")
            try: data = base64.b64decode("".join(raw.split()), validate=True) if encoding == "base64" else raw.encode()
            except ValueError as exc: raise VfsError(f"некорректный base64 в файле {name}") from exc
            if encoding not in {"text", "base64"}: raise VfsError("неподдерживаемая кодировка файла")
            parent.children[name] = Node(name, False, data, parent)
        else: raise VfsError(f"неизвестный элемент VFS: {item.tag}")
    def resolve(self, path: str, cwd: Node):
        current = self.root if path.startswith("/") else cwd
        for part in PurePosixPath(path).parts:
            if part in {"/", "."}: continue
            if part == "..": current = current.parent or current; continue
            if not current.is_dir or part not in current.children: raise VfsError(f"путь не найден: {path}")
            current = current.children[part]
        return current
    def reset(self): self.root = Node("", True)

class Shell:
    def __init__(self, vfs, source): self.vfs, self.source, self.cwd = vfs, source, vfs.root
    def execute(self, line):
        try: args = shlex.split(line)
        except ValueError as exc: print(f"ошибка разбора: {exc}"); return True
        if not args or args[0].startswith("#"): return True
        if args[0] == "exit": return False
        if args[0] == "vfs-init": self.vfs.reset(); self.cwd = self.vfs.root; self.source = "<память>"; print("VFS инициализирована в памяти"); return True
        if args[0] == "vfs-info":
            digest = "недоступно" if self.source == "<память>" else hashlib.sha256(open(self.source,"rb").read()).hexdigest()
            print(f"источник: {self.source}\nsha-256: {digest}"); return True
        print(f"неизвестная команда: {args[0]}"); return True

def main(argv=None):
    parser = argparse.ArgumentParser(description="Эмулятор UNIX-подобной оболочки")
    parser.add_argument("--vfs", required=True, help="XML-файл виртуальной файловой системы")
    parser.add_argument("--no-interactive", action="store_true")
    args = parser.parse_args(argv)
    try: shell = Shell(VirtualFileSystem.from_xml(args.vfs), args.vfs)
    except VfsError as exc: print(f"ошибка: {exc}"); return 1
    if not args.no_interactive:
        while True:
            try:
                if not shell.execute(input("vfs:/$ ")): break
            except (EOFError, KeyboardInterrupt): break
    return 0

if __name__ == "__main__": raise SystemExit(main())
