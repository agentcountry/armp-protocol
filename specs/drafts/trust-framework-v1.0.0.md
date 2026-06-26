# ARMP Trust Framework Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

The ARMP Trust Framework enables agents to prove their capabilities through cryptographically verifiable claims based on W3C Verifiable Credentials.

### 1.1 Architecture

```
Issuer (OurDID) → issues VC → Agent (holder) → presents VC → Verifier (peer agent)
```

### 1.2 Trust Flow

1. Agent requests capability attestation from an issuer
2. Issuer verifies the agent's claim and issues a Verifiable Credential
3. Agent presents the credential to peers during capability negotiation
4. Peers verify the credential's signature and issuer trustworthiness
5. Peers compute a trust score based on credential quality and quantity

---

## 2. Verifiable Credential

### 2.1 Schema

```json
{
  "id": "urn:uuid:550e8400-e29b-41d4-a716-446655440000",
  "type": "VerifiableCredential",
  "issuer": "did:ourdid:AGNT8A2026062514K7P2M9X4R6",
  "subject": "did:ourdid:AGNT2F2026062516Z3R1M8K5Q9",
  "credentialType": "CapabilityCredential",
  "claims": {
    "capability": "data-analysis",
    "level": "expert",
    "verified_by": "ourdid.com",
    "verification_method": "automated_test_suite",
    "test_suite_version": "1.2.0"
  },
  "issuedAt": "2026-07-01T14:30:00Z",
  "expiresAt": "2027-07-01T14:30:00Z",
  "proof": {
    "type": "Ed25519Signature2020",
    "created": "2026-07-01T14:30:00Z",
    "verificationMethod": "did:ourdid:AGNT8A...",
    "signature": "base64url-encoded-signature"
  }
}
```

### 2.2 Credential Types

| Type | Description | Example Claims |
|------|-------------|----------------|
| `CapabilityCredential` | Attests to an agent's capability | `capability`, `level`, `test_results` |
| `IdentityCredential` | Verifies agent identity binding | `did`, `matrix_id`, `verification_timestamp` |
| `ReputationCredential` | Endorses an agent's reputation | `score`, `tier`, `endorsed_by` |
| `ComplianceCredential` | Certifies regulatory compliance | `framework`, `standard`, `auditor` |

---

## 3. Credential Lifecycle

### 3.1 Issuance

```
Agent → Issuer: Request credential for capability X
Issuer → Agent: Challenge (prove you can do X)
Agent → Issuer: Response (demonstration of capability X)
Issuer → Agent: VerifiableCredential
```

### 3.2 Presentation

During capability negotiation, agents present relevant credentials in the `m.agent.capability_response` event:

```json
{
  "m.agent": {
    "agent_card": { ... },
    "credentials": [
      { "id": "urn:uuid:...", "type": "CapabilityCredential", ... }
    ]
  }
}
```

### 3.3 Verification

The verifying agent MUST:
1. Check the credential signature against the issuer's public key
2. Verify the issuer is a trusted authority
3. Check the credential has not expired
4. Check the credential has not been revoked
5. Validate that the credential subject matches the presenting agent's DID

### 3.4 Revocation

Credentials can be revoked by the issuer. Agents check revocation status via:

```
GET https://ourdid.com/api/v1/credentials/{credential_id}/status
```

---

## 4. Trust Scoring

### 4.1 Score Computation

```
trust_score = Σ (credential_quality × issuer_reputation) / total_credentials
```

Where:
- `credential_quality` = 0.0–1.0 based on verification rigor
- `issuer_reputation` = 0.0–1.0 based on issuer trust

### 4.2 Issuer Reputation

| Issuer | Reputation | Verification Method |
|--------|:--:|---------------------|
| OurDID Core | 1.0 | Automated test suites + human review |
| Verified Organization | 0.8 | Organizational attestation |
| Peer Agent | 0.4 | Peer endorsement |
| Self-signed | 0.1 | Self-attestation |

### 4.3 Trust Registry

A trust registry maintains the list of trusted issuers and their reputation scores. The registry is queryable by any ARMP agent:

```
GET https://ourdid.com/api/v1/trust/issuers
```

```json
{
  "issuers": [
    {
      "did": "did:ourdid:AGNT8A...",
      "name": "OurDID Core Authority",
      "reputation": 1.0,
      "supported_credential_types": ["CapabilityCredential", "IdentityCredential"]
    }
  ]
}
```

---

## 5. Reference Implementation

Python: `armp_trust.py` — 372 lines
- `VerifiableCredential` dataclass with W3C-compliant schema
- `TrustRegistry` class for issuer management
- `VerificationService` for credential validation
- `CredentialIssuer` for issuing new credentials

---

## 6. Security Considerations

### 6.1 Key Management

Issuers MUST protect their signing keys. Key compromise allows an attacker to issue fraudulent credentials.

### 6.2 Replay Protection

Credentials include a nonce or timestamp. Verifiers SHOULD track seen credentials to prevent replay.

### 6.3 Privacy

Credentials presented during negotiation reveal capability information. Agents MAY choose which credentials to present based on the negotiation context.
