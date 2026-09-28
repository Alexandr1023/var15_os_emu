import base64

import pytest

from src.shell_emulator import Shell, VfsError, VirtualFileSystem


@pytest.fixture()
def shell(tmp_path):
    xml = tmp_path / "vfs.xml"
    xml.write_text(
        """<vfs name="test">
        <directory name="home">
          <directory name="user">
            <file name="hello.txt" encoding="base64">SGVsbG8hCg==</file>
          </directory>
        </directory>
        <directory name="tmp" />
        </vfs>""",
        encoding="utf-8",
    )
    return Shell(VirtualFileSystem.from_xml(str(xml)), str(xml))


def test_loads_base64_file(shell, capsys):
    shell.execute("cat /home/user/hello.txt")
    assert capsys.readouterr().out == "Hello!\n"


def test_cd_and_pwd(shell, capsys):
    shell.execute("cd /home/user")
    shell.execute("pwd")
    assert capsys.readouterr().out == "/home/user\n"


def test_history_records_commands(shell, capsys):
    shell.execute("pwd")
    shell.execute("history")
    output = capsys.readouterr().out
    assert "pwd" in output
    assert "history" in output


def test_mv_rename(shell, capsys):
    shell.execute("mv /home/user/hello.txt /home/user/renamed.txt")
    shell.execute("ls /home/user")
    assert capsys.readouterr().out.strip() == "renamed.txt"


def test_mv_into_directory(shell, capsys):
    shell.execute("mv /home/user/hello.txt /tmp")
    shell.execute("ls /tmp")
    assert capsys.readouterr().out.strip() == "hello.txt"


def test_vfs_init_resets_memory(shell, capsys):
    shell.execute("vfs-init")
    shell.execute("ls")
    assert capsys.readouterr().out == "VFS инициализирована в памяти\n\n"


def test_unknown_command(shell, capsys):
    shell.execute("does-not-exist")
    assert "неизвестная команда" in capsys.readouterr().out


def test_invalid_path_raises_from_vfs(shell):
    with pytest.raises(VfsError):
        shell.vfs.resolve("/missing", shell.cwd)


def test_binary_decoder():
    assert base64.b64decode("SGVsbG8=") == b"Hello"


def test_mv_directory_and_invalid_destination(shell, capsys):
    shell.execute("cd /home/user")
    shell.execute("mv /home/user /tmp")
    shell.execute("pwd")
    assert capsys.readouterr().out == "/tmp/user\n"
    shell.execute("mv /tmp /tmp/user")
    assert "нельзя переместить каталог" in capsys.readouterr().out
