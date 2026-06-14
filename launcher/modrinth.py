from __future__ import annotations

import json
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


API_BASE = "https://api.modrinth.com/v2"
USER_AGENT = "EnchantedLauncher/0.2 (https://github.com/AdmerPRO/Enchanted_Launcher)"


@dataclass(frozen=True)
class ModrinthProject:
    project_id: str
    slug: str
    title: str
    description: str
    icon_url: str
    downloads: int


def request_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def search_mods(query: str, game_version: str, limit: int = 12) -> list[ModrinthProject]:
    facets = json.dumps(
        [
            ["project_type:mod"],
            ["categories:fabric"],
            [f"versions:{game_version}"],
        ],
        separators=(",", ":"),
    )
    params = urllib.parse.urlencode(
        {
            "query": query,
            "facets": facets,
            "index": "downloads",
            "limit": limit,
        }
    )
    data = request_json(f"{API_BASE}/search?{params}")
    projects: list[ModrinthProject] = []
    for hit in data.get("hits", []):
        projects.append(
            ModrinthProject(
                project_id=str(hit.get("project_id", "")),
                slug=str(hit.get("slug", "")),
                title=str(hit.get("title", "")),
                description=str(hit.get("description", "")),
                icon_url=str(hit.get("icon_url") or ""),
                downloads=int(hit.get("downloads", 0)),
            )
        )
    return projects


def latest_primary_file(project_id: str, game_version: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "loaders": json.dumps(["fabric"], separators=(",", ":")),
            "game_versions": json.dumps([game_version], separators=(",", ":")),
            "include_changelog": "false",
        }
    )
    versions = request_json(f"{API_BASE}/project/{urllib.parse.quote(project_id)}/version?{params}")
    for version in versions:
        files = version.get("files", [])
        primary = next((file for file in files if file.get("primary")), None)
        candidate = primary or (files[0] if files else None)
        if candidate and str(candidate.get("filename", "")).lower().endswith(".jar"):
            return {
                "url": candidate["url"],
                "filename": candidate["filename"],
                "version": version.get("version_number", ""),
            }
    raise FileNotFoundError("No Fabric .jar file found for this Minecraft version.")


def download_url(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as file:
        shutil.copyfileobj(response, file)
    return target


def download_project_icon(project: ModrinthProject, cache_dir: Path) -> Path | None:
    if not project.icon_url:
        return None
    parsed = urllib.parse.urlparse(project.icon_url)
    suffix = Path(parsed.path).suffix or ".png"
    target = cache_dir / f"{project.project_id}{suffix}"
    if target.exists():
        return target
    return download_url(project.icon_url, target)


def download_project_file(project: ModrinthProject, game_version: str, download_dir: Path) -> Path:
    file_info = latest_primary_file(project.project_id, game_version)
    target = download_dir / file_info["filename"]
    return download_url(file_info["url"], target)
