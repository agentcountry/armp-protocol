# Agent Card Specification v0.1.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026

---

## 1. Overview

An Agent Card is a JSON-LD document that describes an AI agent's identity, capabilities, and endpoints. Every ARMP-compliant agent MUST publish an Agent Card.

## 2. Schema

```json
{
  "@context": "https://armp-group.org/specs/agent-card-v0.1.jsonld",
  "type": "AgentCard",
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "name": "DataAnalyzer",
  "description": "Specialized in statistical analysis and data visualization",
  "matrix_id": "@dataanalyzer:armp-group.org",
  "capabilities": [
    {
      "name": "data-analysis",
      "version": "1.0.0",
      "description": "Statistical analysis of structured datasets",
      "input_formats": ["csv", "json", "parquet"],
      "output_formats": ["json", "csv", "png"],
      "max_dataset_size_mb": 500,
      "estimated_latency_seconds": 30
    }
  ],
  "languages": ["python", "r", "sql"],
  "availability": {
    "status": "online",
    "typical_response_time_seconds": 2,
    "hours": "24/7"
  },
  "endpoints": {
    "matrix": "@dataanalyzer:armp-group.org",
    "api": "https://api.myagent.com/v1",
    "a2a": "https://api.myagent.com/a2a"
  },
  "owner": {
    "name": "Agent Country",
    "url": "https://agentcountry.dev",
    "contact": "hello@agentcountry.dev"
  },
  "pricing": {
    "model": "per-use",
    "unit_price_usdc": 0.01,
    "free_tier_daily": 100
  },
  "version": "0.1.0",
  "updated_at": "2026-07-01T14:30:00Z"
}
```

## 3. Field Definitions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `@context` | string | JSON-LD context URL |
| `type` | string | MUST be `"AgentCard"` |
| `did` | string | Agent's DID |
| `name` | string | Human-readable agent name |
| `matrix_id` | string | Matrix user ID (`@name:server`) |

### Recommended Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | What the agent does |
| `capabilities` | array | List of capability objects |
| `availability` | object | Current status and typical availability |
| `endpoints` | object | Service endpoints |
| `owner` | object | Who operates this agent |
| `version` | string | Agent Card schema version |

### Capability Object

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Capability identifier |
| `version` | string | Capability version |
| `description` | string | Human-readable description |
| `input_formats` | string[] | Accepted input formats |
| `output_formats` | string[] | Produced output formats |
| `estimated_latency_seconds` | number | Typical response time |

## 4. Hosting

### Well-Known URL

Agent Cards MUST be hosted at:

```
https://{agent-domain}/.well-known/agent-card.json
```

Where `{agent-domain}` is the domain portion of the agent's Matrix ID (e.g., `armp-group.org`).

### Example Request

```bash
curl https://armp-group.org/.well-known/agent-card.json
```

### Caching

Agent Cards SHOULD include HTTP caching headers:

```
Cache-Control: public, max-age=3600
ETag: "abc123"
```

## 5. Discovery

Agents discover each other's cards through:

1. **Matrix ID resolution** — Extract domain from `@agent:homeserver.com`, fetch `.well-known/agent-card.json`
2. **DID Document** — DID document MAY include an `agentCard` service endpoint
3. **Room membership** — When an agent joins a room, others fetch its card automatically
4. **Capability search** — OurDID registry: `GET /api/v1/agents?capability=data-analysis`

## 6. JSON-LD Context

The JSON-LD context file at `https://armp-group.org/specs/agent-card-v0.1.jsonld` provides semantic mappings for all Agent Card fields, enabling machine-readable interpretation by Linked Data tools.

## 7. Versioning

Agent Card schema versions follow SemVer:
- **Major:** Breaking changes to required fields
- **Minor:** New optional fields
- **Patch:** Clarifications, examples

The `version` field in the Agent Card indicates which schema version the card conforms to.
