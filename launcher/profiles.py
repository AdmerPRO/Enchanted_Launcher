from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import SUPPORTED_VERSIONS
from .mods import DISABLED_SUFFIX, MOD_SUFFIXES, TEMP_PREFIX, is_mod_file


DEFAULT_PROFILE_ID = "default"


@dataclass
class Profile:
    id: str
    name: str
    version: str
    icon: str = ""
    mods: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileMod:
    name: str
    path: Path
    enabled: bool
    inherited: bool
    source_profile: str
    icon_path: Path | None = None
    source: str = "custom"


@dataclass
class QuickPlaySlot:
    index: int
    label: str = ""
    profile_id: str = ""
    server_host: str = ""
    server_port: str = ""


def safe_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "profile"


def enabled_filename(path: Path) -> str:
    return path.name.removesuffix(DISABLED_SUFFIX)


def display_name(path: Path, metadata: dict[str, Any] | None = None) -> str:
    if metadata and metadata.get("title"):
        return str(metadata["title"])
    return Path(enabled_filename(path)).stem


class ProfileStore:
    def __init__(self, profiles_root: Path, temp_mods: Path, root: Path) -> None:
        self.profiles_root = profiles_root
        self.temp_mods = temp_mods
        self.root = root
        self.profiles_root.mkdir(parents=True, exist_ok=True)
        self.temp_mods.mkdir(parents=True, exist_ok=True)
        self.ensure_default_profile()

    def ensure_default_profile(self) -> None:
        default_dir = self.profile_dir(DEFAULT_PROFILE_ID)
        default_dir.mkdir(parents=True, exist_ok=True)
        (default_dir / "mods").mkdir(exist_ok=True)
        config = default_dir / "profile.json"
        if not config.exists():
            self.save_profile(
                Profile(
                    id=DEFAULT_PROFILE_ID,
                    name="Default",
                    version=SUPPORTED_VERSIONS[-2],
                )
            )

    def profile_dir(self, profile_id: str) -> Path:
        return self.profiles_root / profile_id

    def mods_dir(self, profile_id: str) -> Path:
        path = self.profile_dir(profile_id) / "mods"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def profile_config_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "profile.json"

    def load_profile(self, profile_id: str) -> Profile:
        path = self.profile_config_path(profile_id)
        if not path.exists():
            raise FileNotFoundError(f"Profile does not exist: {profile_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile(
            id=str(data.get("id", profile_id)),
            name=str(data.get("name", profile_id.title())),
            version=str(data.get("version", SUPPORTED_VERSIONS[-2])),
            icon=str(data.get("icon", "")),
            mods=dict(data.get("mods", {})),
        )

    def save_profile(self, profile: Profile) -> None:
        profile_dir = self.profile_dir(profile.id)
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "mods").mkdir(exist_ok=True)
        data = {
            "id": profile.id,
            "name": profile.name,
            "version": profile.version,
            "icon": profile.icon,
            "mods": profile.mods,
        }
        self.profile_config_path(profile.id).write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )

    def list_profiles(self) -> list[Profile]:
        profiles = []
        for path in self.profiles_root.iterdir():
            if path.is_dir() and (path / "profile.json").exists():
                profiles.append(self.load_profile(path.name))
        profiles.sort(key=lambda profile: (profile.id != DEFAULT_PROFILE_ID, profile.name.lower()))
        return profiles

    def create_profile(self, name: str, version: str | None = None) -> Profile:
        base_id = safe_id(name)
        profile_id = base_id
        counter = 2
        while self.profile_config_path(profile_id).exists():
            profile_id = f"{base_id}-{counter}"
            counter += 1

        profile = Profile(
            id=profile_id,
            name=name.strip() or "Profile",
            version=version or SUPPORTED_VERSIONS[-2],
        )
        self.save_profile(profile)
        return profile

    def update_profile(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        version: str | None = None,
        icon: str | None = None,
    ) -> Profile:
        profile = self.load_profile(profile_id)
        if name is not None:
            profile.name = name.strip() or profile.name
        if version is not None:
            profile.version = version
        if icon is not None:
            profile.icon = icon
        self.save_profile(profile)
        return profile

    def add_custom_mod(self, profile_id: str, source: Path) -> Path:
        if source.suffix.lower() not in MOD_SUFFIXES:
            raise ValueError("Only .jar and .mrpack files are supported.")
        profile = self.load_profile(profile_id)
        target = self.mods_dir(profile_id) / source.name
        shutil.copy2(source, target)
        key = enabled_filename(target)
        profile.mods[key] = {
            "title": source.stem,
            "source": "custom",
            "icon": "",
        }
        self.save_profile(profile)
        return target

    def add_downloaded_mod(
        self,
        profile_id: str,
        source: Path,
        *,
        title: str,
        project_id: str,
        icon_path: Path | None,
    ) -> Path:
        profile = self.load_profile(profile_id)
        target = self.mods_dir(profile_id) / source.name
        shutil.copy2(source, target)
        profile.mods[enabled_filename(target)] = {
            "title": title,
            "source": "modrinth",
            "project_id": project_id,
            "icon": self.relative_path(icon_path) if icon_path else "",
        }
        self.save_profile(profile)
        return target

    def relative_path(self, path: Path | None) -> str:
        if not path:
            return ""
        try:
            return str(path.resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(path)

    def absolute_path(self, value: str) -> Path | None:
        if not value:
            return None
        path = Path(value)
        if path.is_absolute():
            return path
        return self.root / path

    def list_mods(self, profile_id: str) -> list[ProfileMod]:
        profile = self.load_profile(profile_id)
        own = self._list_profile_mods(profile, inherited=False, source_profile=profile.name)
        if profile.id == DEFAULT_PROFILE_ID:
            return own

        own_names = {mod.name.lower() for mod in own}
        default = self.load_profile(DEFAULT_PROFILE_ID)
        inherited = [
            mod
            for mod in self._list_profile_mods(default, inherited=True, source_profile=default.name)
            if mod.name.lower() not in own_names
        ]
        return inherited + own

    def _list_profile_mods(self, profile: Profile, inherited: bool, source_profile: str) -> list[ProfileMod]:
        entries: list[ProfileMod] = []
        for path in sorted(self.mods_dir(profile.id).iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or not is_mod_file(path):
                continue
            key = enabled_filename(path)
            metadata = profile.mods.get(key, {})
            icon = self.absolute_path(str(metadata.get("icon", "")))
            entries.append(
                ProfileMod(
                    name=display_name(path, metadata),
                    path=path,
                    enabled=not path.name.endswith(DISABLED_SUFFIX),
                    inherited=inherited,
                    source_profile=source_profile,
                    icon_path=icon if icon and icon.exists() else None,
                    source=str(metadata.get("source", "custom")),
                )
            )
        return entries

    def toggle_mod(self, mod: ProfileMod, enable: bool) -> None:
        if mod.inherited:
            raise PermissionError("This mod is inherited from Default. Edit it in the Default profile.")
        if enable and mod.path.name.endswith(DISABLED_SUFFIX):
            mod.path.rename(mod.path.with_name(mod.path.name.removesuffix(DISABLED_SUFFIX)))
        elif not enable and not mod.path.name.endswith(DISABLED_SUFFIX):
            mod.path.rename(mod.path.with_name(f"{mod.path.name}{DISABLED_SUFFIX}"))

    def prepare_mods(self, profile_id: str, minecraft_dir: Path) -> None:
        mc_mods = minecraft_dir / "mods"
        mc_mods.mkdir(exist_ok=True)
        self.temp_mods.mkdir(parents=True, exist_ok=True)

        for suffix in MOD_SUFFIXES:
            for path in mc_mods.glob(f"*{suffix}"):
                target = self.temp_mods / path.name
                if target.exists():
                    target.unlink()
                shutil.move(str(path), str(target))

        copied: dict[str, Path] = {}
        for mod in self.list_mods(profile_id):
            if not mod.enabled:
                continue
            target = mc_mods / f"{TEMP_PREFIX}{enabled_filename(mod.path)}"
            if target.name in copied:
                copied[target.name].unlink(missing_ok=True)
            shutil.copy2(mod.path, target)
            copied[target.name] = target

    def restore_mods(self, minecraft_dir: Path) -> None:
        mc_mods = minecraft_dir / "mods"
        mc_mods.mkdir(exist_ok=True)
        self.temp_mods.mkdir(parents=True, exist_ok=True)

        for suffix in MOD_SUFFIXES:
            for path in mc_mods.glob(f"{TEMP_PREFIX}*{suffix}"):
                path.unlink(missing_ok=True)

        for suffix in MOD_SUFFIXES:
            for path in self.temp_mods.glob(f"*{suffix}"):
                target = mc_mods / path.name
                if target.exists():
                    target.unlink()
                shutil.move(str(path), str(target))
