from __future__ import annotations

import gzip
import shutil
import time
from pathlib import Path


def rotate_latest_log(logs_dir: Path) -> Path:
    logs_dir.mkdir(exist_ok=True)
    latest_log = logs_dir / "latest.txt"

    if latest_log.exists():
        timestamp = time.strftime(
            "%Y-%m-%d-%H%M%S",
            time.localtime(latest_log.stat().st_mtime),
        )
        archive = logs_dir / f"{timestamp}.log.gz"
        try:
            with latest_log.open("rb") as source, gzip.open(archive, "wb") as target:
                shutil.copyfileobj(source, target)
            latest_log.unlink()
        except OSError as error:
            print(f"[LOGS] Failed to rotate latest log: {error}")

    return latest_log
