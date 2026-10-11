"""CustomerService agent. Behaviour lives in prompts/customer_service.md; this file declares its identity, output type, and the MCP tools it may use."""

from models import CustomerServiceReport
from team import AgentSpec

SPEC = AgentSpec(
    name="customer_service",
    role="drafts replies to customers; never sends",
    output_type=CustomerServiceReport,
    prompt_file="customer_service.md",
    mcp_tools=frozenset(
        {
            "list_open_tickets",
        }
    ),
)
