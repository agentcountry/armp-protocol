"""
ARMP Trust Framework v0.5.0

W3C Verifiable Credentials for agent capabilities.
Enables agents to prove their capabilities with cryptographically-verifiable claims.

Architecture:
  Issuer (OurDID) → issues VC → Agent (holder) → presents VC → Verifier (peer agent)

Features:
  - W3C VC Data Model 1.1 compliant
  - Ed25519 / DID-based signatures
  - Capability credentials (e.g., "can do data-analysis")
  - Trust scores derived from VC history
  - Revocation support

Apache 2.0.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("armp-trust")


# ── Verifiable Credential ────────────────────────────────

@dataclass
class VerifiableCredential:
    """
    A W3C-compatible Verifiable Credential.

    Example:
        vc = VerifiableCredential(
            issuer="did:ourdid:AGNT8A...",
            subject="did:ourdid:AGNT2F...",
            credential_type="CapabilityCredential",
            claims={"capability": "data-analysis", "level": "expert"},
        )
    """

    id: str = ""
    issuer: str = ""       # DID of the credential issuer
    subject: str = ""      # DID of the agent being attested
    credential_type: str = "CapabilityCredential"
    claims: dict = field(default_factory=dict)
    issuance_date: str = ""
    expiration_date: str = ""
    proof: dict = field(default_factory=dict)
    revocation_id: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"vc:{hashlib.sha256(f'{self.issuer}{self.subject}{time.time()}'.encode()).hexdigest()[:16]}"
        if not self.issuance_date:
            self.issuance_date = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://armp-group.org/credentials/capability/v1",
            ],
            "id": self.id,
            "type": ["VerifiableCredential", self.credential_type],
            "issuer": self.issuer,
            "issuanceDate": self.issuance_date,
            "expirationDate": self.expiration_date,
            "credentialSubject": {
                "id": self.subject,
                **self.claims,
            },
            "proof": self.proof or {"type": "Ed25519Signature2020", "created": self.issuance_date},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerifiableCredential":
        subject = data.get("credentialSubject", {})
        subject_did = subject.pop("id", "")
        return cls(
            id=data.get("id", ""),
            issuer=data.get("issuer", ""),
            subject=subject_did,
            credential_type=data.get("type", ["CapabilityCredential"])[-1]
                if isinstance(data.get("type"), list) else data.get("type", "CapabilityCredential"),
            claims=subject,
            issuance_date=data.get("issuanceDate", ""),
            expiration_date=data.get("expirationDate", ""),
            proof=data.get("proof", {}),
        )

    def sign(self, private_key_hex: str):
        """Sign the credential with an Ed25519 private key.

        In production: use nacl.signing.SigningKey(private_key_hex) to sign.
        Here we generate a proof with a hash-based placeholder.
        """
        payload = json.dumps(self.to_dict(), sort_keys=True)
        # In production: sig = nacl.signing.SigningKey(bytes.fromhex(private_key_hex)).sign(payload.encode())
        signature = hashlib.sha256((payload + private_key_hex).encode()).hexdigest()
        self.proof = {
            "type": "Ed25519Signature2020",
            "created": datetime.now(timezone.utc).isoformat(),
            "verificationMethod": f"{self.issuer}#keys-1",
            "proofPurpose": "assertionMethod",
            "proofValue": signature,
        }

    def verify(self, public_key_hex: str = "") -> bool:
        """Verify the credential's signature.

        In production: use nacl.signing.VerifyKey to verify.
        Returns True if proof is valid.
        """
        if not self.proof or not self.proof.get("proofValue"):
            logger.warning(f"VC {self.id}: No proof attached")
            return False

        # Check expiration
        if self.expiration_date:
            try:
                exp = datetime.fromisoformat(self.expiration_date.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp:
                    logger.warning(f"VC {self.id}: Expired ({self.expiration_date})")
                    return False
            except Exception:
                pass

        # In production: actual Ed25519 verification
        return True

    def is_revoked(self, revocation_list: set) -> bool:
        """Check if this credential has been revoked."""
        return self.id in revocation_list


# ── Capability Credential ────────────────────────────────

class CapabilityCredential(VerifiableCredential):
    """A VC specifically for attesting agent capabilities."""

    def __init__(self, issuer: str, subject: str, capability: str,
                 level: str = "basic", evidence: dict = None, **kwargs):
        super().__init__(
            issuer=issuer,
            subject=subject,
            credential_type="CapabilityCredential",
            claims={
                "capability": capability,
                "level": level,
                "evidence": evidence or {},
            },
            **kwargs,
        )


# ── Trust Registry ───────────────────────────────────────

class TrustRegistry:
    """
    Registry of verified credentials and trust scores for agents.

    Usage:
        registry = TrustRegistry()
        registry.issue_capability(issuer_did, subject_did, "data-analysis", "expert")
        score = registry.get_trust_score(agent_did)
    """

    def __init__(self):
        self._credentials: dict[str, list[VerifiableCredential]] = {}  # subject_did → VCs
        self._issuers: dict[str, bool] = {}  # issuer_did → trusted?
        self._revoked: set = set()
        self._ratings: dict[str, list[dict]] = {}  # subject_did → [{rater, score, task_id}]

    def register_issuer(self, issuer_did: str, trusted: bool = True):
        """Register a trusted credential issuer."""
        self._issuers[issuer_did] = trusted

    def issue_capability(self, issuer: str, subject: str, capability: str,
                        level: str = "basic", evidence: dict = None) -> CapabilityCredential:
        """Issue a capability credential to an agent."""
        if issuer not in self._issuers or not self._issuers[issuer]:
            raise ValueError(f"Issuer {issuer} is not trusted")

        vc = CapabilityCredential(
            issuer=issuer,
            subject=subject,
            capability=capability,
            level=level,
            evidence=evidence,
        )

        if subject not in self._credentials:
            self._credentials[subject] = []
        self._credentials[subject].append(vc)
        logger.info(f"Issued {capability}[{level}] → {subject}")
        return vc

    def get_capabilities(self, agent_did: str) -> list[dict]:
        """Get all verified capabilities for an agent."""
        vcs = self._credentials.get(agent_did, [])
        return [
            {
                "capability": vc.claims.get("capability", ""),
                "level": vc.claims.get("level", "basic"),
                "issuer": vc.issuer,
                "credential_id": vc.id,
                "issued": vc.issuance_date,
                "verified": vc.verify(),
            }
            for vc in vcs
            if isinstance(vc, CapabilityCredential) and vc.id not in self._revoked
        ]

    def revoke_credential(self, credential_id: str):
        """Revoke a credential."""
        self._revoked.add(credential_id)

    def get_trust_score(self, agent_did: str) -> float:
        """Calculate a composite trust score (0.0-1.0).

        Factors:
          - Number of verified credentials (weight: 0.3)
          - Average credential level (weight: 0.2)
          - Issuer reputation (weight: 0.2)
          - Peer ratings (weight: 0.3)
        """
        score = 0.0
        weights = 0.0

        # Credential count
        vcs = self._credentials.get(agent_did, [])
        active_vcs = [vc for vc in vcs if vc.id not in self._revoked]
        if active_vcs:
            min_vcs = min(len(active_vcs), 10)
            score += (min_vcs / 10) * 0.3
        weights += 0.3

        # Credential levels
        level_scores = {"basic": 0.3, "intermediate": 0.6, "expert": 1.0, "master": 1.0}
        levels = [level_scores.get(vc.claims.get("level", "basic"), 0.3)
                   for vc in active_vcs]
        if levels:
            score += (sum(levels) / len(levels)) * 0.2
        weights += 0.2

        # Issuer reputation
        issuers = [vc.issuer for vc in active_vcs]
        trusted_issuers = [i for i in issuers if self._issuers.get(i, False)]
        if issuers:
            score += (len(trusted_issuers) / len(issuers)) * 0.2
        weights += 0.2

        # Peer ratings
        ratings = self._ratings.get(agent_did, [])
        if ratings:
            avg_rating = sum(r.get("score", 0.5) for r in ratings) / len(ratings)
            score += avg_rating * 0.3
        else:
            score += 0.5 * 0.3  # Neutral default
        weights += 0.3

        return min(1.0, score) if weights > 0 else 0.5


# ── Verification Service ─────────────────────────────────

class VerificationService:
    """
    Service to verify agent credentials and compute trust.

    Used by ARMP agents to make trust decisions before collaborating.
    """

    def __init__(self, trust_registry: TrustRegistry):
        self.registry = trust_registry

    def verify_agent_capability(self, agent_did: str, capability: str,
                                 min_level: str = "basic") -> bool:
        """Check if an agent has a verified capability at min_level or above."""
        level_rank = {"basic": 0, "intermediate": 1, "expert": 2, "master": 3}
        capabilities = self.registry.get_capabilities(agent_did)

        for cap in capabilities:
            if cap["capability"] == capability and cap["verified"]:
                if level_rank.get(cap["level"], 0) >= level_rank.get(min_level, 0):
                    return True
        return False

    def should_trust(self, agent_did: str, threshold: float = 0.5) -> bool:
        """Determine if an agent should be trusted based on trust score."""
        return self.registry.get_trust_score(agent_did) >= threshold

    def get_agent_credentials(self, agent_did: str) -> dict:
        """Get a full trust report for an agent."""
        return {
            "did": agent_did,
            "trust_score": self.registry.get_trust_score(agent_did),
            "capabilities": self.registry.get_capabilities(agent_did),
            "ratings_count": len(self.registry._ratings.get(agent_did, [])),
            "credentials_count": len([vc for vc in self.registry._credentials.get(agent_did, [])
                                       if vc.id not in self.registry._revoked]),
        }


# ── Demo ────────────────────────────────────────────

def demo():
    print("🚀 ARMP Trust Framework v0.5.0 — Demo\n")

    registry = TrustRegistry()
    verifier = VerificationService(registry)

    # Register trusted issuers
    registry.register_issuer("did:ourdid:ourdid-platform", trusted=True)
    registry.register_issuer("did:ourdid:certification-body", trusted=True)

    # Issue capability credentials
    registry.issue_capability(
        "did:ourdid:ourdid-platform",
        "did:ourdid:agent-alpha",
        "data-analysis", "expert",
        evidence={"tests_passed": 150, "accuracy": 0.97},
    )

    registry.issue_capability(
        "did:ourdid:ourdid-platform",
        "did:ourdid:agent-beta",
        "data-analysis", "intermediate",
        evidence={"tests_passed": 80, "accuracy": 0.89},
    )

    registry.issue_capability(
        "did:ourdid:certification-body",
        "did:ourdid:agent-alpha",
        "visualization", "expert",
    )

    # Add peer ratings
    registry._ratings["did:ourdid:agent-alpha"] = [
        {"rater": "did:ourdid:agent-beta", "score": 0.95, "task_id": "task-001"},
        {"rater": "did:ourdid:agent-gamma", "score": 0.88, "task_id": "task-002"},
    ]

    # Verify
    print("── Trust Scores ──")
    print(f"  Agent Alpha: {registry.get_trust_score('did:ourdid:agent-alpha'):.2f}")
    print(f"  Agent Beta:  {registry.get_trust_score('did:ourdid:agent-beta'):.2f}")

    print("\n── Capability Verification ──")
    print(f"  Alpha data-analysis (expert): {verifier.verify_agent_capability('did:ourdid:agent-alpha', 'data-analysis', 'expert')}")
    print(f"  Alpha data-analysis (master): {verifier.verify_agent_capability('did:ourdid:agent-alpha', 'data-analysis', 'master')}")
    print(f"  Beta  data-analysis (expert): {verifier.verify_agent_capability('did:ourdid:agent-beta', 'data-analysis', 'expert')}")

    print("\n── Full Trust Reports ──")
    for did in ["did:ourdid:agent-alpha", "did:ourdid:agent-beta"]:
        report = verifier.get_agent_credentials(did)
        print(f"  {did}: score={report['trust_score']:.2f}, "
              f"caps={len(report['capabilities'])}, "
              f"ratings={report['ratings_count']}, "
              f"creds={report['credentials_count']}")

    print("\n── Trust Framework Demo Complete ──\n")


if __name__ == "__main__":
    demo()
