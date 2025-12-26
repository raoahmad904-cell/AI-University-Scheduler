import csv
import json
import os
from io import StringIO
from pathlib import Path
from typing import List, Dict, Any


def _resolve_upload_dir() -> Path:
    """Pick a writable uploads directory that survives container rebuilds.

    Order of preference:
    1) `UPLOAD_DIR` env var (absolute or relative to CWD)
    2) Project-level `uploads` (sibling of backend when available)
    3) Backend-level `uploads` (/backend/uploads or /app/uploads in container)
    4) Legacy package path /backend/scheduler/uploads
    """

    # 1) explicit override
    env_path = os.getenv("UPLOAD_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()

    here = Path(__file__).resolve()
    parents = list(here.parents)

    # 2) project root (one level above backend). Only if we can see a marker.
    # parents index: 0=.../utils, 1=.../scheduler, 2=.../backend, 3=.../<repo>
    repo_candidate = None
    if len(parents) >= 4:
        maybe_repo = parents[3]
        if (maybe_repo / "frontend").exists() or (maybe_repo / "docker-compose.yml").exists():
            repo_candidate = maybe_repo / "uploads"

    # 3) backend-level (works both locally and in container where /app is backend root)
    backend_candidate = parents[2] / "uploads" if len(parents) >= 3 else None

    # 4) legacy path alongside scheduler
    legacy_candidate = parents[1] / "uploads" if len(parents) >= 2 else None

    for candidate in [repo_candidate, backend_candidate, legacy_candidate]:
        if candidate:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except OSError:
                continue

    # Last resort: cwd/uploads
    fallback = Path.cwd() / "uploads"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


UPLOAD_DIR = _resolve_upload_dir()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def parse_csv_text(text: str) -> List[Dict[str, Any]]:
    f = StringIO(text)
    reader = csv.DictReader(f)
    rows: List[Dict[str, Any]] = []
    for row in reader:
        # Skip empty lines
        if not any((val or "").strip() for val in row.values()):
            continue
        rows.append(dict(row))
    return rows


def save_csv_and_json(kind: str, csv_text: str, rows: List[Dict[str, Any]]):
    csv_path = UPLOAD_DIR / f"{kind}.csv"
    json_path = UPLOAD_DIR / f"{kind}.json"

    # Merge with existing rows instead of replacing, keyed by 'id' when present.
    merged: List[Dict[str, Any]] = []
    existing_map: Dict[str, Dict[str, Any]] = {}

    def _load_existing() -> List[Dict[str, Any]]:
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
            except Exception:
                return []
        if csv_path.exists():
            try:
                return parse_csv_text(csv_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    existing_rows = _load_existing()
    for r in existing_rows:
        key = str(r.get("id")) if isinstance(r, dict) and r.get("id") is not None else None
        if key:
            existing_map[key] = r
        else:
            merged.append(r)

    for r in rows:
        key = str(r.get("id")) if isinstance(r, dict) and r.get("id") is not None else None
        if key:
            # If same id re-uploaded, replace with latest
            existing_map[key] = r
        else:
            merged.append(r)

    merged.extend(existing_map.values())

    # Determine stable field order (union of keys, deterministic)
    fieldnames: List[str] = []
    seen: set[str] = set()
    for row in merged:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)

    # Persist merged data
    csv_output = StringIO()
    if merged:
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(merged)
    
    csv_path.write_text(csv_output.getvalue(), encoding="utf-8")
    json_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")