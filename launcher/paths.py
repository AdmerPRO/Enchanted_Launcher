from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


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
    profiles: Path
    mods: Path
    temp_mods: Path
    logs: Path
    cache: Path
    modrinth_icons: Path
    icon: Path
    steve_skin: Path

    @classmethod
    def create(cls) -> "LauncherPaths":
        root = project_root()
        mods = root / "mods"
        return cls(
            root=root,
            minecraft=root / ".minecraft",
            config=root / "launcher_config.json",
            profiles=root / "profiles",
            mods=mods,
            temp_mods=mods / "temp-mods",
            logs=root / "logs",
            cache=root / "cache",
            modrinth_icons=root / "cache" / "modrinth-icons",
            icon=bundled_path("assets/icon.ico"),
            steve_skin=bundled_path("assets/steve_skin.png"),
        )

    def ensure_runtime_dirs(self, _versions: tuple[str, ...]) -> None:
        self.minecraft.mkdir(exist_ok=True)
        self.profiles.mkdir(exist_ok=True)
        self.mods.mkdir(exist_ok=True)
        self.temp_mods.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)
        self.cache.mkdir(exist_ok=True)
        self.modrinth_icons.mkdir(exist_ok=True)
