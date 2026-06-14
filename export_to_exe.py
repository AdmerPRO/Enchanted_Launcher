from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "EnchantedLauncher"


def build_command(project_root: Path, app_name: str) -> list[str]:
    assets_dir = project_root / "assets"
    icon = assets_dir / "icon.ico"
    data_separator = ";" if sys.platform.startswith("win") else ":"
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        app_name,
        "--icon",
        str(icon),
        "--add-data",
        f"{assets_dir}{data_separator}assets",
        "--collect-all",
        "customtkinter",
        "--distpath",
        str(project_root / "dist"),
        "--workpath",
        str(project_root / "build" / "pyinstaller"),
        "--specpath",
        str(project_root / "build"),
        str(project_root / "main.py"),
    ]


def ensure_ready(project_root: Path) -> None:
    assets_dir = project_root / "assets"
    icon = assets_dir / "icon.ico"
    steve_skin = assets_dir / "steve_skin.png"
    if not icon.exists():
        raise SystemExit(f"Missing icon: {icon}")
    if not steve_skin.exists():
        raise SystemExit(f"Missing Steve skin: {steve_skin}")
    if shutil.which("pyinstaller") is None:
        try:
            subprocess.run(
                [sys.executable, "-m", "PyInstaller", "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise SystemExit(
                "PyInstaller is not installed. Run: python -m pip install -r requirements.txt"
            ) from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Enchanted Launcher as a Windows EXE.")
    parser.add_argument("--name", default=APP_NAME, help="Executable name without extension.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    ensure_ready(project_root)

    command = build_command(project_root, args.name)
    print("Building EXE with PyInstaller...")
    subprocess.check_call(command, cwd=project_root)

    exe_suffix = ".exe" if sys.platform.startswith("win") else ""
    output = project_root / "dist" / f"{args.name}{exe_suffix}"
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
