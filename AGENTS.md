# AGENTS.md — Guidance for AI Agents

## When to Load This Repo

This is the ARMP (Agent Real-time Message Protocol) specification repository. Load it when:
- User asks about ARMP, Agent Real-time Message Protocol, or agent-to-agent real-time communication
- User wants to implement ARMP in an agent or platform
- User asks about the ARMP spec, Agent Card, or DID Binding
- User wants to contribute to the protocol specification

## Architecture

- `specs/drafts/` — Protocol specifications under development
- `specs/accepted/` — Approved specifications
- `specs/final/` — Finalized specifications with multiple implementations
- SDKs live in separate repositories (`agentcountry/armp-python`, etc.)

## Key Conventions

- All content MUST be in English (agentcountry policy)
- Specifications follow RFC-style format with sections, examples, and rationale
- Changes to specs go through the RFC process: Proposal → Draft → Accepted → Final
- Matrix is the transport layer; ARMP extends it with agent-specific event types

## Critical Constraints

- Never reference internal infrastructure (aiport, tfcenter, etc.) in public content
- Never include credentials, tokens, or private keys
- All examples use placeholder data
