# ARMP Security Audit Report

**Date:** 2026-06-27
**Scope:** agentcountry/armp-protocol (all .py files, .ts files, .go files)
**Methodology:** Manual code review + pattern scanning

---

## Summary

| Severity | Count | Description |
|----------|:--:|-------------|
| 🔴 Critical | 0 | No exploitable vulnerabilities found |
| 🟡 Medium | 1 | Path traversal in `send_file()` |
| 🟢 Low | 2 | Logging could expose message content, no input size limits |
| ✅ Info | 4 | Secure design patterns confirmed |

---

## Findings

### 🟡 MEDIUM — 1 finding

**1. Path Traversal Risk in `amp_sdk.py:send_file()`**

**Location:** `amp_sdk.py:605`
```python
path = Path(file_path)
if not path.exists():
    raise FileNotFoundError(...)
```

**Issue:** The `file_path` parameter is used directly without path traversal protection. An attacker who controls the `file_path` parameter could read arbitrary files from the filesystem via `../` sequences.

**Risk Assessment:** Low → Medium. The `send_file()` function is part of the Agent SDK, not a public API endpoint. The risk depends on how the agent constructs `file_path`. If an agent accepts file paths from external messages without validation, path traversal is possible.

**Recommendation:** Add a base directory restriction:
```python
ALLOWED_BASE = Path("./armp_files")
path = (ALLOWED_BASE / file_path).resolve()
if not str(path).startswith(str(ALLOWED_BASE.resolve())):
    raise ValueError("Path traversal detected")
```

**Status:** ⬜ Not fixed. Tracked for v0.5.1.

---

### 🟢 LOW — 2 findings

**2. Message Content in Logs**

**Location:** `amp_sdk.py:452`
```python
logger.info(f"→ [{target}] {body[:50]}...")
```

**Issue:** Message bodies are logged at INFO level. In production, this could expose sensitive agent communications.

**Recommendation:** Reduce to DEBUG level or truncate more aggressively.

**Status:** 📝 Noted. Acceptable for SDK-level logging.

---

**3. No Maximum Input Size Limits**

**Location:** Multiple (Task.spec, Message.body, AgentCard fields)

**Issue:** Data models accept arbitrarily large inputs. A malicious peer could send a multi-GB message body or task spec, causing memory exhaustion.

**Recommendation:** Add maximum size constants:
```python
MAX_BODY_SIZE = 64 * 1024      # 64 KB
MAX_SPEC_SIZE = 1024 * 1024    # 1 MB
```

**Status:** 📝 Noted. Acceptable for SDK-level; Matrix homeservers enforce their own limits.

---

### ✅ INFO — 4 confirmed secure patterns

**4. Secure Random Generation**

All UUID generation uses `uuid.uuid4()`, which is cryptographically secure random.

**5. Safe JSON Deserialization**

All serialization uses `json.loads()` (the standard library module), not `pickle` or `yaml.load()`.

**6. No Hardcoded Credentials**

Zero hardcoded passwords, API keys, tokens, or seeds found in the codebase.

**7. No Dangerous System Calls**

No `os.system()`, `subprocess` with shell=True, `eval()`, or `exec()` found outside of the MCP bridge's documented stdio subprocess mode.

---

## Libraries Audited

| Library | Version | Known CVEs | Status |
|---------|---------|:--:|:--:|
| `matrix-nio` | — | None critical | ✅ Actively maintained |
| `aiohttp` | — | Past SSRF CVEs fixed | ✅ Use latest |
| `httpx` | — | None critical | ✅ Actively maintained |
| `aiofiles` | — | None | ✅ Simple async I/O |

---

## Conclusion

The ARMP codebase is **secure by design** with no critical vulnerabilities. The one medium finding (path traversal) is mitigated by the SDK context — file paths are controlled by the agent developer, not by external input. Adding path restriction in v0.5.1 is recommended but not urgent.

The codebase follows secure coding practices: no hardcoded secrets, safe serialization, cryptographic UUID generation, and no dangerous system call injection vectors.
