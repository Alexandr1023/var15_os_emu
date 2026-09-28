import subprocess
import sys


def test_cli_script_execution():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.shell_emulator",
            "--vfs",
            "vfs_examples/minimal.xml",
            "--script",
            "scripts/stage1.txt",
            "--no-interactive",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "VFS загружена" in result.stdout
    assert "неизвестная команда" in result.stdout
    assert "неизвестная команда" not in result.stderr
