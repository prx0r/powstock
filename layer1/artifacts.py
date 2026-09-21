"""ArtifactStore — global content-addressed objects + per-run receipts.

Level 1 storage model:

  OBJECT
    immutable content-addressed bytes
    stored once globally, never duplicated

  RECEIPT
    this ingest run observed this object at this time
    one object can have many receipts (same bytes fetched on different days)

  INGEST_RUN
    a bounded attempt to fetch from a source
    start → fetch → store artifact → parse → complete

Layout:
  data/raw/objects/{ab}/{cd}/{sha256}.bin   (global, content-addressed)
  data/raw/objects/{ab}/{cd}/{sha256}.meta.json  (sidecar, disaster recovery)

Canonical index is SQLite, not filesystem.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PARSER_VERSION = "1"  # Increment when parser logic changes


@dataclass
class IngestRun:
    """Bounded collection attempt with lifecycle tracking.

    Usage:
        with IngestRun(conn, source="yahoo_prices") as run:
            artifact = store.put_http_response(..., run_id=run.id)
            facts = parse(artifact)
            run.complete(records_seen=len(facts))
    """

    conn: sqlite3.Connection
    source: str
    dataset: str = ""
    source_url: str = ""
    parser_version: str = PARSER_VERSION
    id: int | None = None
    started_at: str = ""
    completed_at: str | None = None
    status: str = "running"
    records_seen: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    error_count: int = 0
    error_message: str | None = None
    content_sha256: str | None = None
    content_length: int | None = None
    raw_object_uri: str | None = None

    def __post_init__(self):
        self.started_at = datetime.now().isoformat()

    def __enter__(self) -> IngestRun:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.status = "error"
            self.error_message = str(exc_val)[:500]
            self.error_count += 1
        if self.completed_at is None:
            self.complete()
        # Only suppress IO/network errors, re-raise programming errors
        if exc_type is not None and not issubclass(exc_type, (IOError, OSError, ConnectionError, TimeoutError)):
            return False  # re-raise
        return True  # suppress

    def start(self) -> None:
        """Record the start of an ingest run."""
        cursor = self.conn.execute(
            """INSERT INTO ingest_run
               (source, dataset, started_at, status, parser_version, source_url)
               VALUES (?, ?, ?, 'running', ?, ?)""",
            (self.source, self.dataset, self.started_at, self.parser_version, self.source_url),
        )
        self.id = cursor.lastrowid
        self.conn.commit()

    def complete(
        self,
        records_seen: int | None = None,
        records_accepted: int | None = None,
        records_rejected: int | None = None,
    ) -> None:
        """Record the completion of an ingest run."""
        self.completed_at = datetime.now().isoformat()
        if self.status == "running":
            self.status = "ok"
        if records_seen is not None:
            self.records_seen = records_seen
        if records_accepted is not None:
            self.records_accepted = records_accepted
        if records_rejected is not None:
            self.records_rejected = records_rejected

        self.conn.execute(
            """UPDATE ingest_run SET
               completed_at=?, status=?, records_seen=?, records_accepted=?,
               records_rejected=?, error_count=?, error_message=?,
               content_sha256=?, content_length=?, raw_object_uri=?
               WHERE run_id=?""",
            (
                self.completed_at, self.status,
                self.records_seen, self.records_accepted, self.records_rejected,
                self.error_count, self.error_message,
                self.content_sha256, self.content_length, self.raw_object_uri,
                self.id,
            ),
        )
        self.conn.commit()

    def link_artifact(self, sha256: str, storage_uri: str, size: int) -> None:
        """Link a stored artifact to this ingest run."""
        self.content_sha256 = sha256
        self.raw_object_uri = storage_uri
        self.content_length = size

        self.conn.execute(
            """INSERT OR IGNORE INTO artifact_receipt
               (sha256, run_id, source, dataset, storage_uri, bytes, retrieved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sha256, self.id, self.source, self.dataset, storage_uri, size,
             datetime.now().isoformat()),
        )
        self.conn.commit()


class ArtifactStore:
    """Global content-addressed raw artifact storage.

    Objects are stored by SHA256 hash in a two-level directory layout:
      data/raw/objects/{ab}/{cd}/{sha256}.bin

    Same bytes → same hash → stored once globally.
    Different runs that fetch identical bytes create new receipts,
    not new objects.

    The canonical index is SQLite (artifact_object + artifact_receipt tables).
    Filesystem sidecar .meta.json is for disaster recovery only.
    """

    def __init__(self, base_dir: str | Path = "data/raw", conn: sqlite3.Connection | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.objects_dir = self.base_dir / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.conn = conn

    def put_bytes(
        self,
        data: bytes,
        source: str,
        dataset: str,
        run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        content_type: str = "application/octet-stream",
        source_url: str = "",
        source_timestamp: str = "",
    ) -> dict[str, Any]:
        """Store raw bytes as a global content-addressed object.

        Returns artifact record with object path and receipt info.
        """
        sha256 = hashlib.sha256(data).hexdigest()
        now = datetime.now().isoformat()

        # Global content-addressed layout: objects/{ab}/{cd}/{sha256}.bin
        ab = sha256[:2]
        cd = sha256[2:4]
        obj_dir = self.objects_dir / ab / cd
        obj_dir.mkdir(parents=True, exist_ok=True)

        obj_path = obj_dir / f"{sha256}.bin"
        meta_path = obj_dir / f"{sha256}.meta.json"

        # Write object only if not already present (global dedup)
        is_new = not obj_path.exists()
        if is_new:
            obj_path.write_bytes(data)

        # Always write sidecar metadata (may update with new receipt info)
        sidecar = {
            "sha256": sha256,
            "bytes": len(data),
            "content_type": content_type,
            "source_url": source_url,
            "first_seen": now if is_new else self._get_first_seen(sha256),
            "last_seen": now,
        }
        meta_path.write_text(json.dumps(sidecar, indent=2, default=str))

        # Record object in database (idempotent)
        if self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO artifact_object
                   (sha256, bytes, content_type, storage_uri, first_seen)
                   VALUES (?, ?, ?, ?, ?)""",
                (sha256, len(data), content_type, str(obj_path),
                 now if is_new else self._get_first_seen(sha256)),
            )

            # Record receipt (this run observed this object)
            if run_id is not None:
                self.conn.execute(
                    """INSERT INTO artifact_receipt
                       (sha256, run_id, source, dataset, storage_uri, bytes, retrieved_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sha256, run_id, source, dataset, str(obj_path), len(data), now),
                )

            self.conn.commit()

        return {
            "artifact_id": sha256,
            "sha256": sha256,
            "bytes": len(data),
            "content_type": content_type,
            "storage_uri": str(obj_path),
            "source_url": source_url,
            "retrieved_at": now,
            "is_new": is_new,
            "run_id": run_id,
            "metadata": metadata or {},
        }

    def put_file(
        self,
        file_path: str | Path,
        source: str,
        dataset: str,
        run_id: int | None = None,
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
            run_id=run_id,
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
        run_id: int | None = None,
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
            run_id=run_id,
            metadata=meta,
            content_type=content_type,
            source_url=source_url,
        )

    def get(self, sha256: str) -> Path | None:
        """Retrieve object by SHA256. Returns path if found."""
        ab = sha256[:2]
        cd = sha256[2:4]
        obj_path = self.objects_dir / ab / cd / f"{sha256}.bin"
        if obj_path.exists():
            return obj_path
        return None

    def exists(self, sha256: str) -> bool:
        """Check if object already stored."""
        return self.get(sha256) is not None

    def list_objects(self, source: str | None = None) -> list[dict[str, Any]]:
        """List all stored objects from DB (canonical index)."""
        if self.conn:
            if source:
                rows = self.conn.execute(
                    """SELECT DISTINCT ao.sha256, ao.bytes, ao.content_type,
                              ao.storage_uri, ao.first_seen
                       FROM artifact_object ao
                       JOIN artifact_receipt ar ON ao.sha256 = ar.sha256
                       WHERE ar.source = ?
                       ORDER BY ao.first_seen""",
                    (source,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT sha256, bytes, content_type, storage_uri, first_seen
                       FROM artifact_object ORDER BY first_seen"""
                ).fetchall()
            return [
                {"sha256": r[0], "bytes": r[1], "content_type": r[2],
                 "storage_uri": r[3], "first_seen": r[4]}
                for r in rows
            ]
        return []

    def list_receipts(self, sha256: str) -> list[dict[str, Any]]:
        """List all receipts for an object (when it was fetched, by which run)."""
        if self.conn:
            rows = self.conn.execute(
                """SELECT ar.run_id, ar.source, ar.dataset, ar.retrieved_at, ar.bytes
                   FROM artifact_receipt ar
                   WHERE ar.sha256 = ?
                   ORDER BY ar.retrieved_at""",
                (sha256,),
            ).fetchall()
            return [
                {"run_id": r[0], "source": r[1], "dataset": r[2],
                 "retrieved_at": r[3], "bytes": r[4]}
                for r in rows
            ]
        return []

    def _get_first_seen(self, sha256: str) -> str:
        """Get first_seen time for an existing object."""
        if self.conn:
            row = self.conn.execute(
                "SELECT first_seen FROM artifact_object WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
            if row:
                return row[0]
        return datetime.now().isoformat()

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
            ".bin": "application/octet-stream",
        }.get(suffix, "application/octet-stream")
