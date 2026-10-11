"""Boss agent. Behaviour lives in prompts/boss.md; this file declares its identity, output type, and the MCP tools it may use."""

from models import BossDecision
from team import AgentSpec

SPEC = AgentSpec(
    name="boss",
    role="reads the ticket, delegates, makes the final decision",
    output_type=BossDecision,
    prompt_file="boss.md",
    mcp_tools=frozenset(
        {
            "list_open_tickets",
        }
    ),
)
