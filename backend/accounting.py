"""Accounting agent. Behaviour lives in prompts/accounting.md; this file declares its identity, output type, and the MCP tools it may use."""

from models import AccountingReport
from team import AgentSpec

SPEC = AgentSpec(
    name="accounting",
    role="cash, invoices, margins; prepares payments and purchase orders for human approval",
    output_type=AccountingReport,
    prompt_file="accounting.md",
    mcp_tools=frozenset(
        {
            "get_cash_and_open_invoices",
            "get_margin_for_discount",
            "propose_payment",
            "propose_purchase_order",
        }
    ),
)
