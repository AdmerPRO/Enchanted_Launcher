from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import minecraft_launcher_lib as mc


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", project_root()))
    return base / relative_path


@dataclass(frozen=True)
class LauncherPaths:
    root: Path
    minecraft: Path
    config: Path
    mods: Path
    temp_mods: Path
    logs: Path
    icon: Path

    @classmethod
    def create(cls) -> "LauncherPaths":
        root = project_root()
        mods = root / "mods"
        return cls(
            root=root,
            minecraft=Path(mc.utils.get_minecraft_directory()),
            config=root / "launcher_config.json",
            mods=mods,
            temp_mods=mods / "temp-mods",
            logs=root / "logs",
            icon=bundled_path("assets/icon.ico"),
        )

    def ensure_runtime_dirs(self, versions: tuple[str, ...]) -> None:
        self.mods.mkdir(exist_ok=True)
        self.temp_mods.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)
        for version in versions:
            (self.mods / f"fabric-{version}").mkdir(exist_ok=True)
