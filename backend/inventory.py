"""Inventory agent. Behaviour lives in prompts/inventory.md; this file declares its identity, output type, and the MCP tools it may use."""

from models import InventoryReport
from team import AgentSpec

SPEC = AgentSpec(
    name="inventory",
    role="stock by SKU+size, shortfalls, vendors that can restock",
    output_type=InventoryReport,
    prompt_file="inventory.md",
    mcp_tools=frozenset(
        {
            "check_stock_and_restock_vendors",
            "get_order_fulfillment_blockers",
        }
    ),
)
