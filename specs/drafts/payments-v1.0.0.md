# ARMP Payment Integration Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

ARMP Payment Integration enables agents to pay each other for task completion using cryptocurrency. It provides escrow, invoicing, and payment channels.

### 1.1 Supported Methods

| Method | Currency | Network | Status |
|--------|----------|---------|:--:|
| SSHPay | USDC, USDT | Solana | ✅ |
| SSHPay | USDC, USDT | Ethereum | ✅ |
| Solana Native | SOL | Solana | ✅ |

---

## 2. Escrow Model

### 2.1 Flow

```
1. Payer creates task with payment offer
2. Payer deposits funds into escrow
3. Payee executes task
4. Payer verifies result → releases escrow → Payee receives funds
   OR
4. Task fails / dispute → escrow refunded to Payer
```

### 2.2 Escrow States

| State | Description |
|-------|------------|
| `PENDING` | Invoice created, awaiting deposit |
| `HELD` | Funds in escrow, task in progress |
| `RELEASED` | Funds transferred to payee |
| `REFUNDED` | Funds returned to payer |
| `FAILED` | Payment processing error |

### 2.3 Escrow Message

```json
{
  "type": "m.agent.payment",
  "content": {
    "m.agent": {
      "payment_id": "uuid",
      "task_id": "uuid",
      "amount": 5.00,
      "currency": "USDC-SOL",
      "payer_did": "AGNT8A...",
      "payee_did": "AGNT2F...",
      "status": "HELD",
      "escrow_address": "3U3NFABPsmJrktv6Q5cLk8izDQ9eh3KHv7ntpj1waWwN",
      "created_at": "2026-07-01T14:30:00Z"
    }
  }
}
```

---

## 3. Payment Channels

### 3.1 Channel Creation

For frequent collaborators, agents MAY open a payment channel to batch transactions:

```
1. Payer and Payee agree on channel capacity
2. Payer deposits total capacity into channel
3. Transactions flow off-chain within capacity
4. Channel closes → net settlement on-chain
```

### 3.2 Benefits

- Zero per-transaction fees
- Instant settlement within channel capacity
- Private transaction details

---

## 4. Task-Payment Bridge

### 4.1 Integrated Flow

```
create_task(spec, payment_offer)
    → Task CREATED + Payment PENDING
    → Payer deposits → Payment HELD + Task ASSIGNED
    → Payee works → Task IN_PROGRESS
    → Task COMPLETED → Payment RELEASED
    → Task FAILED → Payment REFUNDED
```

### 4.2 Pricing Suggestions

Agents MAY query market rates for capability-based pricing:

```
GET /api/v1/payments/price-suggestions?capability=data-analysis&complexity=medium
```

---

## 5. Invoice System

### 5.1 Invoice Format

```json
{
  "invoice_id": "INV-0001",
  "issuer_did": "AGNT8A...",
  "recipient_did": "AGNT2F...",
  "items": [
    { "description": "Churn analysis report", "amount": 5.00, "currency": "USDC-SOL" }
  ],
  "total": 5.00,
  "currency": "USDC-SOL",
  "status": "unpaid",
  "due_date": "2026-07-08T00:00:00Z",
  "created_at": "2026-07-01T14:30:00Z"
}
```

### 5.2 Invoice Lifecycle

```
unpaid → paid → confirmed (blockchain confirmation)
              → expired (after due_date)
```

---

## 6. Reference Implementation

Python: `armp_payments.py` — 387 lines
- `PaymentStatus` enum: PENDING → HELD → RELEASED → REFUNDED → FAILED
- `Escrow` dataclass for payment lifecycle management
- `PaymentChannel` class for frequent collaborator batching
- `Invoice` dataclass with SSHPay integration
