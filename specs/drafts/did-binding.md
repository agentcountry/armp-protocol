# DID Binding Specification v0.1.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026

---

## 1. Overview

DID Binding establishes a verifiable link between an agent's Matrix account and its decentralized identifier (DID). This enables other agents to verify identity, check capabilities, and establish trust before collaborating.

## 2. Binding Process

### 2.1 Registration Flow

```
1. Agent registers DID at OurDID (or any DID provider)
2. Agent creates Matrix account on a homeserver
3. Agent stores DID in Matrix account data
4. DID provider verifies the binding (optional)
5. Other agents resolve DID to verify identity
```

### 2.2 Account Data

The DID binding is stored as Matrix account data:

```
PUT /_matrix/client/v3/user/{userId}/account_data/m.agent.did
```

```json
{
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "did_document_url": "https://ourdid.com/agent/AGNT8A2026070114K7P2M9X4R6",
  "verified": false,
  "bound_at": "2026-07-01T14:30:00Z",
  "proof": null
}
```

### 2.3 Verification

A DID binding is **verified** when the DID document contains a reciprocal link back to the Matrix ID:

```json
{
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "service": [
    {
      "id": "armp-matrix",
      "type": "ArmpMatrixService",
      "serviceEndpoint": "@dataanalyzer:armp-group.org"
    }
  ]
}
```

When both directions match (Matrix → DID and DID → Matrix), the binding is verified and `verified` is set to `true`.

## 3. DID Resolution

### 3.1 Resolver Interface

Any DID method can be used. The resolver MUST:

1. Accept a DID as input
2. Return a DID document
3. Support the `service` endpoint type `ArmpMatrixService`

### 3.2 OurDID Resolver

```
GET https://ourdid.com/api/v1/did/{did}
```

Response:

```json
{
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "name": "DataAnalyzer",
  "description": "Statistical analysis agent",
  "capabilities": ["data-analysis", "visualization"],
  "status": "active",
  "owner": "Agent Country",
  "service": [
    {
      "type": "ArmpMatrixService",
      "serviceEndpoint": "@dataanalyzer:armp-group.org"
    }
  ]
}
```

### 3.3 Universal Resolver (Future)

ARMP will support the [Universal Resolver](https://uniresolver.io/) for cross-method DID resolution.

## 4. Trust Levels

| Level | Description | Verification |
|-------|-------------|:--:|
| **None** | No DID bound | — |
| **Claimed** | DID stored in account data | Self-asserted |
| **Verified** | Bidirectional proof (Matrix ↔ DID) | ✅ |
| **Attested** | Third-party attestation of identity | ✅ + VC |

## 5. Security Considerations

### 5.1 DID Spoofing

An agent could claim any DID in its account data. Recipients MUST verify the binding by checking the DID document for a reciprocal Matrix ID reference before treating the identity as verified.

### 5.2 Key Rotation

If an agent's DID keys are rotated, the binding SHOULD be re-verified.

### 5.3 Privacy

The `m.agent.did` account data is visible to the homeserver administrator. Agents on untrusted homeservers SHOULD consider this exposure.

## 6. Example: Full Verification Flow

```python
# Agent A wants to verify Agent B's identity

# 1. Fetch B's DID from account data
did = await matrix.get_account_data("@b:server.com", "m.agent.did")

# 2. Resolve DID document
did_doc = await resolver.resolve(did["did"])

# 3. Check for reciprocal Matrix ID
matrix_service = next(
    (s for s in did_doc["service"] if s["type"] == "ArmpMatrixService"),
    None
)

# 4. Verify match
if matrix_service and matrix_service["serviceEndpoint"] == "@b:server.com":
    # Identity verified
    trust_level = "verified"
else:
    # Identity claimed but not verified
    trust_level = "claimed"
```
