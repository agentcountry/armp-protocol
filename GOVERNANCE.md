# ARMP Protocol Governance

## Model: BDFL → TSC → Foundation

ARMP follows a staged governance model that evolves with the project.

### Phase 1: BDFL (Current)

**Benevolent Dictator:** Agent Country (Iron / Zhang Changwei)

- Final authority on all decisions
- Sets project direction and priorities
- Approves all RFCs
- Manages access to core repositories

### Phase 2: Technical Steering Committee (TSC)

**Trigger:** 5+ regular external contributors from 3+ organizations.

The TSC consists of 3-5 members elected by the contributor community.

- Chair: elected by TSC members for 1-year terms
- Membership: 1-year terms, staggered elections
- Decision: lazy consensus (no objection within 72 hours) → 2/3 majority vote
- Quorum: 50% of members

**First TSC election:** When contributor count reaches the threshold.

### Phase 3: Independent Foundation

**Trigger:** ARMP reaches IETF RFC status or 100+ federation servers.

A nonprofit foundation (e.g., Apache-style or Linux Foundation project) with:

- Board of Directors (5-7 members)
- Project Management Committee (PMC)
- Community-elected representatives
- Corporate sponsors

---

## Decision-Making Process

### RFC Process

All significant changes go through the RFC process:

1. **Proposal** — Open a GitHub issue with `RFC:` prefix
2. **Discussion** — Minimum 2 weeks community review
3. **Decision** — TSC/BDFL approval, rejection, or request for revision
4. **Implementation** — Reference implementation in the SDK
5. **Finalization** — 2+ independent implementations

### Types of Decisions

| Type | Process | Approver |
|------|---------|----------|
| Bug fix | Direct PR | Any maintainer |
| Minor feature | PR + 1 review | Maintainer |
| Protocol change | RFC | TSC/BDFL |
| Breaking change | RFC + deprecation period | TSC/BDFL |
| Governance change | RFC + supermajority (2/3) | TSC |
| License change | RFC + supermajority + legal review | Foundation board |

---

## Roles and Responsibilities

### Maintainers

- Review and merge PRs
- Triage issues
- Release management
- Code quality enforcement

**Current maintainers:** Agent Country team.

**Becoming a maintainer:** 10+ merged PRs, nominated by existing maintainer, approved by TSC.

### Contributors

Anyone who submits a merged PR is a contributor. All contributors are listed in CONTRIBUTORS.md.

### Community Members

Anyone participating in GitHub Issues, Discussions, or Matrix rooms.

---

## Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

### Core Values

1. **Respect** — Treat everyone with dignity. Disagreement is fine; disrespect is not.
2. **Meritocracy** — The best idea wins, regardless of who proposes it.
3. **Transparency** — All decisions and discussions happen in public.
4. **Inclusion** — We welcome contributors regardless of background.
5. **Ship** — Working code over perfect specs. Iterate fast.

---

## Intellectual Property

### License

All code: **Apache License 2.0**

All specifications: **Creative Commons Attribution 4.0 (CC-BY 4.0)**

### Contributor License Agreement (CLA)

**Required for all contributors.** See [CLA.md](CLA.md).

We use a standard Apache-style Individual CLA. The CLA grants the project a license to use your contribution but does NOT transfer copyright ownership.

### Patent Grant

The Apache 2.0 license includes an express patent grant from contributors to users.

---

## Repositories

| Repository | Purpose | Access |
|------------|---------|--------|
| `agentcountry/armp-protocol` | Core protocol + Python SDK | Maintainers |
| `agentcountry/armp-js` | TypeScript SDK | Maintainers |
| `agentcountry/armp-go` | Go SDK | Maintainers |
| `agentcountry/armp-rs` | Rust SDK | Maintainers |
| `agentcountry/armp-specs` | Specification documents | Maintainers |
| `agentcountry/armp-website` | armp-group.org website | Maintainers |

---

## Release Process

1. **Release candidate** — Tagged `vX.Y.Z-rc1`
2. **Testing period** — Minimum 1 week
3. **Final release** — Tagged `vX.Y.Z`
4. **Changelog** — Generated from conventional commits
5. **Announcement** — GitHub Releases, Matrix room, X/Twitter

### Versioning

Follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR**: Breaking protocol changes
- **MINOR**: New features, backward-compatible
- **PATCH**: Bug fixes

---

## Conflict Resolution

1. **Direct discussion** — Talk it out in the RFC thread or Matrix room
2. **Mediation** — TSC chair facilitates
3. **Vote** — TSC majority decides
4. **Escalation** — BDFL (Phase 1) or Foundation board (Phase 3) as final arbiter

---

## Amendments

This governance document can be amended by:

- Phase 1: BDFL decision
- Phase 2: TSC 2/3 majority vote
- Phase 3: Foundation board + community vote

---

*Adopted: 2026-06-28. Apache 2.0.*
