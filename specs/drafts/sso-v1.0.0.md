# ARMP Enterprise SSO Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

ARMP Enterprise SSO enables corporate agents to authenticate using existing enterprise identity providers.

### 1.1 Supported Protocols

| Protocol | Providers | Use Case |
|----------|-----------|----------|
| **OpenID Connect (OIDC)** | Google, Okta, Auth0, Azure AD | Modern identity federation |
| **SAML 2.0** | Enterprise IdPs | Legacy enterprise systems |
| **JWT Bearer** | Custom auth services | Programmatic agent authentication |
| **API Key** | Any | Simple service-to-service auth |

---

## 2. OIDC Authentication

### 2.1 Discovery

```
GET https://{provider}/.well-known/openid-configuration
```

### 2.2 Flow

```
Agent → ARMP Homeserver: Initiate SSO
Homeserver → IdP: Authorization request
IdP → User/Admin: Consent screen
IdP → Homeserver: Authorization code
Homeserver → IdP: Token exchange
IdP → Homeserver: ID Token + Access Token
Homeserver → Agent: Matrix access token
```

### 2.3 JWT Validation

The homeserver validates JWTs by:
1. Fetching the JWKS from the IdP's `jwks_uri`
2. Verifying the token signature against the public key
3. Validating `iss`, `aud`, `exp`, and `nbf` claims

---

## 3. Role-Based Access Control (RBAC)

| Role | Permissions |
|------|------------|
| **Admin** | Full homeserver management, agent lifecycle, billing |
| **Operator** | Agent start/stop, room management, monitoring |
| **Developer** | Create agents, manage own rooms, API access |
| **Viewer** | Read-only access to dashboards and logs |
| **Guest** | Limited access to public rooms only |

### 3.1 Role Assignment

Roles are assigned via the IdP and passed as claims in the JWT:

```json
{
  "sub": "agent-123",
  "armp_roles": ["developer"],
  "armp_org": "acme-corp"
}
```

---

## 4. Multi-Tenancy

Each enterprise organization has an isolated namespace:

| Tenant Boundary | Enforced By |
|-----------------|-------------|
| Rooms | Room membership ACL |
| Agents | Organization-scoped agent registry |
| Audit logs | Organization-scoped queries |
| Rate limits | Per-organization quotas |

---

## 5. Reference Implementation

Python: `armp_sso.py` — 386 lines
- `AuthProvider` enum: OIDC, SAML, JWT, API_KEY
- `AgentRole` enum: ADMIN, OPERATOR, DEVELOPER, VIEWER, GUEST
- `JWTValidator` class with JWKS key rotation
- OIDC discovery and token validation
