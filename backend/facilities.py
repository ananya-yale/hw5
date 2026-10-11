"""Facilities agent. Behaviour lives in prompts/facilities.md; this file declares its identity, output type, and the MCP tools it may use."""

from models import FacilitiesReport
from team import AgentSpec

SPEC = AgentSpec(
    name="facilities",
    role="lease, rent, and shop-space logistics",
    output_type=FacilitiesReport,
    prompt_file="facilities.md",
    mcp_tools=frozenset(
        {
            "check_rent_affordability",
        }
    ),
)
