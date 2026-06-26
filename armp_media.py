"""
ARMP Multi-Modal Messages — Image, video, and audio support for agent-to-agent chat.

Phase 7: Extends ARMP's message format to support rich media exchange between agents.
Agents can send, receive, and process images, video, audio, and structured data.

Protocol: ARMP extension v0.7.0
"""

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("armp.media")


class MediaType(str, Enum):
    IMAGE = "image"          # PNG, JPEG, WebP, SVG
    VIDEO = "video"          # MP4, WebM, GIF
    AUDIO = "audio"          # MP3, OGG, WAV, FLAC
    DOCUMENT = "document"    # PDF, CSV, JSON, etc.
    STRUCTURED = "structured"  # Tables, charts, diagrams
    CODE = "code"            # Code snippets with syntax highlighting


@dataclass
class MediaAttachment:
    """A media attachment in an ARMP message."""
    media_id: str
    media_type: MediaType
    filename: str
    mime_type: str = ""
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    thumbnail_url: str = ""
    content_url: str = ""          # Matrix MXC URL or remote URL
    caption: str = ""
    metadata: dict = field(default_factory=dict)
    checksum_sha256: str = ""

    def to_dict(self) -> dict:
        return {
            "media_id": self.media_id,
            "media_type": self.media_type.value,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url,
            "content_url": self.content_url,
            "caption": self.caption,
            "checksum_sha256": self.checksum_sha256,
        }


@dataclass
class StructuredData:
    """Structured tabular/chart data in a message."""
    data_id: str
    format: str = "table"          # table, chart, diagram, json
    title: str = ""
    headers: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    chart_type: str = ""           # bar, line, pie, scatter
    chart_config: dict = field(default_factory=dict)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "data_id": self.data_id,
            "format": self.format,
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "chart_type": self.chart_type,
            "chart_config": self.chart_config,
            "raw_data": self.raw_data,
        }


@dataclass
class MediaMessage:
    """An ARMP message containing media attachments."""
    message_id: str = ""
    sender_did: str = ""
    body: str = ""
    attachments: list[MediaAttachment] = field(default_factory=list)
    structured_data: list[StructuredData] = field(default_factory=list)
    reply_to: str = ""
    thread_id: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.message_id:
            import uuid
            self.message_id = f"MM-{uuid.uuid4().hex[:8].upper()}"
        if not self.timestamp:
            self.timestamp = _now_iso()

    def to_armp_event(self) -> dict:
        """Convert to ARMP Matrix event format."""
        return {
            "msgtype": "m.agent.media",
            "body": self.body or "Media message",
            "format": "org.matrix.custom.html",
            "formatted_body": self._format_html(),
            "amp_metadata": {
                "version": "0.7.0",
                "message_id": self.message_id,
                "sender_did": self.sender_did,
                "media_message": {
                    "attachments": [a.to_dict() for a in self.attachments],
                    "structured_data": [s.to_dict() for s in self.structured_data],
                    "reply_to": self.reply_to,
                    "thread_id": self.thread_id,
                    "timestamp": self.timestamp,
                },
            },
        }

    def _format_html(self) -> str:
        """Format the message as rich HTML."""
        parts = [f"<p>{self.body}</p>"] if self.body else []

        for att in self.attachments:
            if att.media_type == MediaType.IMAGE:
                parts.append(
                    f'<img src="{att.content_url}" '
                    f'width="{att.width}" height="{att.height}" '
                    f'alt="{att.caption or att.filename}" />'
                )
            elif att.media_type == MediaType.VIDEO:
                parts.append(
                    f'<video src="{att.content_url}" controls '
                    f'poster="{att.thumbnail_url}">'
                    f'{att.caption or att.filename}</video>'
                )
            elif att.media_type == MediaType.AUDIO:
                parts.append(
                    f'<audio src="{att.content_url}" controls>'
                    f'{att.caption or att.filename}</audio>'
                )

        for sd in self.structured_data:
            if sd.format == "table":
                parts.append(_render_table_html(sd))

        return "\n".join(parts)

    @classmethod
    def from_armp_event(cls, event: dict) -> "MediaMessage":
        """Parse from an ARMP Matrix event."""
        meta = event.get("amp_metadata", {}).get("media_message", {})
        attachments = [MediaAttachment(**a) for a in meta.get("attachments", [])]
        structured = [StructuredData(**s) for s in meta.get("structured_data", [])]
        return cls(
            message_id=meta.get("message_id", ""),
            sender_did=meta.get("sender_did", ""),
            body=event.get("body", ""),
            attachments=attachments,
            structured_data=structured,
            reply_to=meta.get("reply_to", ""),
            thread_id=meta.get("thread_id", ""),
            timestamp=meta.get("timestamp", ""),
        )


def _render_table_html(data: StructuredData) -> str:
    """Render structured data as an HTML table."""
    html = ['<table border="1" style="border-collapse:collapse">']
    if data.title:
        html.append(f'<caption>{data.title}</caption>')
    if data.headers:
        html.append("<tr>" + "".join(f"<th>{h}</th>" for h in data.headers) + "</tr>")
    for row in data.rows:
        html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    html.append("</table>")
    return "".join(html)


class MediaProcessor:
    """Processes and validates media attachments."""

    ALLOWED_TYPES = {
        MediaType.IMAGE: ["image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/gif"],
        MediaType.VIDEO: ["video/mp4", "video/webm", "image/gif"],
        MediaType.AUDIO: ["audio/mpeg", "audio/ogg", "audio/wav", "audio/flac"],
        MediaType.DOCUMENT: ["application/pdf", "text/csv", "application/json"],
    }

    MAX_SIZE = {
        MediaType.IMAGE: 50 * 1024 * 1024,      # 50 MB
        MediaType.VIDEO: 500 * 1024 * 1024,      # 500 MB
        MediaType.AUDIO: 100 * 1024 * 1024,      # 100 MB
        MediaType.DOCUMENT: 100 * 1024 * 1024,   # 100 MB
    }

    @classmethod
    def validate(cls, attachment: MediaAttachment) -> tuple[bool, str]:
        """Validate a media attachment."""
        allowed = cls.ALLOWED_TYPES.get(attachment.media_type, [])
        if allowed and attachment.mime_type not in allowed:
            return False, f"MIME type '{attachment.mime_type}' not allowed for {attachment.media_type.value}"

        max_size = cls.MAX_SIZE.get(attachment.media_type, 10 * 1024 * 1024)
        if attachment.size_bytes > max_size:
            return False, f"Size {attachment.size_bytes} exceeds max {max_size}"

        return True, "OK"

    @classmethod
    def detect_type(cls, filename: str) -> Optional[MediaType]:
        """Detect media type from filename extension."""
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            return None
        if mime.startswith("image/"):
            return MediaType.IMAGE
        if mime.startswith("video/"):
            return MediaType.VIDEO
        if mime.startswith("audio/"):
            return MediaType.AUDIO
        if mime in ("application/pdf", "text/csv", "application/json"):
            return MediaType.DOCUMENT
        return None


class MediaManager:
    """Manages media message sending and receiving."""

    def __init__(self, matrix_client=None):
        self.matrix = matrix_client
        self._attachments: dict[str, MediaAttachment] = {}
        self._history: list[MediaMessage] = []

    async def upload(self, file_path: str, media_type: MediaType | None = None) -> MediaAttachment:
        """Upload a file and prepare as an ARMP attachment."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        if not media_type:
            media_type = MediaProcessor.detect_type(path.name) or MediaType.DOCUMENT

        size = path.stat().st_size

        # Compute checksum
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        import uuid
        attachment = MediaAttachment(
            media_id=f"ATT-{uuid.uuid4().hex[:8].upper()}",
            media_type=media_type,
            filename=path.name,
            mime_type=mime_type,
            size_bytes=size,
            checksum_sha256=sha256.hexdigest(),
        )

        ok, err = MediaProcessor.validate(attachment)
        if not ok:
            raise ValueError(f"Invalid attachment: {err}")

        # Upload to Matrix if client available
        if self.matrix:
            content_url = await self._upload_to_matrix(file_path, mime_type)
            attachment.content_url = content_url

        self._attachments[attachment.media_id] = attachment
        return attachment

    async def _upload_to_matrix(self, file_path: str, mime_type: str) -> str:
        """Upload a file to the Matrix homeserver."""
        # In production: call matrix_client.upload()
        # Stub for now
        return f"mxc://armp-group.org/{Path(file_path).name}"

    async def send_media(self, room_id: str, body: str, file_paths: list[str]) -> MediaMessage:
        """Send a media message with attachments to a room."""
        attachments = []
        for fp in file_paths:
            att = await self.upload(fp)
            attachments.append(att)

        msg = MediaMessage(
            body=body,
            attachments=attachments,
        )
        self._history.append(msg)
        return msg

    async def send_image(self, room_id: str, file_path: str, caption: str = "") -> MediaMessage:
        """Send a single image."""
        return await self.send_media(room_id, caption or Path(file_path).stem, [file_path])

    async def send_video(self, room_id: str, file_path: str, caption: str = "") -> MediaMessage:
        """Send a single video."""
        return await self.send_media(room_id, caption or Path(file_path).stem, [file_path])

    async def send_table(self, room_id: str, title: str, headers: list, rows: list) -> MediaMessage:
        """Send a structured table."""
        import uuid
        sd = StructuredData(
            data_id=f"TBL-{uuid.uuid4().hex[:8].upper()}",
            format="table",
            title=title,
            headers=headers,
            rows=rows,
        )
        msg = MediaMessage(body=title, structured_data=[sd])
        self._history.append(msg)
        return msg

    # ── Stats ─────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "total_attachments": len(self._attachments),
            "messages_sent": len(self._history),
            "by_type": {
                t.value: sum(1 for a in self._attachments.values() if a.media_type == t)
                for t in MediaType
            },
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Demo ────────────────────────────────────────────

async def demo():
    """Demonstrate multi-modal messages."""
    print("🖼️ ARMP Multi-Modal Messages v0.7.0 — Demo\n")

    manager = MediaManager()

    # Create a media message
    msg = MediaMessage(
        sender_did="AGNT-A",
        body="Here's the sales report and a chart",
        attachments=[
            MediaAttachment(
                media_id="ATT-001",
                media_type=MediaType.IMAGE,
                filename="chart.png",
                mime_type="image/png",
                size_bytes=245760,
                width=1200,
                height=800,
                content_url="mxc://armp-group.org/chart.png",
                caption="Q3 Sales Chart",
            ),
        ],
        structured_data=[
            StructuredData(
                data_id="TBL-001",
                format="table",
                title="Q3 Sales by Region",
                headers=["Region", "Revenue", "Growth"],
                rows=[["North", "$2.4M", "+12%"], ["South", "$1.8M", "+8%"], ["East", "$3.1M", "+15%"]],
            ),
        ],
    )

    event = msg.to_armp_event()
    print("ARMP Event:")
    print(json.dumps(event, indent=2)[:500])

    # Parse back
    parsed = MediaMessage.from_armp_event(event)
    print(f"\nParsed: {len(parsed.attachments)} attachments, {len(parsed.structured_data)} structured data")
    print(f"HTML: {parsed._format_html()[:200]}")

    print("\n── Demo Complete ──\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())
