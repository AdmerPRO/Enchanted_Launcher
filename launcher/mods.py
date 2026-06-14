from __future__ import annotations

from pathlib import Path


MOD_SUFFIXES = (".jar", ".mrpack")
DISABLED_SUFFIX = ".disabled"
TEMP_PREFIX = "tmp_el_"


def is_mod_file(path: Path) -> bool:
    name = path.name.lower()
    disabled_suffixes = tuple(f"{suffix}{DISABLED_SUFFIX}" for suffix in MOD_SUFFIXES)
    return name.endswith(MOD_SUFFIXES) or name.endswith(disabled_suffixes)
