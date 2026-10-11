"""Data types for the Campus Customs agent team.

Two groups:
  * Pydantic models the agents return (their structured outputs). They are kept
    deliberately small: every field an agent fills in costs output tokens, and
    every field a parent agent reads costs input tokens.
  * Plain dataclasses that carry run-time state (shared usage budget, delegation
    chain, audit buffer) into agents via PydanticAI dependency injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
ALL_AGENTS: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

ProposalKind = Literal["invoice", "rent", "purchase_order"]


# --------------------------------------------------------------------------- shared pieces


class ProposalRef(BaseModel):
    """A payment or purchase order that was PREPARED for a human. Nothing here is paid."""

    proposal_id: Optional[int] = Field(None, description="payment_proposals id from the MCP tool")
    kind: ProposalKind
    amount: float
    created: bool = Field(description="False if the MCP tool refused (e.g. not enough free cash)")
    blocked_by_invoice_ids: list[int] = Field(
        default_factory=list,
        description="Open vendor invoices that must be paid before this purchase order can ship",
    )
    note: str = Field("", description="One short line: what it is for, or why it was refused")


class DraftMessage(BaseModel):
    """A DRAFT reply. Never sent: the team has no way to email or call anyone."""

    to: str
    subject: str
    body: str
    status: Literal["draft_only"] = "draft_only"


# --------------------------------------------------------------------------- agent outputs


class VendorOption(BaseModel):
    vendor_id: int
    name: str
    lead_days: int
    can_ship_now: bool = Field(description="False if the vendor has any unpaid open invoice")
    blocked_by_invoice_ids: list[int] = Field(default_factory=list)
    fits_product: bool = Field(description="Judgement from the vendor's specialty text")


class InventoryReport(BaseModel):
    sku: str
    size: str
    qty_on_hand: int
    qty_needed: int
    shortfall: int
    restock_options: list[VendorOption] = Field(default_factory=list)
    summary: str = Field(description="At most 40 words")


class AccountingReport(BaseModel):
    checking_balance: Optional[float] = None
    available_after_commitments: Optional[float] = Field(
        None, description="Balance minus cash already reserved by unpaid proposals"
    )
    overdue_invoice_ids: list[int] = Field(default_factory=list)
    margin_per_unit: Optional[float] = None
    break_even_discount_percent: Optional[float] = None
    proposals: list[ProposalRef] = Field(default_factory=list)
    summary: str = Field(description="At most 40 words")


class FacilitiesReport(BaseModel):
    lease_id: int
    monthly_rent: float
    next_due: str
    days_until_due: int
    rent_affordable_alone: bool
    rent_and_open_invoices_affordable: bool
    summary: str = Field(description="At most 40 words")


class CustomerServiceReport(BaseModel):
    drafts: list[DraftMessage]
    summary: str = Field(description="At most 25 words")


class BossDecision(BaseModel):
    ticket_id: int
    status: Literal["ready_pending_human_approval", "resolved", "blocked", "needs_info"]
    decision: str = Field(description="What we will do, in 1-3 sentences")
    rationale: str = Field(description="Why, citing the numbers that drove it; at most 60 words")
    pending_human_approvals: list[ProposalRef] = Field(default_factory=list)
    drafts: list[DraftMessage] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- run-time state


@dataclass
class TeamSession:
    """Lives for the whole process: the MCP toolset, shared read cache, audit file."""

    read_cache: dict[tuple[str, str], Any] = field(default_factory=dict)
    cache_hits: int = 0
    mcp_calls: int = 0


@dataclass
class TicketRun:
    """Everything shared by every agent working on ONE ticket (boss + all delegates)."""

    run_id: str
    ticket_id: Optional[int]
    session: TeamSession
    usage: Any  # pydantic_ai.usage.RunUsage, shared so the budget covers the whole team
    limits: Any  # pydantic_ai.usage.UsageLimits
    max_delegations: int
    max_depth: int
    delegations: int = 0
    seq: int = 0
    audit_buffer: list[dict] = field(default_factory=list)
    delegation_cache: dict[tuple[str, str], dict] = field(default_factory=dict)
    cache_hit_tool_call_ids: set[str] = field(default_factory=set)


@dataclass
class AgentDeps:
    """Per-agent context injected into tools and hooks via RunContext.deps."""

    run: TicketRun
    agent: AgentName
    chain: tuple[AgentName, ...]  # who is waiting on whom, root first, ending with this agent
    depth: int
    delegated_by: Optional[AgentName] = None


# --------------------------------------------------------------------------- API request bodies


class ApprovalRequest(BaseModel):
    """Body of the approve/reject routes: the human who clicked the button."""

    approver: str = Field(min_length=1, max_length=80, description="Name of the person approving")


class ResolveRequest(ApprovalRequest):
    """Body of the resolve route: who is closing the ticket, and what they decided."""

    note: str = Field("", max_length=500, description="What the human decided (kept in the audit trail)")
