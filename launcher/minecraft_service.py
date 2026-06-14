from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

import minecraft_launcher_lib as mc

from .constants import USERNAME_PATTERN


def valid_username(username: str) -> bool:
    return bool(re.fullmatch(USERNAME_PATTERN, username))


def installed_fabric_id(minecraft_dir: Path, minecraft_version: str) -> str | None:
    installed = mc.utils.get_installed_versions(str(minecraft_dir))
    matches: list[tuple[tuple[int, ...], str]] = []

    for version in installed:
        version_id = version.get("id", "")
        if not version_id.startswith("fabric-loader") or not version_id.endswith(minecraft_version):
            continue

        parts = version_id.split("-")
        if len(parts) < 3:
            continue

        loader_version = tuple(int(part) for part in parts[2].split(".") if part.isdigit())
        matches.append((loader_version, version_id))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0])
    return matches[-1][1]


def install_fabric(minecraft_dir: Path, minecraft_version: str) -> None:
    mc.fabric.install_fabric(minecraft_version, str(minecraft_dir))


def build_launch_command(minecraft_dir: Path, version_id: str, username: str) -> list[str]:
    player_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")
    settings = {
        "username": username,
        "uuid": str(player_uuid),
        "token": "offline",
    }
    return mc.command.get_minecraft_command(version_id, str(minecraft_dir), settings)


def start_process(command: list[str], cwd: Path, log_file, hide_console: bool = True) -> subprocess.Popen:
    creation_flags = subprocess.CREATE_NO_WINDOW if hide_console and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        creationflags=creation_flags,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
