# ARMP Multi-Modal Messages — Specification v0.7.0

## 1. Overview

ARMP Multi-Modal Messages extend the protocol to support rich media exchange between agents: images, video, audio, structured tables, and code snippets.

## 2. Message Format

```json
{
  "msgtype": "m.agent.media",
  "body": "Here's the Q3 report",
  "format": "org.matrix.custom.html",
  "formatted_body": "<p>Here's the Q3 report</p><img src='...' />",
  "amp_metadata": {
    "version": "0.7.0",
    "media_message": {
      "attachments": [...],
      "structured_data": [...]
    }
  }
}
```

## 3. Media Types

| Type | MIME Types | Max Size |
|------|-----------|:--:|
| Image | image/png, jpeg, webp, svg+xml, gif | 50 MB |
| Video | video/mp4, webm, image/gif | 500 MB |
| Audio | audio/mpeg, ogg, wav, flac | 100 MB |
| Document | application/pdf, text/csv, application/json | 100 MB |
| Structured | Tables, charts, diagrams | 10 MB |
| Code | Text with syntax metadata | 5 MB |

## 4. Attachment Object

```json
{
  "media_id": "ATT-001",
  "media_type": "image",
  "filename": "chart.png",
  "mime_type": "image/png",
  "size_bytes": 245760,
  "width": 1200,
  "height": 800,
  "content_url": "mxc://armp-group.org/chart.png",
  "caption": "Q3 Sales Chart",
  "checksum_sha256": "abc123..."
}
```

## 5. Structured Data

```json
{
  "data_id": "TBL-001",
  "format": "table",
  "title": "Q3 Sales",
  "headers": ["Region", "Revenue", "Growth"],
  "rows": [
    ["North", "$2.4M", "+12%"],
    ["South", "$1.8M", "+8%"]
  ]
}
```

### Chart Types

- `bar`, `line`, `pie`, `scatter`, `area`
- `heatmap`, `radar`, `gauge`

## 6. Validation

All attachments are validated before transmission:
- MIME type whitelist
- Size limits
- SHA-256 checksum verification
- Dimension validation for images

## 7. Transport

Media files are uploaded to the Matrix homeserver's content repository and referenced by `mxc://` URLs. Large files (>50MB) may use WebRTC for direct peer-to-peer transfer.

---

*Version 0.7.0. Apache 2.0.*
