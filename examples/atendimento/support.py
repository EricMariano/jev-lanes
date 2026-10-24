"""Customer-service tools shared by the examples: three tools, three risk levels.

The back office is an in-memory stand-in, so the examples have no side effects outside the
process. The minimum confidences are illustrative, not calibrated defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.tools import tool

from jev_lanes import GatedTool

INTENTS = {
    "orders": "Where is my order, delivery and tracking questions.",
    "billing": "Invoices, charges, refunds and payment problems.",
    "other": "Anything that fits none of the other intents.",
}

INSTRUCTIONS = (
    "You are a customer-service agent. Use the tools to act on the customer's request. "
    "Reply briefly once the tool results are in."
)


@dataclass
class BackOffice:
    """Tiny in-memory back office; ``refunds`` and ``invoices_sent`` record side effects."""

    orders: dict[str, str] = field(default_factory=lambda: {"A100": "shipped", "B200": "packing"})
    refunds: list[str] = field(default_factory=list)
    invoices_sent: list[str] = field(default_factory=list)


def build_tools(office: BackOffice) -> list[GatedTool]:
    @tool
    def order_status(order_id: str) -> str:
        """Look up the status of an order. Read-only."""
        return f"Order {order_id}: {office.orders.get(order_id, 'not found')}"

    @tool
    def send_invoice_copy(order_id: str) -> str:
        """Email the customer a copy of the invoice. Harmless and repeatable."""
        office.invoices_sent.append(order_id)
        return f"Invoice for {order_id} sent."

    @tool
    def refund(order_id: str) -> str:
        """Refund an order in full. Cannot be undone."""
        office.refunds.append(order_id)
        return f"Order {order_id} refunded."

    return [
        GatedTool(order_status, ["orders"], min_confidence=0.50),
        GatedTool(send_invoice_copy, ["billing"], min_confidence=0.70),
        GatedTool(refund, ["billing"], min_confidence=0.90),
    ]
