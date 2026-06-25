"""
ARMP Payment Integration v0.5.0

Agent-to-agent microtransactions via SSHPay / crypto.
Enables agents to pay each other for task completion.

Supported payment methods:
  - SSHPay (native)
  - Solana USDC / SOL
  - Ethereum USDC / ETH
  - Future: Lightning Network

Features:
  - Task escrow (hold payment until verification)
  - Per-task pricing negotiation
  - Payment channels for frequent collaborators
  - Invoice generation

Apache 2.0.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("armp-payments")


# ── Types ────────────────────────────────────────────────

class PaymentStatus(str, Enum):
    PENDING = "pending"       # Not yet paid
    HELD = "held"             # In escrow
    RELEASED = "released"     # Paid to recipient
    REFUNDED = "refunded"     # Returned to payer
    FAILED = "failed"


class Currency(str, Enum):
    USDC_SOL = "USDC-SOL"     # USDC on Solana
    USDC_ETH = "USDC-ETH"     # USDC on Ethereum
    SOL = "SOL"
    USDT_SOL = "USDT-SOL"


# ── Data Models ──────────────────────────────────────────

@dataclass
class PaymentInvoice:
    """An invoice for agent-to-agent payment."""
    invoice_id: str = ""
    payer_did: str = ""
    payee_did: str = ""
    amount: float = 0.0
    currency: Currency = Currency.USDC_SOL
    description: str = ""
    task_id: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: str = ""
    paid_at: str = ""
    tx_hash: str = ""  # Blockchain transaction hash

    def __post_init__(self):
        if not self.invoice_id:
            self.invoice_id = f"inv-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class EscrowPayment:
    """Payment held in escrow until task completion."""
    escrow_id: str = ""
    task_id: str = ""
    payer_did: str = ""
    payee_did: str = ""
    amount: float = 0.0
    currency: Currency = Currency.USDC_SOL
    status: PaymentStatus = PaymentStatus.HELD
    release_condition: str = ""  # e.g., "task_completed", "verification_passed"
    created_at: str = ""
    released_at: str = ""

    def __post_init__(self):
        if not self.escrow_id:
            self.escrow_id = f"escrow-{uuid.uuid4().hex[:16]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class PaymentChannel:
    """A payment channel between two agents for frequent transactions."""
    channel_id: str = ""
    agent_a_did: str = ""
    agent_b_did: str = ""
    balance_a: float = 0.0  # How much A owes B (positive = A owes)
    total_volume: float = 0.0
    currency: Currency = Currency.USDC_SOL
    status: str = "open"  # open, closed, disputed

    def __post_init__(self):
        if not self.channel_id:
            self.channel_id = f"chan-{uuid.uuid4().hex[:16]}"


# ── Payment Service ──────────────────────────────────────

class PaymentService:
    """
    Manages agent-to-agent payments via SSHPay.

    Usage:
        svc = PaymentService(sshpay_endpoint="https://pay.armp-group.org")
        invoice = svc.create_invoice("agent-alpha", "agent-beta", 5.0, Currency.USDC_SOL)
        svc.pay_invoice(invoice.invoice_id, tx_hash="solana-tx-abc123")
    """

    def __init__(self, sshpay_endpoint: str = "https://pay.armp-group.org",
                  solana_rpc: str = "https://api.mainnet-beta.solana.com"):
        self.sshpay_endpoint = sshpay_endpoint
        self.solana_rpc = solana_rpc
        self._invoices: dict[str, PaymentInvoice] = {}
        self._escrows: dict[str, EscrowPayment] = {}
        self._channels: dict[str, PaymentChannel] = {}

    # ── Invoicing ────────────────────────────────────

    def create_invoice(self, payer_did: str, payee_did: str,
                        amount: float, currency: Currency = Currency.USDC_SOL,
                        description: str = "", task_id: str = "") -> PaymentInvoice:
        """Create a payment invoice."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        invoice = PaymentInvoice(
            payer_did=payer_did,
            payee_did=payee_did,
            amount=amount,
            currency=currency,
            description=description,
            task_id=task_id,
        )
        self._invoices[invoice.invoice_id] = invoice
        logger.info(f"Invoice {invoice.invoice_id}: {amount} {currency.value} — {payer_did} → {payee_did}")
        return invoice

    def pay_invoice(self, invoice_id: str, tx_hash: str = "") -> bool:
        """Mark an invoice as paid (after on-chain confirmation).

        In production: verify tx_hash on-chain before marking paid.
        """
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        if invoice.status != PaymentStatus.PENDING:
            raise ValueError(f"Invoice {invoice_id} is {invoice.status.value}")

        invoice.status = PaymentStatus.RELEASED
        invoice.paid_at = datetime.now(timezone.utc).isoformat()
        invoice.tx_hash = tx_hash
        logger.info(f"Invoice {invoice_id}: paid — {tx_hash}")
        return True

    # ── Escrow ───────────────────────────────────────

    def create_escrow(self, task_id: str, payer_did: str, payee_did: str,
                       amount: float, currency: Currency = Currency.USDC_SOL,
                       release_condition: str = "task_completed") -> EscrowPayment:
        """Hold payment in escrow until task completion condition is met."""
        escrow = EscrowPayment(
            task_id=task_id,
            payer_did=payer_did,
            payee_did=payee_did,
            amount=amount,
            currency=currency,
            release_condition=release_condition,
        )
        self._escrows[escrow.escrow_id] = escrow
        logger.info(f"Escrow {escrow.escrow_id}: {amount} {currency.value} held for task {task_id}")
        return escrow

    def release_escrow(self, escrow_id: str) -> bool:
        """Release escrowed payment to the payee."""
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            raise ValueError(f"Escrow {escrow_id} not found")
        if escrow.status != PaymentStatus.HELD:
            raise ValueError(f"Escrow {escrow_id} is {escrow.status.value}")

        escrow.status = PaymentStatus.RELEASED
        escrow.released_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Escrow {escrow_id}: released {escrow.amount} {escrow.currency.value} → {escrow.payee_did}")
        return True

    def refund_escrow(self, escrow_id: str) -> bool:
        """Refund escrowed payment to the payer."""
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            raise ValueError(f"Escrow {escrow_id} not found")

        escrow.status = PaymentStatus.REFUNDED
        logger.info(f"Escrow {escrow_id}: refunded → {escrow.payer_did}")
        return True

    # ── Payment Channels ─────────────────────────────

    def open_channel(self, agent_a: str, agent_b: str,
                      initial_balance_a: float = 0.0) -> PaymentChannel:
        """Open a payment channel between two agents."""
        channel = PaymentChannel(
            agent_a_did=agent_a,
            agent_b_did=agent_b,
            balance_a=initial_balance_a,
        )
        self._channels[channel.channel_id] = channel
        logger.info(f"Channel {channel.channel_id}: {agent_a} ↔ {agent_b}")
        return channel

    def channel_transfer(self, channel_id: str, from_agent: str, amount: float) -> bool:
        """Transfer within a payment channel."""
        channel = self._channels.get(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        if from_agent == channel.agent_a_did:
            channel.balance_a += amount  # A owes more
        else:
            channel.balance_a -= amount  # A owes less

        channel.total_volume += abs(amount)
        logger.info(f"Channel {channel_id}: {from_agent} transferred {amount}")
        return True

    def close_channel(self, channel_id: str) -> dict:
        """Close a payment channel and settle on-chain."""
        channel = self._channels.get(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        channel.status = "closed"
        settlement = {
            "channel_id": channel_id,
            "agent_a_did": channel.agent_a_did,
            "agent_b_did": channel.agent_b_did,
            "net_settlement": channel.balance_a,
            "total_volume": channel.total_volume,
            "currency": channel.currency.value,
        }
        logger.info(f"Channel {channel_id}: closed — net {channel.balance_a} {channel.currency.value}")
        return settlement

    # ── Pricing ──────────────────────────────────────

    @staticmethod
    def suggest_price(task_spec: dict) -> float:
        """Suggest a fair price for a task based on its complexity.

        This is a simple heuristic. In production, use market data.
        """
        description = task_spec.get("description", "")
        capabilities = task_spec.get("capabilities_required", [])

        # Base price
        price = 1.0  # USDC

        # Complexity factors
        for cap in capabilities:
            if "data-analysis" in str(cap).lower():
                price += 3.0
            elif "visualization" in str(cap).lower():
                price += 2.0
            elif "ml" in str(cap).lower() or "machine-learning" in str(cap).lower():
                price += 5.0

        # Length factor
        if len(description) > 200:
            price += 2.0

        return round(price, 2)


# ── Task + Payment Bridge ────────────────────────────────

class TaskPaymentBridge:
    """Bridges ARMP task lifecycle with payments.

    Automates: create task → escrow payment → complete task → release payment.
    """

    def __init__(self, payment_svc: PaymentService):
        self.payment_svc = payment_svc
        self._task_escrows: dict[str, str] = {}  # task_id → escrow_id

    def fund_task(self, task_id: str, payer_did: str, payee_did: str,
                   amount: float, currency: Currency = Currency.USDC_SOL) -> EscrowPayment:
        """Create escrow for a task — holds payment until completion."""
        escrow = self.payment_svc.create_escrow(
            task_id=task_id,
            payer_did=payer_did,
            payee_did=payee_did,
            amount=amount,
            currency=currency,
            release_condition="task_completed",
        )
        self._task_escrows[task_id] = escrow.escrow_id
        return escrow

    def on_task_completed(self, task_id: str) -> bool:
        """Release escrowed payment when task completes."""
        escrow_id = self._task_escrows.get(task_id)
        if not escrow_id:
            logger.warning(f"No escrow found for task {task_id}")
            return False
        return self.payment_svc.release_escrow(escrow_id)

    def on_task_failed(self, task_id: str) -> bool:
        """Refund escrowed payment when task fails."""
        escrow_id = self._task_escrows.get(task_id)
        if not escrow_id:
            return False
        return self.payment_svc.refund_escrow(escrow_id)


# ── Demo ────────────────────────────────────────────

def demo():
    print("🚀 ARMP Payment Integration v0.5.0 — Demo\n")

    svc = PaymentService()
    bridge = TaskPaymentBridge(svc)

    # Create an invoice
    invoice = svc.create_invoice(
        payer_did="agent-alpha",
        payee_did="agent-beta",
        amount=5.0,
        currency=Currency.USDC_SOL,
        description="Churn analysis report — Q3 2026",
        task_id="task-001",
    )
    print(f"Invoice: {invoice.invoice_id} — {invoice.amount} {invoice.currency.value}")
    svc.pay_invoice(invoice.invoice_id, "solana-tx-abc123def456")
    print(f"  Status: {invoice.status.value} (tx: {invoice.tx_hash})")

    # Escrow workflow
    print("\n── Escrow Workflow ──")
    escrow = bridge.fund_task("task-002", "agent-alpha", "agent-gamma", 15.0, Currency.USDC_SOL)
    print(f"  Escrow: {escrow.escrow_id} — {escrow.amount} {escrow.currency.value} held")

    bridge.on_task_completed("task-002")
    print(f"  Task completed → payment released: {escrow.status.value}")

    # Failed task refund
    escrow2 = bridge.fund_task("task-003", "agent-alpha", "agent-delta", 10.0)
    bridge.on_task_failed("task-003")
    print(f"  Task failed → refunded: {escrow2.status.value}")

    # Payment channel
    print("\n── Payment Channel ──")
    channel = svc.open_channel("agent-alpha", "agent-beta", initial_balance_a=0)
    svc.channel_transfer(channel.channel_id, "agent-alpha", 5.0)  # Alpha pays Beta 5
    svc.channel_transfer(channel.channel_id, "agent-beta", 2.0)   # Beta pays Alpha 2
    print(f"  Balance: {channel.balance_a} USDC (A owes B)")
    print(f"  Volume: {channel.total_volume} USDC")

    settlement = svc.close_channel(channel.channel_id)
    print(f"  Settled: net {settlement['net_settlement']} {settlement['currency']}")

    # Price suggestion
    print("\n── Task Pricing ──")
    price = svc.suggest_price({
        "description": "Advanced churn analysis with ML models",
        "capabilities_required": ["data-analysis", "visualization"],
    })
    print(f"  Suggested price: ${price} USDC")

    print("\n── Payment Demo Complete ──\n")


if __name__ == "__main__":
    demo()
