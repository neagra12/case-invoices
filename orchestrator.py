"""
LangGraph orchestration graph.

Flow:
  ingest → validate → approve → pay → END
           │ (duplicate)            │
           └──────────────→ END  ←──┘ (rejected)
"""

import operator
from typing import Annotated, Any, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

import agents.approval as approval_agent
import agents.ingestion as ingestion_agent
import agents.payment as payment_agent
import agents.validation as validation_agent


# ── State ──────────────────────────────────────────────────────────────────────

class WorkflowState(TypedDict):
    invoice_path: str
    raw_text: str
    invoice_data: Optional[dict]
    validation_result: Optional[dict]
    approval_result: Optional[dict]
    payment_result: Optional[dict]
    # operator.add reducer: each node appends; list is never replaced wholesale
    processing_log: Annotated[list[str], operator.add]
    error: Optional[str]


# ── Node wrappers ──────────────────────────────────────────────────────────────

def ingest_node(state: WorkflowState) -> dict:
    return ingestion_agent.run(dict(state))


def validate_node(state: WorkflowState) -> dict:
    return validation_agent.run(dict(state))


def approve_node(state: WorkflowState) -> dict:
    return approval_agent.run(dict(state))


def pay_node(state: WorkflowState) -> dict:
    return payment_agent.run(dict(state))


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_ingest(state: WorkflowState) -> str:
    if state.get("error"):
        return END
    return "validate"


def route_after_validate(state: WorkflowState) -> str:
    if state.get("error"):
        return END
    vr = state.get("validation_result") or {}
    if vr.get("is_duplicate"):
        return END
    return "approve"


def route_after_approve(state: WorkflowState) -> str:
    if state.get("error"):
        return END
    # Always go to pay — the payment agent handles both approved and rejected paths
    if state.get("approval_result"):
        return "pay"
    return END


# ── Graph construction ─────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(WorkflowState)

    builder.add_node("ingest",   ingest_node)
    builder.add_node("validate", validate_node)
    builder.add_node("approve",  approve_node)
    builder.add_node("pay",      pay_node)

    builder.set_entry_point("ingest")

    builder.add_conditional_edges(
        "ingest",
        route_after_ingest,
        {"validate": "validate", END: END},
    )
    builder.add_conditional_edges(
        "validate",
        route_after_validate,
        {"approve": "approve", END: END},
    )
    builder.add_conditional_edges(
        "approve",
        route_after_approve,
        {"pay": "pay", END: END},
    )
    builder.add_edge("pay", END)

    return builder.compile()


# Module-level compiled graph (imported by main.py and ui/app.py)
graph = build_graph()


def process_invoice(invoice_path: str) -> dict:
    """
    Run the full pipeline for a single invoice.
    Returns the final WorkflowState dict.
    """
    initial_state: WorkflowState = {
        "invoice_path": invoice_path,
        "raw_text": "",
        "invoice_data": None,
        "validation_result": None,
        "approval_result": None,
        "payment_result": None,
        "processing_log": [],
        "error": None,
    }
    return graph.invoke(initial_state)
