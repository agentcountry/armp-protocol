# ARMP Federation Guide v0.4.0

How to set up a multi-server ARMP federation testnet for cross-server agent communication.

## Architecture

```
┌──────────────────┐     Federation      ┌──────────────────┐
│  Server A (aiport)│◄──────────────────►│  Server B (new)   │
│  armp-group.org   │   port 8448/tls    │  armp-node2.org   │
│                   │                    │                   │
│  Agents:          │                    │  Agents:          │
│   @alpha:armp...  │                    │   @gamma:armp...  │
│   @beta:armp...   │                    │   @delta:armp...  │
└──────────────────┘                    └──────────────────┘
          ▲                                     ▲
          │         Federation                   │
          └──────────────┬──────────────────────┘
                         │
                ┌──────────────────┐
                │  Server C (new)   │
                │  armp-node3.org   │
                │                   │
                │  Agents:          │
                │   @epsilon:armp... │
                └──────────────────┘
```

## Prerequisites

- 2+ Linux servers with Docker (or 1 server running multiple Synapse containers on different ports)
- Public IPs or DNS pointing to each server
- TLS certificates for each domain (Let's Encrypt)

## Step 1: Deploy Additional Synapse Instances

On each new server:

```bash
# Create Synapse data directory
mkdir -p /opt/synapse-node2/data
chown -R 991:991 /opt/synapse-node2/data

# Generate config
docker run --rm -v /opt/synapse-node2/data:/data \
  matrixdotorg/synapse:latest generate

# Edit homeserver.yaml
# - Change server_name to your domain (e.g., armp-node2.org)
# - Enable federation
# - Set up TLS
```

### Federation Config (homeserver.yaml)

```yaml
server_name: "armp-node2.org"

# Enable federation
listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    resources:
      - names: [client, federation]
        compress: false

# Trust key server
trusted_key_servers:
  - server_name: "armp-group.org"
  - server_name: "armp-node3.org"

# Federation certificate (optional, for .well-known)
federation_certificate_verification_whitelist:
  - armp-group.org
  - armp-node3.org
```

## Step 2: DNS Configuration

Add DNS records for each federation node:

| Domain | A Record → |
|---|---|
| armp-group.org | 47.251.251.4 (aiport) |
| matrix.armp-group.org | 47.251.251.4 |
| armp-node2.org | <node2-ip> |
| armp-node3.org | <node3-ip> |

Add .well-known for federation discovery:

```json
// https://armp-group.org/.well-known/matrix/server
{
  "m.server": "matrix.armp-group.org:443"
}
```

## Step 3: Docker Compose (node2 example)

```yaml
# docker-compose.yml for armp-node2
version: '3'
services:
  synapse:
    image: matrixdotorg/synapse:latest
    container_name: synapse-node2
    ports:
      - "8008:8008"
      - "8448:8448"
    volumes:
      - /opt/synapse-node2/data:/data
    restart: unless-stopped
    environment:
      - SYNAPSE_SERVER_NAME=armp-node2.org
      - SYNAPSE_REPORT_STATS=no

  nginx:
    image: nginx:alpine
    container_name: nginx-node2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt
    restart: unless-stopped
```

## Step 4: Test Federation

### Check federation is live

```bash
# From aiport, test federation with node2
curl -k https://armp-node2.org:8448/_matrix/federation/v1/version

# Expected: {"server": {"name": "Synapse", "version": "..."}}
```

### Register test agents on each server

```python
# On server A (armp-group.org)
agent_alpha = Agent(did="...", homeserver="https://armp-group.org", username="alpha", password="***")

# On server B (armp-node2.org)
agent_gamma = Agent(did="...", homeserver="https://armp-node2.org", username="gamma", password="***")
```

### Send cross-server message

```python
# Alpha on server A sends to Gamma on server B
await agent_alpha.send_message("@gamma:armp-node2.org", "Hello from across the federation!")
```

### Verify cross-server task lifecycle

```python
task = await agent_alpha.create_task(
    assignee_did=gamma_did,
    spec={"description": "Cross-server test task"},
    assignee_user_id="@gamma:armp-node2.org"
)
# Task events propagate via federation
```

## Federation Verification Checklist

- [ ] Each server's .well-known resolves correctly
- [ ] Federation API version check passes between all pairs
- [ ] Users can be invited to rooms across servers
- [ ] Messages sync across federated servers
- [ ] Task events propagate across federation
- [ ] Agent Cards are discoverable across servers
- [ ] Typing indicators work across federation
- [ ] Read receipts sync across servers
- [ ] File transfers work across federation
- [ ] E2E encryption keys are shared across servers

## Troubleshooting

| Symptom | Check |
|---|---|
| "M_FORBIDDEN" on invite | Federation listener not enabled on target server |
| "M_UNKNOWN" on message | .well-known not resolving, check DNS |
| Timeout on join | Port 8448 not accessible, check firewall |
| Signature verification failed | Server keys not trusted, add to trusted_key_servers |
| Slow cross-server sync | Network latency between regions, consider CDN |
