"""ArtifactStore — raw bytes before parsing.

This is the correct Level 1 abstraction:

  fetch()
    ↓
  ArtifactStore.put_bytes(response.content, metadata)
    ↓
  artifact_id (content-addressed)
    ↓
  parse(artifact)
    ↓
  normalized rows

Never: parse → store parsed object → call it raw.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class ArtifactStore:
    """Content-addressed raw artifact storage.

    Stores original bytes on disk and metadata in SQLite.
    Same bytes → same hash → no duplicate storage.
    """

    def __init__(self, base_dir: str | Path = "data/raw", conn: sqlite3.Connection | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.conn = conn

    def put_bytes(
        self,
        data: bytes,
        source: str,
        dataset: str,
        metadata: dict[str, Any] | None = None,
        content_type: str = "application/octet-stream",
        source_url: str = "",
        source_timestamp: str = "",
    ) -> dict[str, Any]:
        """Store raw bytes. Returns artifact record.

        The artifact_id is the SHA256 of the bytes — content-addressed.
        """
        sha256 = hashlib.sha256(data).hexdigest()
        now = datetime.now().isoformat()

        # Organize by source/date
        today = datetime.now().strftime("%Y-%m-%d")
        artifact_dir = self.base_dir / source / today
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Content-addressed filename
        filename = f"{sha256[:16]}_{dataset}.bin"
        artifact_path = artifact_dir / filename

        # Dedup: skip if same hash already stored
        if not artifact_path.exists():
            artifact_path.write_bytes(data)

        artifact = {
            "artifact_id": sha256,
            "source": source,
            "dataset": dataset,
            "content_type": content_type,
            "bytes": len(data),
            "sha256": sha256,
            "storage_uri": str(artifact_path),
            "source_url": source_url,
            "source_timestamp": source_timestamp,
            "retrieved_at": now,
            "metadata": metadata or {},
        }

        # Store metadata alongside artifact
        meta_path = artifact_dir / f"{sha256[:16]}_{dataset}.meta.json"
        meta_path.write_text(json.dumps(artifact, indent=2, default=str))

        # Record in database if available
        if self.conn:
            self.conn.execute("""
                INSERT OR IGNORE INTO raw_artifact
                (run_id, sha256, mime_type, bytes, storage_uri)
                VALUES (0, ?, ?, ?, ?)
            """, (sha256, content_type, len(data), str(artifact_path)))

        return artifact

    def put_file(
        self,
        file_path: str | Path,
        source: str,
        dataset: str,
        metadata: dict[str, Any] | None = None,
        source_url: str = "",
        source_timestamp: str = "",
    ) -> dict[str, Any]:
        """Store a file as a raw artifact."""
        path = Path(file_path)
        data = path.read_bytes()
        return self.put_bytes(
            data=data,
            source=source,
            dataset=dataset,
            metadata=metadata,
            content_type=self._guess_content_type(path),
            source_url=source_url,
            source_timestamp=source_timestamp,
        )

    def put_http_response(
        self,
        content: bytes,
        source: str,
        dataset: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
        source_url: str = "",
    ) -> dict[str, Any]:
        """Store HTTP response bytes as a raw artifact."""
        meta = {
            "status_code": status_code,
            "headers": headers or {},
            **(metadata or {}),
        }
        content_type = (headers or {}).get("content-type", "application/octet-stream")
        return self.put_bytes(
            data=content,
            source=source,
            dataset=dataset,
            metadata=meta,
            content_type=content_type,
            source_url=source_url,
        )

    def get(self, sha256: str) -> Path | None:
        """Retrieve artifact by SHA256. Returns path if found."""
        # Search all source/date directories
        for meta_path in self.base_dir.rglob(f"{sha256[:16]}_*.meta.json"):
            meta = json.loads(meta_path.read_text())
            storage_path = Path(meta["storage_uri"])
            if storage_path.exists():
                return storage_path
        return None

    def exists(self, sha256: str) -> bool:
        """Check if artifact already stored."""
        return self.get(sha256) is not None

    def list_artifacts(self, source: str | None = None) -> list[dict[str, Any]]:
        """List stored artifacts."""
        artifacts = []
        pattern = f"*/*.meta.json" if not source else f"{source}/*/*.meta.json"
        for meta_path in self.base_dir.glob(pattern):
            artifacts.append(json.loads(meta_path.read_text()))
        return artifacts

    def _guess_content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".zip": "application/zip",
            ".json": "application/json",
            ".jsonl": "application/jsonl",
            ".csv": "text/csv",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".html": "text/html",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
        }.get(suffix, "application/octet-stream")
