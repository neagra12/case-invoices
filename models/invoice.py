import operator
from datetime import date as _date
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    item: str
    quantity: float
    unit_price: float
    note: Optional[str] = None

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price


class InvoiceData(BaseModel):
    invoice_number: str
    vendor: str
    date: Optional[_date] = None
    due_date: Optional[_date] = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: float
    currency: str = "USD"
    payment_terms: Optional[str] = None
    raw_text: Optional[str] = None
    ingestion_flags: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class ValidationFlag(BaseModel):
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    item: Optional[str] = None


class ValidationResult(BaseModel):
    passed: bool
    flags: list[ValidationFlag] = Field(default_factory=list)
    is_duplicate: bool = False


class ApprovalResult(BaseModel):
    approved: bool
    requires_scrutiny: bool
    reasoning: str
    critique: str
    final_decision: str  # human-readable summary


class PaymentResult(BaseModel):
    status: str  # "paid" | "rejected" | "error"
    detail: str
    vendor: Optional[str] = None
    amount: Optional[float] = None


# LangGraph workflow state
# processing_log uses operator.add reducer so each node appends rather than replaces
class WorkflowState(dict):
    """
    TypedDict-compatible state for LangGraph.
    Keys:
      invoice_path     : str
      raw_text         : str
      invoice_data     : dict | None   (InvoiceData.model_dump())
      validation_result: dict | None   (ValidationResult.model_dump())
      approval_result  : dict | None   (ApprovalResult.model_dump())
      payment_result   : dict | None   (PaymentResult.model_dump())
      processing_log   : list[str]     (appended by each node)
      error            : str | None
      retries          : int
    """
