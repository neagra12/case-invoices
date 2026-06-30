"""
Streamlit UI — Acme Corp Invoice Processing Automation
Run:  streamlit run ui/app.py
"""

import os, sys, sqlite3, tempfile, time
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

# Auto-initialise the database on first boot (required on Streamlit Cloud)
_db = Path(__file__).parent.parent / "inventory.db"
if not _db.exists():
    import setup_db
    setup_db.setup()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Acme Corp — Invoice Automation",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #f1f5f9; }
[data-testid="stMainBlockContainer"] { padding-top: 3rem !important; }

/* Apply Inter ONLY to main content — never touch sidebar to avoid breaking Material Icons arrow */
[data-testid="stMainBlockContainer"] * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Toolbar ── */
header[data-testid="stHeader"] {
    background: #f1f5f9 !important;
    border-bottom: 1px solid #e2e8f0 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebarContent"] { padding-top: 0.75rem !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }


/* ── Status banner ── */
.banner { border-radius:12px; padding:20px 28px; margin-bottom:20px; display:flex; align-items:center; gap:20px; }
.banner-paid     { background:linear-gradient(135deg,#dcfce7,#bbf7d0); border:1px solid #86efac; }
.banner-rejected { background:linear-gradient(135deg,#fee2e2,#fecaca); border:1px solid #fca5a5; }
.banner-error    { background:linear-gradient(135deg,#fef9c3,#fef08a); border:1px solid #fde047; }
.banner-icon { font-size:2.8rem; line-height:1; }
.banner-title { font-size:1.5rem; font-weight:700; margin:0; }
.banner-sub   { font-size:0.9rem; margin:4px 0 0; opacity:0.8; }
.banner-amount { margin-left:auto; text-align:right; }
.banner-amount-val { font-size:1.8rem; font-weight:700; }
.banner-amount-label { font-size:0.75rem; opacity:0.7; text-transform:uppercase; letter-spacing:.05em; }

/* ── Pipeline track ── */
.pipeline { display:flex; gap:0; margin:20px 0; }
.pipe-stage {
    flex:1; padding:14px 16px; position:relative;
    background:#fff; border:1px solid #e2e8f0;
    border-right:none;
}
.pipe-stage:first-child { border-radius:10px 0 0 10px; }
.pipe-stage:last-child  { border-radius:0 10px 10px 0; border-right:1px solid #e2e8f0; }
.pipe-stage.ps-pass { background:#f0fdf4; border-color:#86efac; }
.pipe-stage.ps-fail { background:#fef2f2; border-color:#fca5a5; }
.pipe-stage.ps-warn { background:#fffbeb; border-color:#fde68a; }
.pipe-stage.ps-skip { background:#f8fafc; border-color:#e2e8f0; }
.pipe-num  { font-size:.65rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:#94a3b8; }
.pipe-name { font-size:.9rem; font-weight:700; margin:2px 0; }
.pipe-detail { font-size:.78rem; color:#64748b; }
.pipe-icon { font-size:1.2rem; float:right; margin-top:-2px; }

/* ── Flags ── */
.flag-row { display:flex; gap:8px; align-items:flex-start; padding:8px 12px;
            border-radius:8px; margin-bottom:6px; font-size:.875rem; }
.flag-error   { background:#fef2f2; border-left:3px solid #ef4444; }
.flag-warning { background:#fffbeb; border-left:3px solid #f59e0b; }
.flag-info    { background:#eff6ff; border-left:3px solid #3b82f6; }
.flag-code { font-weight:700; font-size:.75rem; white-space:nowrap; padding-top:1px; }
.flag-error   .flag-code { color:#ef4444; }
.flag-warning .flag-code { color:#f59e0b; }
.flag-info    .flag-code { color:#3b82f6; }

/* ── Risk badge ── */
.risk-badge { display:inline-block; padding:3px 10px; border-radius:20px;
              font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
.risk-low    { background:#dcfce7; color:#166534; }
.risk-medium { background:#fef9c3; color:#713f12; }
.risk-high   { background:#fee2e2; color:#991b1b; }

/* ── Reasoning card ── */
.reason-card { background:#fff; border:1px solid #e2e8f0; border-radius:10px;
               padding:16px 20px; margin:12px 0; }
.reason-card h4 { margin:0 0 8px; font-size:.85rem; text-transform:uppercase;
                  letter-spacing:.06em; color:#64748b; }
.reason-card p { margin:0; font-size:.9rem; line-height:1.6; color:#1e293b; }

/* ── Line items table ── */
.li-table { width:100%; border-collapse:collapse; font-size:.875rem; }
.li-table th { background:#f1f5f9; padding:8px 10px; text-align:left;
               font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; color:#64748b; }
.li-table td { padding:8px 10px; border-bottom:1px solid #f1f5f9; }
.li-table tr:last-child td { border-bottom:none; }
.li-table .amount { text-align:right; font-weight:600; }

/* ── Metric cards ── */
.biz-metric { background:#fff; border:1px solid #e2e8f0; border-radius:10px;
              padding:16px 20px; text-align:center; }
.biz-metric-val { font-size:1.8rem; font-weight:700; margin:4px 0; }
.biz-metric-label { font-size:.78rem; color:#64748b; text-transform:uppercase; letter-spacing:.05em; }

/* ── Sidebar stat ── */
.sb-stat { background:#1e293b; border-radius:10px; padding:12px 16px; margin-bottom:8px;
           border:1px solid #334155; }
.sb-stat-val { font-size:1.4rem; font-weight:800; color:#f8fafc; letter-spacing:-.02em; }
.sb-stat-label { font-size:.68rem; color:#64748b; text-transform:uppercase; letter-spacing:.07em; margin-top:1px; }

/* ── Confidence bar ── */
.conf-bar-wrap { background:#e2e8f0; border-radius:4px; height:8px; margin-top:4px; }
.conf-bar { background:#22c55e; border-radius:4px; height:8px; }

/* ── Invoice detail card ── */
.detail-card { background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; }
.detail-card-title { font-size:.7rem; font-weight:700; text-transform:uppercase;
                     letter-spacing:.08em; color:#94a3b8; margin-bottom:14px; }
.detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px 24px; }
.detail-item-label { font-size:.72rem; color:#94a3b8; text-transform:uppercase;
                     letter-spacing:.05em; margin-bottom:2px; }
.detail-item-val { font-size:.95rem; font-weight:600; color:#1e293b; }
.detail-item-val.missing { color:#ef4444; font-style:italic; font-weight:400; }

/* ── Verdict card ── */
.verdict-approved { background:linear-gradient(135deg,#f0fdf4,#dcfce7);
                    border:1px solid #86efac; border-radius:12px; padding:20px 24px; margin-bottom:16px; }
.verdict-rejected { background:linear-gradient(135deg,#fef2f2,#fee2e2);
                    border:1px solid #fca5a5; border-radius:12px; padding:20px 24px; margin-bottom:16px; }
.verdict-label { font-size:1.3rem; font-weight:700; margin:0 0 4px; }
.verdict-sub   { font-size:.85rem; opacity:.75; margin:0; }

/* ── Receipt card ── */
.receipt { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
           padding:24px; max-width:460px; }
.receipt-header { display:flex; justify-content:space-between; align-items:flex-start;
                  margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid #f1f5f9; }
.receipt-title  { font-size:1rem; font-weight:700; color:#1e293b; margin:0; }
.receipt-badge-paid { background:#dcfce7; color:#166534; font-size:.72rem;
                      font-weight:700; padding:3px 10px; border-radius:20px; }
.receipt-badge-fail { background:#fee2e2; color:#991b1b; font-size:.72rem;
                      font-weight:700; padding:3px 10px; border-radius:20px; }
.receipt-row { display:flex; justify-content:space-between; margin-bottom:10px;
               font-size:.875rem; }
.receipt-row-label { color:#64748b; }
.receipt-row-val   { font-weight:600; color:#1e293b; }
.receipt-amount { font-size:1.6rem; font-weight:700; color:#1e293b;
                  text-align:right; margin-top:16px; padding-top:16px;
                  border-top:2px solid #f1f5f9; }
.receipt-txn { font-size:.72rem; color:#94a3b8; text-align:right; margin-top:4px;
               font-family:monospace; }

/* ── Empty state ── */
.empty-state { text-align:center; padding:48px 24px; }
.empty-state-title { font-size:1.1rem; font-weight:700; color:#1e293b; margin:16px 0 8px; }
.empty-state-sub { font-size:.875rem; color:#64748b; margin:0; }
.how-it-works { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin:32px 0; }
.how-step { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
            padding:20px 16px; text-align:center; }
.how-step-num { width:32px; height:32px; border-radius:50%; display:inline-flex;
                align-items:center; justify-content:center; font-weight:700;
                font-size:.8rem; margin-bottom:10px; }
.how-step-num-1 { background:#eff6ff; color:#2563eb; }
.how-step-num-2 { background:#f0fdf4; color:#16a34a; }
.how-step-num-3 { background:#fef9c3; color:#ca8a04; }
.how-step-num-4 { background:#fdf4ff; color:#9333ea; }
.how-step-name { font-size:.85rem; font-weight:700; color:#1e293b; margin-bottom:4px; }
.how-step-desc { font-size:.75rem; color:#64748b; line-height:1.4; }


/* ── Page heading ── */
.page-heading { margin-bottom: 28px; }
.page-heading-eyebrow {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: .7rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; color: #6366f1;
    background: #eef2ff; border-radius: 20px;
    padding: 3px 10px; margin-bottom: 10px;
}
.page-heading h1 {
    font-size: 2rem; font-weight: 800; margin: 0 0 6px;
    color: #0f172a; letter-spacing: -.03em; line-height: 1.15;
}
.page-heading h1 span {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.page-heading p { margin: 0; font-size: .925rem; color: #64748b; line-height: 1.6; }

/* ── Run pipeline button (primary) ── */
button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.4) !important;
    transition: all .15s ease !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4f46e5, #4338ca) !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.5) !important;
    transform: translateY(-1px) !important;
}


/* ── Custom upload zone (replaces native file uploader chrome) ── */
.custom-upload-zone {
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 28px 20px;
    text-align: center;
    cursor: pointer;
    background: #f8fafc;
    transition: border-color .2s, background .2s;
    user-select: none;
}
.custom-upload-zone:hover {
    border-color: #6366f1;
    background: #eef2ff;
}
.custom-upload-zone-icon { font-size: 1.8rem; margin-bottom: 8px; }
.custom-upload-zone-title { font-weight: 600; color: #1e293b; font-size: .9rem; margin-bottom: 4px; }
.custom-upload-zone-sub { font-size: .78rem; color: #64748b; }

/* Visually hide native uploader chrome but keep it in DOM & functional */
[data-testid="stFileUploadDropzone"] {
    position: absolute !important;
    width: 1px !important; height: 1px !important;
    padding: 0 !important; margin: -1px !important;
    overflow: hidden !important; clip: rect(0,0,0,0) !important;
    border: 0 !important; opacity: 0 !important;
}
[data-testid="stFileUploader"] > div:first-child {
    min-height: 0 !important;
}
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span { display: none !important; }

/* ── Tab styling ── */
[data-testid="stTabs"] [data-testid="stTab"] {
    font-weight: 600;
    font-size: 0.875rem;
}

/* ── Divider color fix in sidebar ── */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── DB helpers ─────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "inventory.db"

def db_stats() -> dict:
    if not DB_PATH.exists():
        return {"total": 0, "paid": 0, "rejected": 0, "paid_amount": 0.0}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM processed_invoices")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM processed_invoices WHERE status='paid'")
    row = cur.fetchone(); paid, paid_amt = row[0], row[1]
    cur.execute("SELECT COUNT(*) FROM processed_invoices WHERE status='rejected'")
    rejected = cur.fetchone()[0]
    conn.close()
    return {"total": total, "paid": paid, "rejected": rejected, "paid_amount": paid_amt}

def db_history(limit: int = 8) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""SELECT invoice_number, vendor, total, status, processed_at
                   FROM processed_invoices ORDER BY processed_at DESC LIMIT ?""", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def db_reset():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM processed_invoices")
    conn.commit()
    conn.close()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:4px 0 16px">
        <div style="font-size:1.05rem;font-weight:800;color:#f8fafc;letter-spacing:-.02em">
            🏭 Acme Corp
        </div>
        <div style="font-size:.72rem;color:#6366f1;font-weight:600;letter-spacing:.06em;
                    text-transform:uppercase;margin-top:2px">
            AP Automation
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    mode = st.radio("View", ["Process Invoice", "Batch Run", "Processing History"],
                    label_visibility="collapsed")
    st.divider()

    # Live stats from DB
    stats = db_stats()
    st.markdown("**Live Metrics**")
    st.markdown(f"""
    <div class="sb-stat">
        <div class="sb-stat-val">{stats['total']}</div>
        <div class="sb-stat-label">Invoices Processed</div>
    </div>
    <div class="sb-stat">
        <div class="sb-stat-val" style="color:#86efac">${stats['paid_amount']:,.0f}</div>
        <div class="sb-stat-label">Cleared for Payment</div>
    </div>
    <div class="sb-stat">
        <div class="sb-stat-val" style="color:#fca5a5">{stats['rejected']}</div>
        <div class="sb-stat-label">Blocked / Rejected</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    show_log = st.toggle("Show agent log", value=False)
    show_raw = st.toggle("Show raw invoice text", value=False)
    st.divider()

# ── Helpers ────────────────────────────────────────────────────────────────────

def pipeline_html(inv, vr, ar, pay, err) -> str:
    def stage(num, name, css, icon, detail):
        return f"""<div class="pipe-stage {css}">
            <span class="pipe-icon">{icon}</span>
            <div class="pipe-num">Step {num}</div>
            <div class="pipe-name">{name}</div>
            <div class="pipe-detail">{detail}</div>
        </div>"""

    # Ingestion
    if err and not inv:
        s1 = stage(1, "Ingestion", "ps-fail", "❌", "Failed")
    elif inv:
        conf = inv.get("confidence", 1.0)
        nf   = len(inv.get("ingestion_flags", []))
        css  = "ps-warn" if nf else "ps-pass"
        icon = "⚠️" if nf else "✅"
        s1   = stage(1, "Ingestion", css, icon, f"Confidence {conf:.0%}" + (f" · {nf} flag(s)" if nf else ""))
    else:
        s1 = stage(1, "Ingestion", "ps-skip", "⬜", "—")

    # Validation
    if vr:
        errors = [f for f in vr.get("flags", []) if f["severity"] == "error"]
        warns  = [f for f in vr.get("flags", []) if f["severity"] == "warning"]
        is_dup = vr.get("is_duplicate", False)
        if is_dup:
            s2 = stage(2, "Validation", "ps-fail", "❌", "Duplicate invoice")
        elif errors:
            s2 = stage(2, "Validation", "ps-fail", "❌",
                       f"{len(errors)} error(s)" + (f", {len(warns)} warning(s)" if warns else ""))
        elif warns:
            s2 = stage(2, "Validation", "ps-warn", "⚠️", f"Passed · {len(warns)} warning(s)")
        else:
            s2 = stage(2, "Validation", "ps-pass", "✅", "All checks passed")
    elif inv:
        s2 = stage(2, "Validation", "ps-skip", "⬜", "—")
    else:
        s2 = stage(2, "Validation", "ps-skip", "⬜", "—")

    # Approval
    if ar:
        approved = ar.get("approved", False)
        scrutiny = ar.get("requires_scrutiny", False)
        detail = ("⚑ High-value scrutiny" if scrutiny else "Auto-approved" if not scrutiny and approved else "Rejected")
        s3 = stage(3, "Approval", "ps-pass" if approved else "ps-fail",
                   "✅" if approved else "❌", detail)
    elif vr:
        s3 = stage(3, "Approval", "ps-skip", "⬜", "—")
    else:
        s3 = stage(3, "Approval", "ps-skip", "⬜", "—")

    # Payment
    if pay:
        status = pay.get("status", "")
        if status == "paid":
            s4 = stage(4, "Payment", "ps-pass", "✅", "Processed")
        else:
            s4 = stage(4, "Payment", "ps-fail", "❌", "Not processed")
    elif ar:
        s4 = stage(4, "Payment", "ps-skip", "⬜", "—")
    else:
        s4 = stage(4, "Payment", "ps-skip", "⬜", "—")

    return f'<div class="pipeline">{s1}{s2}{s3}{s4}</div>'


def banner_html(inv, pay, ar, err) -> str:
    status = (pay.get("status") if pay else None) or ("error" if err and not inv else None)
    vendor   = (inv or {}).get("vendor", "Unknown")
    inv_num  = (inv or {}).get("invoice_number", "—")
    total    = (inv or {}).get("total", 0)
    currency = (inv or {}).get("currency", "USD")

    if status == "paid":
        css   = "banner-paid"
        icon  = "✅"
        title = "Invoice Approved & Paid"
        sub   = f"Payment of {currency} {total:,.2f} cleared for {vendor}"
    elif status == "rejected":
        css   = "banner-rejected"
        icon  = "🚫"
        title = "Invoice Rejected"
        # Business impact statement
        v_flags = [] if not ar else []
        if ar and not ar.get("approved"):
            reason = (ar.get("reasoning") or "")[:120]
            sub = f"Blocked {currency} {total:,.2f} — {reason}..."
        else:
            sub = f"{currency} {total:,.2f} blocked from payment queue"
    elif status == "error":
        css   = "banner-error"
        icon  = "⚠️"
        title = "Processing Error"
        sub   = str(err or "An unexpected error occurred")
    else:
        return ""

    amount_block = f"""<div class="banner-amount">
        <div class="banner-amount-label">Invoice</div>
        <div class="banner-amount-val">{currency} {total:,.2f}</div>
        <div style="font-size:.8rem;opacity:.7">{inv_num}</div>
    </div>"""

    return f"""<div class="banner {css}">
        <div class="banner-icon">{icon}</div>
        <div>
            <p class="banner-title">{title}</p>
            <p class="banner-sub">{sub}</p>
        </div>
        {amount_block if inv else ""}
    </div>"""


def flag_html(flags: list[dict]) -> str:
    if not flags:
        return '<p style="color:#22c55e;font-size:.9rem">✅ No issues found — all checks passed.</p>'
    html = ""
    for f in flags:
        sev  = f.get("severity", "info")
        code = f.get("code", "")
        msg  = f.get("message", "")
        html += f'<div class="flag-row flag-{sev}"><span class="flag-code">{code}</span><span>{msg}</span></div>'
    return html


def line_items_html(items: list[dict], tax=None, total=None, currency="USD") -> str:
    rows = ""
    for li in items:
        qty   = li.get("quantity", 0)
        price = li.get("unit_price", 0)
        amt   = qty * price
        note  = f' <span style="color:#94a3b8;font-size:.8rem">({li["note"]})</span>' if li.get("note") else ""
        rows += f"""<tr>
            <td>{li.get('item','')}{note}</td>
            <td style="color:#64748b">{qty:g} × ${price:,.2f}</td>
            <td class="amount">${amt:,.2f}</td>
        </tr>"""
    footer = ""
    if tax:
        footer += f'<tr><td colspan="2" style="color:#64748b;font-style:italic">Tax</td><td class="amount">${tax:,.2f}</td></tr>'
    if total is not None:
        footer += f'<tr style="font-weight:700;background:#f8fafc"><td colspan="2">{currency} Total</td><td class="amount">${total:,.2f}</td></tr>'
    return f"""<table class="li-table">
        <thead><tr><th>Item</th><th>Qty × Price</th><th style="text-align:right">Amount</th></tr></thead>
        <tbody>{rows}{footer}</tbody>
    </table>"""


def render_result(state: dict, compact: bool = False) -> None:
    inv  = state.get("invoice_data")      or {}
    vr   = state.get("validation_result") or {}
    ar   = state.get("approval_result")   or {}
    pay  = state.get("payment_result")    or {}
    err  = state.get("error")
    log  = state.get("processing_log")   or []

    # Banner
    st.markdown(banner_html(inv or None, pay or None, ar or None, err),
                unsafe_allow_html=True)

    # Pipeline track
    st.markdown(pipeline_html(inv, vr, ar, pay, err), unsafe_allow_html=True)

    if not inv and err:
        st.error(f"**Ingestion failed:** {err}")
        return

    # Details in tabs
    tab_labels = ["📄 Invoice", "🔍 Validation", "🧠 Approval", "💳 Payment"]
    if show_log:
        tab_labels.append("📋 Agent Log")
    tabs = st.tabs(tab_labels)

    # ── Tab 1: Invoice ──────────────────────────────────────────────────────────
    with tabs[0]:
        if inv:
            c1, c2 = st.columns([1, 1])
            with c1:
                # Styled detail card
                def _val(v, missing=False):
                    cls = "detail-item-val missing" if missing else "detail-item-val"
                    return f'<div class="{cls}">{v}</div>'

                vendor    = inv.get("vendor") or None
                due_date  = inv.get("due_date") or None
                conf      = inv.get("confidence", 1.0)
                conf_color = "#22c55e" if conf >= 0.85 else "#f59e0b" if conf >= 0.6 else "#ef4444"

                st.markdown(f"""
                <div class="detail-card">
                  <div class="detail-card-title">Invoice Details</div>
                  <div class="detail-grid">
                    <div>
                      <div class="detail-item-label">Invoice #</div>
                      {_val(inv.get("invoice_number","—"))}
                    </div>
                    <div>
                      <div class="detail-item-label">Vendor</div>
                      {_val(vendor or "missing", missing=not vendor)}
                    </div>
                    <div>
                      <div class="detail-item-label">Date</div>
                      {_val(str(inv.get("date") or "—"))}
                    </div>
                    <div>
                      <div class="detail-item-label">Due Date</div>
                      {_val(str(due_date) if due_date else "missing", missing=not due_date)}
                    </div>
                    <div>
                      <div class="detail-item-label">Currency</div>
                      {_val(inv.get("currency","USD"))}
                    </div>
                    <div>
                      <div class="detail-item-label">Terms</div>
                      {_val(inv.get("payment_terms") or "—")}
                    </div>
                  </div>
                  <div style="margin-top:16px;padding-top:14px;border-top:1px solid #f1f5f9">
                    <div class="detail-item-label">Extraction Confidence — {conf:.0%}</div>
                    <div class="conf-bar-wrap" style="margin-top:6px">
                      <div class="conf-bar" style="width:{conf*100:.0f}%;background:{conf_color}"></div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                st.markdown(
                    line_items_html(
                        inv.get("line_items", []),
                        tax=inv.get("tax"),
                        total=inv.get("total"),
                        currency=inv.get("currency", "USD"),
                    ),
                    unsafe_allow_html=True,
                )

            if inv.get("ingestion_flags"):
                st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)
                iflags = [{"severity":"warning","code":"INGEST","message":f} for f in inv["ingestion_flags"]]
                st.markdown(flag_html(iflags), unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            if show_raw and state.get("raw_text"):
                with st.expander("Raw invoice text"):
                    st.code(state["raw_text"], language=None)

    # ── Tab 2: Validation ───────────────────────────────────────────────────────
    with tabs[1]:
        if vr:
            flags = vr.get("flags", [])
            errors   = [f for f in flags if f["severity"] == "error"]
            warnings = [f for f in flags if f["severity"] == "warning"]
            infos    = [f for f in flags if f["severity"] == "info"]

            if errors or warnings or infos:
                if errors:
                    st.markdown(f"**{len(errors)} error(s) — invoice blocked from auto-approval**")
                st.markdown(flag_html(flags), unsafe_allow_html=True)
            else:
                st.markdown(flag_html([]), unsafe_allow_html=True)

            # Inventory summary table
            if inv.get("line_items"):
                st.markdown("---")
                st.markdown("**Inventory Check**")
                from tools.inventory import check_item
                from collections import defaultdict
                agg: dict = defaultdict(float)
                for li in inv["line_items"]:
                    if li.get("quantity", 0) > 0:
                        agg[li["item"]] += li["quantity"]

                inv_rows = []
                for item, qty in agg.items():
                    r = check_item(item, qty)
                    status_icon = {"ok": "✅", "exceeds_stock": "❌", "zero_stock": "🚫", "unknown": "❓"}.get(r["status"], "—")
                    inv_rows.append({
                        "Item": item,
                        "Requested": f"{qty:g}",
                        "In Stock": str(r["available"]) if r["status"] != "unknown" else "—",
                        "Result": f"{status_icon} {r['status'].replace('_', ' ').title()}"
                    })

                import pandas as pd
                st.dataframe(pd.DataFrame(inv_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Validation stage not reached.")

    # ── Tab 3: Approval ─────────────────────────────────────────────────────────
    with tabs[2]:
        if ar:
            approved   = ar.get("approved", False)
            scrutiny   = ar.get("requires_scrutiny", False)
            risk_level = "high" if not approved else ("medium" if scrutiny else "low")

            # Prominent verdict card
            verdict_css = "verdict-approved" if approved else "verdict-rejected"
            verdict_icon = "✅" if approved else "🚫"
            verdict_text = "Approved for Payment" if approved else "Rejected"
            verdict_sub  = ("Enhanced VP scrutiny applied — invoice exceeds $10,000 threshold"
                            if scrutiny else
                            "Auto-approved — all checks passed within normal parameters"
                            if approved else
                            "Invoice failed one or more approval criteria")
            st.markdown(f"""
            <div class="{verdict_css}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <p class="verdict-label">{verdict_icon} {verdict_text}</p>
                  <p class="verdict-sub">{verdict_sub}</p>
                </div>
                <span class="risk-badge risk-{risk_level}">Risk: {risk_level.upper()}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Reasoning
            st.markdown(
                f'<div class="reason-card"><h4>VP Reasoning</h4><p>{ar.get("reasoning","")}</p></div>',
                unsafe_allow_html=True,
            )

            # Self-critique — the "Above and Beyond" feature
            with st.expander("🔄 Self-Critique Loop — AI second opinion"):
                st.caption(
                    "After the initial decision, the agent critiques its own reasoning "
                    "and may revise. This reflection loop catches edge cases and reduces false rejections."
                )
                st.markdown(
                    f'<div class="reason-card"><h4>Critique</h4><p>{ar.get("critique","")}</p></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Approval stage not reached.")

    # ── Tab 4: Payment ──────────────────────────────────────────────────────────
    with tabs[3]:
        if pay:
            status   = pay.get("status", "")
            vendor   = pay.get("vendor", inv.get("vendor", "—"))
            amount   = pay.get("amount", inv.get("total", 0))
            currency = inv.get("currency", "USD")
            detail   = pay.get("detail", "")
            txn_id   = ""
            if "TXN-" in detail:
                txn_id = "TXN-" + detail.split("TXN-")[-1].strip()

            badge_cls = "receipt-badge-paid" if status == "paid" else "receipt-badge-fail"
            badge_txt = "PAYMENT PROCESSED" if status == "paid" else "PAYMENT BLOCKED"

            st.markdown(f"""
            <div class="receipt">
              <div class="receipt-header">
                <p class="receipt-title">Payment Record</p>
                <span class="{badge_cls}">{badge_txt}</span>
              </div>
              <div class="receipt-row">
                <span class="receipt-row-label">Vendor</span>
                <span class="receipt-row-val">{vendor}</span>
              </div>
              <div class="receipt-row">
                <span class="receipt-row-label">Invoice</span>
                <span class="receipt-row-val">{inv.get("invoice_number","—")}</span>
              </div>
              <div class="receipt-row">
                <span class="receipt-row-label">Currency</span>
                <span class="receipt-row-val">{currency}</span>
              </div>
              {"<div class='receipt-row'><span class='receipt-row-label'>Due Date</span><span class='receipt-row-val'>" + str(inv.get('due_date') or '—') + "</span></div>" if inv.get("due_date") else ""}
              <div class="receipt-amount">{currency} {amount:,.2f}</div>
              {"<div class='receipt-txn'>" + txn_id + "</div>" if txn_id else ""}
              {"<div style='margin-top:14px;padding-top:14px;border-top:1px solid #f1f5f9;font-size:.8rem;color:#64748b'>Rejection logged to AP audit system. No funds transferred.</div>" if status != "paid" else ""}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Payment stage not reached.")

    # ── Tab 5: Agent Log ────────────────────────────────────────────────────────
    if show_log and len(tabs) > 4:
        with tabs[4]:
            st.caption("Structured trace of every agent decision in the pipeline.")
            for line in log:
                colour = "#22c55e" if "[OK]" in line else "#ef4444" if "[FAIL]" in line else "#f59e0b" if "[WARN]" in line else "#94a3b8"
                st.markdown(
                    f'<code style="color:{colour};font-size:.8rem;display:block;padding:2px 0">{line}</code>',
                    unsafe_allow_html=True,
                )


# ── Mode: Process Invoice ──────────────────────────────────────────────────────
def mode_single():
    st.markdown("""
    <div class="page-heading">
        <div class="page-heading-eyebrow">⚡ AI-Powered</div>
        <h1>Process <span>Invoice</span></h1>
        <p>Upload any invoice format — the 4-agent pipeline handles ingestion, validation, approval and payment automatically.</p>
    </div>
    """, unsafe_allow_html=True)

    sample_dir = Path(__file__).parent.parent / "data" / "invoices"
    sample_files = sorted(sample_dir.glob("*")) if sample_dir.exists() else []

    col_up, col_pick = st.columns([1, 1])
    with col_up:
        has_file = bool(st.session_state.get("invoice_upload"))
        if not has_file:
            st.markdown("""
            <div class="custom-upload-zone" onclick="
                var inp = document.querySelector('[data-testid=stFileUploadDropzone] input[type=file]');
                if (!inp) inp = document.querySelector('[data-testid=stFileUploader] input[type=file]');
                if (inp) inp.click();
            ">
                <div class="custom-upload-zone-icon">📄</div>
                <div class="custom-upload-zone-title">Click to browse or drag &amp; drop</div>
                <div class="custom-upload-zone-sub">TXT · JSON · CSV · XML · PDF &nbsp;·&nbsp; up to 200 MB</div>
            </div>
            """, unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "",
            type=["txt", "json", "csv", "xml", "pdf"],
            label_visibility="collapsed",
            key="invoice_upload",
        )
        if uploaded:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;background:#f0fdf4;
                        border:1px solid #86efac;border-radius:10px;padding:12px 16px;margin-top:4px">
                <span style="font-size:1.2rem">✅</span>
                <div>
                    <div style="font-weight:600;color:#166534;font-size:.875rem">{uploaded.name}</div>
                    <div style="font-size:.75rem;color:#16a34a">{uploaded.size:,} bytes · ready to process</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    with col_pick:
        sample_names = ["— or select a sample invoice —"] + [f.name for f in sample_files]
        selected_sample = st.selectbox("Sample", sample_names, label_visibility="collapsed")

    run_btn = st.button("▶  Run Pipeline", type="primary")

    if not run_btn:
        st.markdown("""
        <div class="how-it-works">
          <div class="how-step">
            <div class="how-step-num how-step-num-1">1</div>
            <div class="how-step-name">Ingestion</div>
            <div class="how-step-desc">Parses 7 formats — TXT, JSON, CSV, XML, PDF, email. LLM normalises with self-correction retry.</div>
          </div>
          <div class="how-step">
            <div class="how-step-num how-step-num-2">2</div>
            <div class="how-step-name">Validation</div>
            <div class="how-step-desc">Checks inventory stock, flags duplicates, detects fraud signals and data errors.</div>
          </div>
          <div class="how-step">
            <div class="how-step-num how-step-num-3">3</div>
            <div class="how-step-name">Approval</div>
            <div class="how-step-desc">VP-level LLM review with self-critique reflection loop. >$10K triggers high-value scrutiny.</div>
          </div>
          <div class="how-step">
            <div class="how-step-num how-step-num-4">4</div>
            <div class="how-step-name">Payment</div>
            <div class="how-step-desc">Approved invoices are paid via mock API. All outcomes are logged to the SQLite audit trail.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    if run_btn:
        from orchestrator import process_invoice
        path = None
        if uploaded:
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                path = tmp.name
        elif selected_sample != "— or select a sample invoice —":
            path = str(sample_dir / selected_sample)

        if not path:
            st.warning("Select a sample invoice or upload a file to continue.")
            return

        with st.spinner("Running pipeline — this takes ~15–20s with Grok-3…"):
            t0 = time.time()
            state = process_invoice(path)
            elapsed = time.time() - t0

        st.caption(f"Completed in {elapsed:.1f}s")
        st.divider()
        render_result(state)


# ── Mode: Batch Run ────────────────────────────────────────────────────────────
def mode_batch():
    st.markdown("""
    <div class="page-heading">
        <div class="page-heading-eyebrow">📦 Full Suite</div>
        <h1><span>Batch</span> Processing</h1>
        <p>Run all 16 test invoices through the full pipeline and see aggregate business impact.</p>
    </div>
    """, unsafe_allow_html=True)

    sample_dir = Path(__file__).parent.parent / "data" / "invoices"
    n_files = len([f for f in sample_dir.iterdir()
                   if f.suffix.lower() in {".txt",".json",".csv",".xml",".pdf"}]) if sample_dir.exists() else 0

    col1, col2 = st.columns([1, 4])
    with col1:
        run_btn = st.button("▶  Run All", type="primary", use_container_width=True)
    with col2:
        st.caption(f"{n_files} invoices in `data/invoices/`")

    if not run_btn:
        st.markdown("""
        **What this tests:**
        - ✅ Clean invoices across 7 file formats (TXT, JSON, CSV, XML, PDF, email, key-value CSV)
        - ❌ Stock mismatches, unknown items, negative quantities, fraud signals
        - 🔄 Duplicate detection across the full batch
        - ⚑ High-value scrutiny for invoices over $10,000
        """)
        return

    from orchestrator import process_invoice
    files = sorted([f for f in sample_dir.iterdir()
                    if f.suffix.lower() in {".txt",".json",".csv",".xml",".pdf"}])
    if not files:
        st.error("No invoice files found."); return

    progress_bar = st.progress(0, text="Starting…")
    results = []
    for i, fpath in enumerate(files):
        progress_bar.progress((i+1)/len(files), text=f"Processing {fpath.name}…")
        t0 = time.time()
        state = process_invoice(str(fpath))
        results.append((fpath.name, state, time.time()-t0))
    progress_bar.empty()

    # ── Business impact metrics ────────────────────────────────────────────────
    paid_results  = [(n,s,e) for n,s,e in results if (s.get("payment_result") or {}).get("status")=="paid"]
    rej_results   = [(n,s,e) for n,s,e in results if (s.get("payment_result") or {}).get("status")=="rejected"]
    err_results   = [(n,s,e) for n,s,e in results if s.get("error") and not s.get("invoice_data")]
    fraud_results = [(n,s,e) for n,s,e in results
                     if any(f["code"] in ("FRAUD_SIGNAL","ZERO_STOCK")
                            for f in (s.get("validation_result") or {}).get("flags",[]))]

    paid_total     = sum((s.get("invoice_data") or {}).get("total",0) for _,s,_ in paid_results)
    blocked_total  = sum((s.get("invoice_data") or {}).get("total",0) for _,s,_ in rej_results)
    total_elapsed  = sum(e for _,_,e in results)

    st.markdown("### Business Impact")
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">✅ Cleared</div>
        <div class="biz-metric-val" style="color:#16a34a">{len(paid_results)}</div>
        <div style="font-size:.8rem;color:#64748b">${paid_total:,.0f} processed</div>
    </div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">🚫 Blocked</div>
        <div class="biz-metric-val" style="color:#dc2626">{len(rej_results)}</div>
        <div style="font-size:.8rem;color:#64748b">${blocked_total:,.0f} protected</div>
    </div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">🔴 Fraud / Suspicious</div>
        <div class="biz-metric-val" style="color:#dc2626">{len(fraud_results)}</div>
        <div style="font-size:.8rem;color:#64748b">detected & blocked</div>
    </div>""", unsafe_allow_html=True)
    c4.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">⏱ Processing Time</div>
        <div class="biz-metric-val">{total_elapsed:.0f}s</div>
        <div style="font-size:.8rem;color:#64748b">vs ~{len(results)*5}min manual</div>
    </div>""", unsafe_allow_html=True)

    # ── Results table ──────────────────────────────────────────────────────────
    st.markdown("### All Invoices")
    import pandas as pd

    rows = []
    for fname, state, elapsed in results:
        inv  = state.get("invoice_data") or {}
        pay  = state.get("payment_result") or {}
        vr   = state.get("validation_result") or {}
        err_codes = [f["code"] for f in vr.get("flags",[]) if f["severity"]=="error"]
        status = (pay.get("status") or ("error" if state.get("error") else "—")).upper()
        rows.append({
            "File":        Path(fname).name,
            "Invoice #":   inv.get("invoice_number","?"),
            "Vendor":      (inv.get("vendor") or "?")[:22],
            "Amount":      f"${inv.get('total',0):,.2f}" if inv else "—",
            "Errors":      ", ".join(err_codes) if err_codes else "none",
            "Status":      status,
            "Time":        f"{elapsed:.1f}s",
        })

    def colour_status(val):
        if val == "PAID":     return "background-color:#dcfce7;color:#166534;font-weight:600"
        if val == "REJECTED": return "background-color:#fee2e2;color:#991b1b;font-weight:600"
        return ""

    df = pd.DataFrame(rows)
    st.dataframe(
        df.style.map(colour_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    # ── Per-invoice expandable detail ──────────────────────────────────────────
    st.markdown("### Per-Invoice Detail")
    for fname, state, elapsed in results:
        pay    = state.get("payment_result") or {}
        status = (pay.get("status") or ("error" if state.get("error") else "—")).upper()
        icon   = "✓" if status=="PAID" else "✗" if status=="REJECTED" else "!"
        inv    = state.get("invoice_data") or {}
        label  = f"{icon}  {Path(fname).name}  ·  {inv.get('invoice_number','?')}  ·  ${inv.get('total',0):,.2f}  ·  {status}"
        with st.expander(label):
            render_result(state, compact=True)


# ── Mode: Processing History ───────────────────────────────────────────────────
def mode_history():
    st.markdown("""
    <div class="page-heading">
        <div class="page-heading-eyebrow">🗄️ Audit Log</div>
        <h1>Processing <span>History</span></h1>
        <p>All invoices processed in this session — pulled live from the local SQLite audit database.</p>
    </div>
    """, unsafe_allow_html=True)

    rows = db_history(limit=50)
    if not rows:
        st.markdown("""
        <div class="empty-state">
          <div style="font-size:2.5rem">📭</div>
          <div class="empty-state-title">No invoices processed yet</div>
          <p class="empty-state-sub">Switch to Process Invoice or Batch Run to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Stats header
    h_stats = db_stats()
    hc1, hc2, hc3 = st.columns(3)
    hc1.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">Total Processed</div>
        <div class="biz-metric-val">{h_stats['total']}</div>
    </div>""", unsafe_allow_html=True)
    hc2.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">✅ Paid</div>
        <div class="biz-metric-val" style="color:#16a34a">${h_stats['paid_amount']:,.0f}</div>
    </div>""", unsafe_allow_html=True)
    hc3.markdown(f"""<div class="biz-metric">
        <div class="biz-metric-label">🚫 Rejected</div>
        <div class="biz-metric-val" style="color:#dc2626">{h_stats['rejected']}</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)

    import pandas as pd
    df = pd.DataFrame(rows)
    df["total"] = df["total"].apply(lambda x: f"${x:,.2f}" if x else "—")
    df["processed_at"] = pd.to_datetime(df["processed_at"]).dt.strftime("%Y-%m-%d %H:%M")
    df.columns = ["Invoice #", "Vendor", "Amount", "Status", "Processed At"]

    def colour(val):
        if val == "paid":     return "background-color:#dcfce7;color:#166534;font-weight:600"
        if val == "rejected": return "background-color:#fee2e2;color:#991b1b;font-weight:600"
        return ""

    st.dataframe(df.style.map(colour, subset=["Status"]),
                 use_container_width=True, hide_index=True)



# ── Reset via query param (pure HTML — avoids CSS conflicts with file uploader) ─
if st.query_params.get("reset") == "1":
    db_reset()
    st.query_params.clear()
    st.rerun()

st.markdown("""
<div style="display:flex;justify-content:flex-end;margin-bottom:4px">
  <a href="?reset=1" style="
    display:inline-flex;align-items:center;gap:6px;
    background:linear-gradient(135deg,#ef4444,#dc2626);
    color:#fff !important;text-decoration:none;
    font-family:'Inter',sans-serif;font-size:.8rem;font-weight:600;
    padding:7px 16px;border-radius:8px;
    box-shadow:0 2px 8px rgba(239,68,68,0.3);
    transition:all .15s ease;
  " onmouseover="this.style.background='linear-gradient(135deg,#dc2626,#b91c1c)'"
     onmouseout="this.style.background='linear-gradient(135deg,#ef4444,#dc2626)'">
    🗑️ Reset History
  </a>
</div>
""", unsafe_allow_html=True)

# ── Dispatch ───────────────────────────────────────────────────────────────────
if mode == "Process Invoice":
    mode_single()
elif mode == "Batch Run":
    mode_batch()
else:
    mode_history()
