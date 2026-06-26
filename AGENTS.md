# AGENTS.md — Guidance for AI Agents

## When to Load This Repo

This is the ARMP (Agent Real-time Message Protocol) specification repository. Load it when:
- User asks about ARMP, Agent Real-time Message Protocol, or agent-to-agent real-time communication
- User wants to implement ARMP in an agent or platform
- User asks about the ARMP spec, Agent Card, or DID Binding
- User wants to contribute to the protocol specification

## Architecture

- `specs/drafts/` — 12 protocol specifications (core v1.0.0 + 8 module specs + 3 legacy)
- `specs/drafts/draft-agentcountry-armp-protocol-00.md` — IETF Internet-Draft
- SDKs: Python (`amp_sdk.py`), TypeScript (`armp-js/`), Go (`armp-go/`), Rust (`armp-rs/`)
- Phase modules: `armp_a2a_bridge.py`, `armp_mcp.py`, `armp_trust.py`, `armp_reputation.py`, `armp_payments.py`, `armp_sso.py`, `armp_audit.py`, `armp_ratelimit.py`, `armp_admin.py`
- Plugins: `langchain_armp/`, `crewai_armp/`
- `tests/` — 35 interop tests (Python SDK)
- `SECURITY.md` — Security audit report
- `FEDERATION.md` — Multi-server federation guide

## Key Conventions

- All content MUST be in English (agentcountry policy)
- Specifications follow RFC-style format with sections, examples, and rationale
- Changes to specs go through the RFC process: Proposal → Draft → Accepted → Final
- Matrix is the transport layer; ARMP extends it with agent-specific event types

## Critical Constraints

- Never reference internal infrastructure (aiport, tfcenter, etc.) in public content
- Never include credentials, tokens, or private keys
- All examples use placeholder data

## Current Status

All 6 phases complete (2026-06-27):
- Phase 1-2: Core protocol + Python SDK + Social features
- Phase 3: Intelligence (negotiation, tasks, discovery, routing) + JS SDK
- Phase 4: Ecosystem (A2A, MCP, LangChain, CrewAI, Federation, Go SDK)
- Phase 5: Trust & Commerce (Trust, Reputation, Payments, SSO, Audit, Rate Limit, Admin)
- Phase 6: Standardization (9 spec docs, Rust SDK, IETF Draft, 35 tests, security audit)
