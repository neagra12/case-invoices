# Galatiq Case: Invoice Processing Automation

## Background

Acme Corp is a PE-backed manufacturing firm losing **$2M/year** on manual invoice processing. Invoices arrive via email as PDFs in messy formats with frequent errors. Staff manually extract data, validate against a legacy inventory database (inconsistent), obtain VP approval (via email chains), and process payment (via a banking API).

**Current pain points:**
- 30% error rate
- 5-day processing delays
- Frustrated stakeholders

## Objective

Build a **multi-agent system** that automates the end-to-end invoice processing workflow. The system must run as a working prototype — not just designs or slides.

## Workflow

The system should handle four stages:

1. **Ingestion** — Extract structured data from invoice documents (PDFs, text files). Fields include: Vendor, Amount, Items (with quantities), and Due Date. Expect unstructured text, typos, missing data, and potentially fraudulent entries.

2. **Validation** — Verify extracted data against a mock inventory database (SQLite). Flag mismatches such as quantity exceeding available stock or items not found in inventory.

3. **Approval** — Simulate VP-level review with rule-based decision-making (e.g., invoices over $10K require additional scrutiny). The agent should reason through approval/rejection with a reflection or critique loop.

4. **Payment** — If approved, call a mock payment function. If rejected, log the rejection with reasoning.

## Technical Requirements

- **LLM Integration**: Use xAI's Grok as the core reasoning engine (via the xAI API at https://grok.x.ai). Other models are acceptable if you don't have an API key.
- **Multi-Agent Orchestration**: Use a framework such as LangGraph, CrewAI, AutoGen, or a custom solution.
- **Agent Capabilities**: Function calling / tool use, structured outputs, and self-correction loops.
- **Runtime**: Assume no internet for external APIs — simulate everything locally.
- **Tech Stack**: Python (preferred), with libraries like `langchain`, `crewai`, `autogen`, `pdfplumber`, `PyMuPDF`, etc. Run locally — no cloud deployment.

## Provided Resources

### Mock Invoice Data

Sample invoices are provided in the `data/invoices/` directory in various formats (PDF, CSV, JSON, TXT). Use these as inputs for testing. The data intentionally includes a mix of clean entries and problematic ones — identifying and handling issues is part of the challenge.

### Mock Inventory Database (Required Setup)

Before running the system, you **must** create a local SQLite database that the validation agent will check invoices against. The sample invoices in `data/invoices/` reference specific items and quantities — your database needs to contain matching inventory records so the validation stage can flag mismatches, out-of-stock items, and unknown products.

Below is a starter schema and seed data that covers the core items referenced across the provided invoices:

```python
import sqlite3

conn = sqlite3.connect('inventory.db')  # Persist to file so all agents can access it
cursor = conn.cursor()

cursor.execute('CREATE TABLE IF NOT EXISTS inventory (item TEXT PRIMARY KEY, stock INTEGER)')
cursor.execute("""
    INSERT INTO inventory VALUES
    ('WidgetA', 15),
    ('WidgetB', 10),
    ('GadgetX', 5),
    ('FakeItem', 0)
""")
conn.commit()
```

**Why this matters:** The sample invoices are designed to test your validation logic against this database. For example:

| Scenario | Invoice | What should happen |
|---|---|---|
| Normal order within stock | INV-1001, INV-1004, INV-1006 | Items found, quantities valid — passes validation |
| Quantity exceeds stock | INV-1002 (requests 20× GadgetX, only 5 in stock) | Flagged as stock mismatch |
| Fraudulent / zero-stock item | INV-1003 (references FakeItem, 0 stock) | Flagged as out of stock or suspicious |
| Item not in database at all | INV-1008 (SuperGizmo, MegaSprocket), INV-1016 (WidgetC) | Flagged as unknown item |
| Invalid data | INV-1009 (negative quantity) | Flagged as data integrity issue |

You may extend the seed data with additional items or columns (e.g., unit price, category) to support richer validation — the above is the minimum needed to exercise the provided test invoices. If you want your system to also validate pricing or vendor information, consider adding tables for those as well.

### Mock Payment API

```python
def mock_payment(vendor, amount):
    print(f"Paid {amount} to {vendor}")
    return {"status": "success"}
```

### Grok API Setup

```python
from xai import Grok

client = Grok(api_key="your_key")
response = client.chat.completions.create(
    model="grok-3",
    messages=[{"role": "user", "content": "Reason about this..."}]
)
```

## Running the System

The system should be executable from the command line:

```bash
python main.py --invoice_path=data/invoices/invoice1.txt
```

Output should include structured logs and results.

## Evaluation Criteria

- **Functionality** — Does the system work end-to-end?
- **Code Quality** — Clean, testable, well-structured code with error handling and observability
- **Agentic Sophistication** — LLM integration, multi-agent flow, tool use, self-correction loops
- **Shipping Mindset** — Valuable MVP delivered under ambiguity; scope ruthlessly cut where needed
- **Presentation** — Clear translation of technical decisions to business impact
- **Above/Beyond** - Have you made it your own? Implemented additional features that make the solution feel great? Expanded assumptions? Added to test cases?
- **UI/UX** - Users will understand and enjoy using this system.

---

# Implementation

## What Was Built

A fully working, end-to-end multi-agent invoice processing system using **LangGraph** for orchestration and **xAI Grok-3** as the reasoning engine. The system handles all four pipeline stages — ingestion, validation, approval, and payment — with no manual intervention required.

```
Invoice File
     │
     ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  INGESTION  │────▶│  VALIDATION  │────▶│   APPROVAL   │────▶│   PAYMENT   │
│             │     │              │     │              │     │             │
│ Format-     │     │ Inventory DB │     │ LLM + self-  │     │ Mock API +  │
│ aware parse │     │ checks +     │     │ critique     │     │ SQLite      │
│ + LLM norm  │     │ dupe detect  │     │ reflection   │     │ audit log   │
│ + retry     │     │              │     │ loop         │     │             │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
     │ error              │ duplicate          │ rejected
     └──────────────────▶ END ◀───────────────┘
```

---

## Setup & Installation

**1. Clone and install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure your API key**

Copy `.env.example` to `.env` and add your key:
```bash
cp .env.example .env
```
```env
XAI_API_KEY=your_xai_key_here
# Fallback: OPENAI_API_KEY=your_openai_key_here
```

**3. Initialise the database**
```bash
python setup_db.py
```
This creates `inventory.db` with the inventory table and a `processed_invoices` table for duplicate detection and audit logging. Re-run at any time to reset to a clean state.

---

## How to Run

**Single invoice (CLI)**
```bash
python main.py --invoice_path data/invoices/invoice_1001.txt
python main.py --invoice_path data/invoices/invoice_1003.txt --verbose
```

**Batch — all 16 test invoices**
```bash
python main.py --batch data/invoices/
```
Exports a `batch_results.json` summary on completion.

**Streamlit UI**
```bash
streamlit run ui/app.py
```
Open `http://localhost:8501`. Supports file upload, sample invoice picker, batch run, and processing history.

> **Testing tip — Reset History:** The system records every processed invoice in SQLite for duplicate detection. If you re-run the same invoice (e.g. after testing), it will be flagged as a duplicate and rejected. To clear the audit log between test runs, click the **🗑️ Reset** button in the top-right of the UI (beside the Deploy button), or re-run `python setup_db.py` from the terminal. This does not affect inventory stock levels.

---

## Agent Architecture

### 1. Ingestion Agent (`agents/ingestion.py`)

Converts any invoice file into a validated `InvoiceData` Pydantic model.

**Two-stage approach:**
- **Stage 1 — format-aware parsing** (`tools/parsers.py`): extracts clean intermediate text/structure from 7 supported formats without LLM cost: `TXT`, `JSON` (including nested vendor objects), `CSV-columnar`, `CSV-key-value`, `XML`, `PDF` (via pdfplumber), and plain-text email bodies (detected by `From:`/`Subject:` headers).
- **Stage 2 — LLM normalisation**: Grok-3 maps the intermediate text to a strict JSON schema with field-level instructions for item name normalisation, date parsing, and currency handling.

**Self-correction loop**: If the LLM output fails schema validation or Pydantic coercion, the agent retries up to 2 times, feeding the validation error back into the prompt so Grok can fix its own output.

**Heuristic anomaly detection** runs post-extraction and flags: fraud language (`urgent`, `wire transfer`, `pay immediately`, etc.), non-USD currency, missing vendor, negative quantities, OCR artifacts (letter O in numeric contexts), and math mismatches (accounting for tax: `line_items_sum + tax ≈ total`).

### 2. Validation Agent (`agents/validation.py`)

Validates the extracted data against the SQLite inventory database.

- **Duplicate detection**: checks `processed_invoices` table; if a revision is detected (e.g. `INV-1004_revised`), issues a WARNING instead of a hard rejection so a human can review.
- **Required-field checks**: vendor, due date, positive total, at least one line item.
- **Inventory checks with aggregation**: quantities for the same item across multiple rows are summed before checking stock — critical for INV-1013 where GadgetX appears across 4 rows totalling 9 units against a stock of 5.
- **Fuzzy item name matching**: strips spaces and lowercases before lookup (`"Widget A"` → `"WidgetA"`) to handle OCR variants.
- Severity levels: `error` (blocks approval), `warning` (flags for review), `info` (logged only).

### 3. Approval Agent (`agents/approval.py`)

Simulates VP-level review with an LLM reasoning and reflection loop.

- **Fast-path auto-approve**: invoices with no errors, no fraud flags, and total ≤ $10,000 are approved without an LLM call — keeps latency low for routine invoices.
- **High-value scrutiny**: invoices over $10,000 trigger an enhanced review prompt that explicitly weighs the financial risk.
- **Reflection loop**: the agent makes an initial decision, then runs a second *self-critique* prompt that challenges its own reasoning and may revise the verdict. This catches edge cases where the first pass is overconfident or too conservative.

### 4. Payment Agent (`agents/payment.py`)

Closes the loop regardless of approval outcome.

- **Approved**: calls `mock_payment()` and records the invoice in `processed_invoices` with `status=paid`.
- **Rejected**: records with `status=rejected` and logs the full rejection reasoning.
- Both paths write to the audit log, ensuring the database is always complete.

---

## Test Invoice Coverage

All 16 provided invoices are handled and verified:

| Invoice | Format | Scenario | Expected Outcome |
|---|---|---|---|
| INV-1001 | TXT | Standard clean invoice | ✅ PAID |
| INV-1002 | TXT | GadgetX qty 20 vs stock 5 | ❌ REJECTED — exceeds stock |
| INV-1003 | TXT | FakeItem (0 stock) + fraud language | ❌ REJECTED — zero stock + fraud signals |
| INV-1004 | JSON | Clean invoice with tax | ✅ PAID |
| INV-1004_revised | JSON | Revision of already-processed invoice | ⚠️ WARNING — revision flagged, proceeds for review |
| INV-1005 | JSON | Nested vendor object, high value >$10K, GadgetX exceeds stock | ❌ REJECTED — stock mismatch |
| INV-1006 | CSV | Key-value CSV layout (`field,value` rows) | ✅ PAID |
| INV-1007 | CSV | Columnar CSV (one item per row) | ✅ PAID |
| INV-1008 | TXT | Email body format, unknown items (SuperGizmo, MegaSprocket) | ❌ REJECTED — unknown items |
| INV-1009 | JSON | Negative quantity, missing vendor, negative total | ❌ REJECTED — multiple data errors |
| INV-1010 | TXT | Same item on multiple rows, shipping line, tax | ✅ PAID |
| INV-1011 | PDF | Clean PDF invoice | ✅ PAID |
| INV-1012 | PDF | PDF with OCR artefacts (letter O in numbers) | ⚠️ Flagged, processed with warnings |
| INV-1013 | JSON/PDF | Split quantities across 8 rows; GadgetX total 9 > stock 5 | ❌ REJECTED — aggregate stock exceeded |
| INV-1014 | XML | XML invoice format | ✅ PAID |
| INV-1015 | CSV | Columnar CSV with totals footer rows | ✅ PAID |
| INV-1016 | JSON | Unknown item (WidgetC — not in inventory) | ❌ REJECTED — unknown item |

---

## Above & Beyond

Features implemented beyond the minimum spec:

**Format support** — 7 distinct invoice parsers covering every real-world format encountered: plain text, JSON (including nested vendor objects), two CSV layouts, XML, PDF, and raw email bodies. The parser auto-detects format and routes accordingly.

**Aggregate stock checking** — Validation sums quantities per item across all line rows before checking inventory. This correctly catches INV-1013 where GadgetX is split across 4 entries (5 + 3 + 1 = 9 units against stock of 5). A naive per-row check would pass it.

**Revision detection** — INV-1004_revised is detected as a revision of an already-processed invoice. Instead of hard-rejecting as a duplicate, the system issues a warning and passes it through for human review — matching real AP workflow.

**Fraud signal detection** — The ingestion agent scans raw text for 8 urgency/fraud patterns (`wire transfer`, `pay immediately`, `avoid penalties`, etc.) and surfaces them as flags that feed into the approval decision.

**OCR artifact detection** — Regex scan for letter O/o appearing in numeric contexts (e.g., `3,5O0.00`) flags potential OCR corruption from scanned PDFs.

**Self-correction loop** — Ingestion retries up to 2× on schema validation failure, passing the specific error back to Grok so it can fix the extraction rather than starting from scratch.

**Reflection/critique loop** — The approval agent runs a second LLM call to critique its own initial decision before finalising, reducing false rejections on borderline invoices.

**Streamlit UI** — Full interactive interface with: drag-and-drop file upload, sample invoice picker, 4-stage pipeline visualisation, per-tab breakdown (Invoice · Validation · Approval · Payment), live inventory check table, confidence bar, risk badge, self-critique expander, batch run mode with aggregate business metrics, and processing history from SQLite.

**CLI batch mode** — `--batch` flag processes an entire directory, prints a summary table, and exports `batch_results.json`.

**Audit database** — Every processed invoice (paid or rejected) is written to SQLite with timestamp, amount, vendor, and status — providing a persistent audit trail beyond the session.

---

## Design Decisions

**Why LangGraph?** StateGraph gives a clean separation between agent logic and routing logic. The `operator.add` reducer on `processing_log` means each agent appends to the log without overwriting — no state merge bugs.

**Why two-stage parsing?** Feeding raw PDFs or email bodies directly to the LLM is expensive and inconsistent. The format-specific parser handles structural extraction cheaply; the LLM only handles semantic normalisation (dates, names, amounts). This also makes the system resilient to LLM API failures — the parse step always succeeds.

**Why `import tools.llm as llm` not `from tools.llm import chat_json`?** The module-level import pattern ensures `unittest.mock.patch('tools.llm.chat_json')` intercepts calls correctly. Direct function imports create a local binding that bypasses the patch.

**Why always route to the payment agent on rejection?** Rejected invoices still need to be recorded in the audit database. Routing rejections directly to END would skip that step, leaving the audit log incomplete and allowing the same invoice to pass duplicate detection on a resubmission.
