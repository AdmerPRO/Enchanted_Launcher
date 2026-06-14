from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


MOD_SUFFIXES = (".jar", ".mrpack")
DISABLED_SUFFIX = ".disabled"
TEMP_PREFIX = "tmp_el_"
LOCKED_PREFIX = "locked_el-"


@dataclass(frozen=True)
class ModEntry:
    name: str
    path: Path
    enabled: bool
    locked: bool


def version_mod_dir(mods_root: Path, version: str) -> Path:
    path = mods_root / f"fabric-{version}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_mod_file(path: Path) -> bool:
    name = path.name.lower()
    disabled_suffixes = tuple(f"{suffix}{DISABLED_SUFFIX}" for suffix in MOD_SUFFIXES)
    return name.endswith(MOD_SUFFIXES) or name.endswith(disabled_suffixes)


def display_name(path: Path) -> str:
    name = path.name
    if name.endswith(DISABLED_SUFFIX):
        name = name.removesuffix(DISABLED_SUFFIX)
    return name.removeprefix(LOCKED_PREFIX)


def list_mods(mods_root: Path, version: str) -> list[ModEntry]:
    folder = version_mod_dir(mods_root, version)
    entries: list[ModEntry] = []
    for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or not is_mod_file(path):
            continue
        entries.append(
            ModEntry(
                name=display_name(path),
                path=path,
                enabled=not path.name.endswith(DISABLED_SUFFIX),
                locked=path.name.startswith(LOCKED_PREFIX),
            )
        )
    return entries


def add_mod(mods_root: Path, version: str, source: Path) -> Path:
    if source.suffix.lower() not in MOD_SUFFIXES:
        raise ValueError("Only .jar and .mrpack files are supported.")
    target = version_mod_dir(mods_root, version) / source.name
    shutil.copy2(source, target)
    return target


def toggle_mod(entry: ModEntry, enable: bool) -> Path:
    if entry.locked:
        raise PermissionError("This mod is locked and cannot be disabled.")

    if enable and entry.path.name.endswith(DISABLED_SUFFIX):
        target = entry.path.with_name(entry.path.name.removesuffix(DISABLED_SUFFIX))
        entry.path.rename(target)
        return target

    if not enable and not entry.path.name.endswith(DISABLED_SUFFIX):
        target = entry.path.with_name(f"{entry.path.name}{DISABLED_SUFFIX}")
        entry.path.rename(target)
        return target

    return entry.path


def prepare_version_mods(mods_root: Path, minecraft_dir: Path, version: str) -> None:
    mc_mods = minecraft_dir / "mods"
    temp_mods = mods_root / "temp-mods"
    mc_mods.mkdir(exist_ok=True)
    temp_mods.mkdir(parents=True, exist_ok=True)

    for suffix in MOD_SUFFIXES:
        for path in mc_mods.glob(f"*{suffix}"):
            target = temp_mods / path.name
            if target.exists():
                target.unlink()
            shutil.move(str(path), str(target))

    for entry in list_mods(mods_root, version):
        if entry.enabled:
            shutil.copy2(entry.path, mc_mods / f"{TEMP_PREFIX}{entry.path.name}")


def restore_original_mods(mods_root: Path, minecraft_dir: Path) -> None:
    mc_mods = minecraft_dir / "mods"
    temp_mods = mods_root / "temp-mods"
    mc_mods.mkdir(exist_ok=True)
    temp_mods.mkdir(parents=True, exist_ok=True)

    for suffix in MOD_SUFFIXES:
        for path in mc_mods.glob(f"{TEMP_PREFIX}*{suffix}"):
            path.unlink(missing_ok=True)

    for suffix in MOD_SUFFIXES:
        for path in temp_mods.glob(f"*{suffix}"):
            target = mc_mods / path.name
            if target.exists():
                target.unlink()
            shutil.move(str(path), str(target))
