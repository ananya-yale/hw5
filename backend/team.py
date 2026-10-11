"""The Campus Customs agent team: model, MCP connection, delegation, and agent loop.

Design in one paragraph
-----------------------
Five PydanticAI agents (boss, inventory, accounting, facilities, customer
service) all run on gpt-6-luna through Portkey. Shop facts only ever come from
the MCP server (mcp_server/server.py) over a single stdio connection; each
agent sees only the MCP tools listed in its own file. Every agent also gets
`ask_<teammate>` tools, so any agent can delegate to any other (full mesh),
with guards that keep it cheap: an agent never asks someone already waiting on
it (no loops), delegation depth and count are capped per ticket, identical
requests are answered from cache, identical MCP reads are served from cache
(cleared by any write), and one shared usage budget covers the whole team.
Every loop step is written to output/audit_trail.json (see audit.py).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pydantic_ai import Agent, RunContext, Tool  # noqa: E402
from pydantic_ai.exceptions import UsageLimitExceeded  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.tools import ToolDefinition  # noqa: E402
from pydantic_ai.usage import RunUsage, UsageLimits  # noqa: E402

import audit  # noqa: E402
from audit import clip, record  # noqa: E402
from models import (  # noqa: E402
    ALL_AGENTS,
    AgentDeps,
    AgentName,
    BossDecision,
    TeamSession,
    TicketRun,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROMPTS_DIR = HERE / "prompts"
SERVER_PATH = ROOT / "mcp_server" / "server.py"

# The assignment allows exactly one model for every agent. It is a constant on
# purpose (no environment override) so no agent can drift to another model.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Low reasoning effort keeps token use down; the work here is lookups and short summaries.
REASONING_EFFORT = "low"

# Per-ticket budget shared by the boss and every delegate.
REQUEST_LIMIT = 30
TOTAL_TOKENS_LIMIT = 150_000
MAX_DELEGATIONS = 8
MAX_DEPTH = 2  # boss = 0, its delegates = 1, their delegates = 2 (who cannot delegate further)

WRITE_TOOLS = {"propose_payment", "propose_purchase_order", "record_human_approval", "pay_approved"}
PROPOSE_TOOLS = {"propose_payment", "propose_purchase_order"}

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")


@dataclass(frozen=True)
class AgentSpec:
    """What each agent file declares. The agent's *behaviour* lives in its prompt file."""

    name: AgentName
    role: str  # one line, shown to teammates in the ask_<name> tool description
    output_type: Any
    prompt_file: str
    mcp_tools: frozenset[str]


def make_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey. The key is read from the environment, never logged.

    Uses the Responses API: Portkey/Azure reject function tools with reasoning on /chat/completions."""
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (expected in the parent .env).")
    client = AsyncOpenAI(
        api_key=api_key, base_url=PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": api_key}
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def _server_env(approval_code: Optional[str]) -> dict[str, str]:
    """Environment for the MCP server process: no Portkey credentials, plus the approval code."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PORTKEY")}
    env.pop("CAMPUS_APPROVAL_CODE", None)
    if approval_code:
        env["CAMPUS_APPROVAL_CODE"] = approval_code
    return env


class Team:
    def __init__(self, approval_code: Optional[str] = None, db_path: Optional[str] = None):
        # The code unlocks the human-only MCP tools (record_human_approval, pay_approved). Only the
        # backend's approve route holds it; it is never given to an agent. None = those tools refuse.
        self.approval_code = approval_code
        self.last_outcome = "not run"
        env = _server_env(approval_code)
        if db_path:
            env["CAMPUS_DB_PATH"] = db_path
        transport = StdioTransport(command=sys.executable, args=[str(SERVER_PATH)], env=env)
        self.toolset = MCPToolset(transport, process_tool_call=self._process_tool_call)
        self.session = TeamSession()
        self.model = make_model()
        self.specs = self._load_specs()
        self.agents: dict[str, Agent] = {name: self._build_agent(spec) for name, spec in self.specs.items()}

    async def __aenter__(self) -> "Team":
        await self.toolset.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.toolset.__aexit__(*exc)

    # ------------------------------------------------------------------ construction

    @staticmethod
    def _load_specs() -> dict[str, AgentSpec]:
        import accounting, boss, customer_service, facilities, inventory  # noqa: E401

        specs = {m.SPEC.name: m.SPEC for m in (boss, inventory, accounting, facilities, customer_service)}
        assert set(specs) == set(ALL_AGENTS)
        return specs

    def _build_agent(self, spec: AgentSpec) -> Agent:
        allowed = spec.mcp_tools
        scoped = self.toolset.filtered(lambda ctx, tool_def, allowed=allowed: tool_def.name in allowed)
        delegate_tools = [self._delegate_tool(other) for other in self.specs.values() if other.name != spec.name]
        return Agent(
            self.model,
            deps_type=AgentDeps,
            instructions=(PROMPTS_DIR / spec.prompt_file).read_text(encoding="utf-8"),
            output_type=spec.output_type,
            toolsets=[scoped],
            tools=delegate_tools,
            model_settings=OpenAIResponsesModelSettings(openai_reasoning_effort=REASONING_EFFORT),
            retries=2,
            name=spec.name,
        )

    def _delegate_tool(self, target: AgentSpec) -> Tool:
        async def delegate(ctx: RunContext[AgentDeps], request: str) -> dict:
            return await self.delegate(ctx, target.name, request)

        async def prepare(ctx: RunContext[AgentDeps], tool_def: ToolDefinition) -> ToolDefinition | None:
            d = ctx.deps
            # Hidden (so it costs no schema tokens and can't be misused) when the target is already
            # waiting on this agent (cycle), or the depth / per-ticket delegation cap is reached.
            if target.name in d.chain or d.depth + 1 > d.run.max_depth:
                return None
            if d.run.delegations >= d.run.max_delegations:
                return None
            return tool_def

        return Tool(
            delegate,
            name=f"ask_{target.name}",
            description=(
                f"Delegate to the {target.name} agent ({target.role}). It cannot see your conversation, "
                "so put every id, sku, size, and qty it needs in `request`. Ask once, specifically."
            ),
            prepare=prepare,
            takes_ctx=True,
        )

    # ------------------------------------------------------------------ MCP access

    async def _process_tool_call(self, ctx: RunContext[AgentDeps], call_tool: Any, name: str, args: dict) -> Any:
        """Wraps every MCP call an agent makes: stamps proposer, caches reads, clears cache on writes."""
        if name in PROPOSE_TOOLS:
            # Agents can't claim to be someone else or file a proposal under another ticket.
            args = {**args, "proposed_by": ctx.deps.agent, "ticket_id": ctx.deps.run.ticket_id}
        if name in WRITE_TOOLS:
            result = await call_tool(name, args)
            self.session.read_cache.clear()
            self.session.mcp_calls += 1
            return result
        key = (name, json.dumps(args, sort_keys=True, default=str))
        if key in self.session.read_cache:
            self.session.cache_hits += 1
            ctx.deps.run.cache_hit_tool_call_ids.add(ctx.tool_call_id or "")
            return self.session.read_cache[key]
        result = await call_tool(name, args)
        self.session.read_cache[key] = result
        self.session.mcp_calls += 1
        return result

    async def call_mcp_direct(self, name: str, args: dict) -> Any:
        """For the human-facing runner only (approval + payment execution), never for agents."""
        result = await self.toolset.direct_call_tool(name, args)
        if name in WRITE_TOOLS:
            self.session.read_cache.clear()
        return result

    # ------------------------------------------------------------------ delegation + loop

    async def delegate(self, ctx: RunContext[AgentDeps], target: AgentName, request: str) -> dict:
        d = ctx.deps
        run = d.run
        key = (target, " ".join(request.lower().split()))
        if key in run.delegation_cache:
            record(run, d, "delegation_cache_hit", to=target, request=clip(request, audit.MAX_ARGS_CHARS))
            return {**run.delegation_cache[key], "note": "answered from cache (identical earlier request)"}
        run.delegations += 1
        record(run, d, "delegation", to=target, request=clip(request, audit.MAX_ARGS_CHARS))
        sub = AgentDeps(run=run, agent=target, chain=d.chain + (target,), depth=d.depth + 1, delegated_by=d.agent)
        try:
            output = await self.run_loop(target, request, sub)
            payload = output.model_dump(mode="json", exclude_none=True)
        except UsageLimitExceeded as exc:
            payload = {"error": f"team usage budget exhausted: {exc}"}
        except Exception as exc:  # a failed delegate must not crash the boss; report it instead
            payload = {"error": f"{type(exc).__name__}: {exc}"}
        run.delegation_cache[key] = payload
        return payload

    async def run_loop(self, name: AgentName, prompt: str, deps: AgentDeps) -> Any:
        """Run one agent to completion, logging every loop step to the audit buffer."""
        run = deps.run
        agent = self.agents[name]
        record(run, deps, "agent_start", request=clip(prompt, audit.MAX_ARGS_CHARS), model=MODEL_NAME,
               team_usage_so_far=_usage_dict(run.usage))
        try:
            async with agent.iter(prompt, deps=deps, usage=run.usage, usage_limits=run.limits) as agent_run:
                async for node in agent_run:
                    self._log_node(node, deps)
            output = agent_run.result.output
        except Exception as exc:
            record(run, deps, "agent_error", error=clip(f"{type(exc).__name__}: {exc}", audit.MAX_RESULT_CHARS))
            audit.flush(run)
            raise
        record(run, deps, "agent_end", output=clip(output.model_dump(mode="json", exclude_none=True),
                                                   audit.MAX_RESULT_CHARS), team_usage_so_far=_usage_dict(run.usage))
        audit.flush(run)
        return output

    def _log_node(self, node: Any, deps: AgentDeps) -> None:
        run = deps.run
        if Agent.is_model_request_node(node):
            # Tool results (and validation retries) that are being fed back to the model.
            for part in node.request.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name != "final_result":
                    record(run, deps, "tool_result", tool=part.tool_name, call_id=part.tool_call_id,
                           result=clip(part.content, audit.MAX_RESULT_CHARS),
                           cache_hit=True if part.tool_call_id in run.cache_hit_tool_call_ids else None)
                elif isinstance(part, RetryPromptPart):
                    record(run, deps, "retry", tool=part.tool_name,
                           problem=clip(part.content if isinstance(part.content, str) else str(part.content), 500))
        elif Agent.is_call_tools_node(node):
            resp = node.model_response
            calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
            text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
            usage = resp.usage
            for p in calls:
                is_final = p.tool_name == "final_result"
                record(run, deps, "final_output" if is_final else "tool_call", tool=p.tool_name, call_id=p.tool_call_id,
                       args=clip(p.args, audit.MAX_ARGS_CHARS if not is_final else audit.MAX_RESULT_CHARS))
            if text:
                record(run, deps, "model_text", text=clip(text, 1000))
            record(run, deps, "model_response", model=resp.model_name,
                   input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                   requests_so_far=run.usage.requests)
        audit.flush(run)  # write each step out now so the dashboard can show a run while it is in progress

    # ------------------------------------------------------------------ top level

    async def run_ticket(self, ticket_id: int) -> Optional[BossDecision]:
        run = TicketRun(
            run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id, session=self.session, usage=RunUsage(),
            limits=UsageLimits(request_limit=REQUEST_LIMIT, total_tokens_limit=TOTAL_TOKENS_LIMIT),
            max_delegations=MAX_DELEGATIONS, max_depth=MAX_DEPTH,
        )
        deps = AgentDeps(run=run, agent="boss", chain=("boss",), depth=0)
        record(run, None, "run_start", model=MODEL_NAME, request_limit=REQUEST_LIMIT,
               total_tokens_limit=TOTAL_TOKENS_LIMIT, max_delegations=MAX_DELEGATIONS, max_depth=MAX_DEPTH)
        decision: Optional[BossDecision] = None
        outcome = "completed"
        try:
            decision = await self.run_loop("boss", f"Resolve open ticket {ticket_id}.", deps)
        except Exception as exc:
            outcome = f"error: {type(exc).__name__}: {exc}"
        finally:
            record(run, None, "run_end", outcome=clip(outcome, 500), team_usage=_usage_dict(run.usage),
                   delegations=run.delegations, mcp_cache_hits_total=self.session.cache_hits)
            audit.flush(run)
        self.last_run = run
        self.last_outcome = outcome
        return decision


def _usage_dict(u: RunUsage) -> dict:
    return {"requests": u.requests, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "tool_calls": u.tool_calls}
