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
/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #f8fafc; }

/* ── Toolbar / top bar — match main bg so it doesn't look broken ── */
header[data-testid="stHeader"] {
    background: #f8fafc !important;
    border-bottom: 1px solid #e2e8f0 !important;
}

/* ── Sidebar — remove excess top padding ── */
[data-testid="stSidebar"] { background: #1e293b !important; }
[data-testid="stSidebarContent"] { padding-top: 0.75rem !important; }
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] hr { border-color: #334155 !important; }
[data-testid="stSidebar"] h1 { color: #f1f5f9 !important; font-size: 1.1rem !important; }

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
.sb-stat { background:#334155; border-radius:8px; padding:10px 14px; margin-bottom:8px; }
.sb-stat-val { font-size:1.3rem; font-weight:700; color:#f1f5f9; }
.sb-stat-label { font-size:.72rem; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; }

/* ── Confidence bar ── */
.conf-bar-wrap { background:#e2e8f0; border-radius:4px; height:8px; margin-top:4px; }
.conf-bar { background:#22c55e; border-radius:4px; height:8px; }

/* ── Reset History button — make it a visible danger button ── */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button,
[data-testid="stSidebar"] .stButton button {
    background: linear-gradient(135deg, #ef4444, #dc2626) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
    box-shadow: 0 2px 6px rgba(239,68,68,0.35) !important;
    transition: all .15s ease !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button:hover,
[data-testid="stSidebar"] .stButton button:hover {
    background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
    box-shadow: 0 4px 10px rgba(239,68,68,0.45) !important;
    transform: translateY(-1px) !important;
}

/* ── Main header area ── */
.main-header {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-radius: 14px;
    padding: 28px 32px;
    margin-bottom: 24px;
    color: #f1f5f9;
}
.main-header h2 { margin: 0 0 4px; font-size: 1.5rem; color: #f8fafc; }
.main-header p  { margin: 0; font-size: 0.9rem; color: #94a3b8; }

/* ── Run pipeline button (primary) ── */
button[kind="primary"] {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(59,130,246,0.4) !important;
    transition: all .15s ease !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    box-shadow: 0 4px 14px rgba(59,130,246,0.5) !important;
    transform: translateY(-1px) !important;
}

/* ── Top-right Reset button ── */
[data-testid="stButton"][key="top_reset_btn"] button,
div:has(> [data-testid="baseButton-secondary"]#top_reset_btn) button {
    background: linear-gradient(135deg, #ef4444, #dc2626) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    padding: 6px 12px !important;
    box-shadow: 0 2px 6px rgba(239,68,68,0.35) !important;
}

/* ── Upload area refinement ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #cbd5e1 !important;
    border-radius: 12px !important;
    background: #f8fafc !important;
    transition: border-color .2s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #3b82f6 !important;
}

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
    st.markdown("## 🏭 Acme Corp AP")
    st.caption("Invoice Automation System")
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
    st.markdown('<p style="font-size:.72rem;color:#475569;margin:0;text-align:center">Use the 🗑️ Reset button (top right)</p>', unsafe_allow_html=True)

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
                st.markdown("**Invoice Details**")
                details = {
                    "Number":   inv.get("invoice_number", "—"),
                    "Vendor":   inv.get("vendor") or "*(missing)*",
                    "Date":     str(inv.get("date") or "—"),
                    "Due Date": str(inv.get("due_date") or "*(missing)*"),
                    "Currency": inv.get("currency", "USD"),
                    "Terms":    inv.get("payment_terms") or "—",
                }
                for k, v in details.items():
                    st.markdown(f"**{k}:** {v}")

                # Confidence bar
                conf = inv.get("confidence", 1.0)
                conf_color = "#22c55e" if conf >= 0.85 else "#f59e0b" if conf >= 0.6 else "#ef4444"
                st.markdown(f"**Extraction confidence:** {conf:.0%}")
                st.markdown(
                    f'<div class="conf-bar-wrap"><div class="conf-bar" '
                    f'style="width:{conf*100:.0f}%;background:{conf_color}"></div></div>',
                    unsafe_allow_html=True,
                )

            with c2:
                st.markdown("**Line Items**")
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
                st.markdown("---")
                st.markdown("**Ingestion Notes**")
                for f in inv["ingestion_flags"]:
                    st.warning(f)

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
            approved     = ar.get("approved", False)
            scrutiny     = ar.get("requires_scrutiny", False)
            risk_level   = "high" if not approved else ("medium" if scrutiny else "low")
            risk_label   = risk_level.upper()

            col_a, col_b = st.columns([3, 1])
            with col_a:
                label = "✅ Approved" if approved else "🚫 Rejected"
                st.markdown(f"### {label}")
                if scrutiny:
                    st.markdown("⚑ **High-value invoice** — enhanced VP scrutiny applied (>$10,000 threshold)")
            with col_b:
                st.markdown(
                    f'<div style="text-align:right"><span class="risk-badge risk-{risk_level}">'
                    f'Risk: {risk_label}</span></div>',
                    unsafe_allow_html=True,
                )

            # Reasoning
            st.markdown(
                f'<div class="reason-card"><h4>VP Reasoning</h4><p>{ar.get("reasoning","")}</p></div>',
                unsafe_allow_html=True,
            )

            # Self-critique — the "Above and Beyond" feature
            with st.expander("🔄 Self-Critique Loop (AI second opinion)"):
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
            status = pay.get("status", "")
            vendor = pay.get("vendor", inv.get("vendor", "—"))
            amount = pay.get("amount", inv.get("total", 0))
            currency = inv.get("currency", "USD")

            if status == "paid":
                st.success(f"**Payment processed** — {currency} {amount:,.2f} sent to **{vendor}**")
                detail = pay.get("detail", "")
                if "TXN-" in detail:
                    txn = detail.split("TXN-")[-1].strip()
                    st.caption(f"Transaction ID: TXN-{txn}")
            elif status == "rejected":
                st.error(f"**Payment blocked** — {currency} {amount:,.2f} withheld from {vendor}")
                st.markdown("**Rejection reason logged to AP system.**")
            else:
                st.warning(pay.get("detail", "Unknown status"))
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
    <div class="main-header">
        <h2>Process Invoice</h2>
        <p>Upload any invoice format — the 4-agent pipeline handles ingestion, validation, approval and payment automatically.</p>
    </div>
    """, unsafe_allow_html=True)

    sample_dir = Path(__file__).parent.parent / "data" / "invoices"
    sample_files = sorted(sample_dir.glob("*")) if sample_dir.exists() else []

    col_up, col_pick = st.columns([1, 1])
    with col_up:
        uploaded = st.file_uploader(
            "Upload invoice",
            type=["txt", "json", "csv", "xml", "pdf"],
            help="Supported: TXT, JSON, CSV, XML, PDF",
            label_visibility="collapsed",
        )
    with col_pick:
        sample_names = ["— or select a sample invoice —"] + [f.name for f in sample_files]
        selected_sample = st.selectbox("Sample", sample_names, label_visibility="collapsed")

    run_btn = st.button("▶  Run Pipeline", type="primary")

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

        with st.spinner("Running 4-stage pipeline…"):
            t0 = time.time()
            state = process_invoice(path)
            elapsed = time.time() - t0

        st.caption(f"Completed in {elapsed:.1f}s")
        st.divider()
        render_result(state)


# ── Mode: Batch Run ────────────────────────────────────────────────────────────
def mode_batch():
    st.markdown("""
    <div class="main-header">
        <h2>Batch Processing</h2>
        <p>Process all invoices in the test suite and see aggregate business impact across the full pipeline.</p>
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
    c1.metric("✅ Invoices Cleared", len(paid_results), f"${paid_total:,.0f}")
    c2.metric("🚫 Invoices Blocked", len(rej_results), f"${blocked_total:,.0f} protected")
    c3.metric("🔴 Fraud / Suspicious", len(fraud_results), "detected & blocked")
    c4.metric("⏱ Total Processing Time", f"{total_elapsed:.0f}s",
              f"vs. ~{len(results)*5*60//60}h manual")

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
            "File":        fname,
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
        icon   = "✅" if status=="PAID" else "🚫" if status=="REJECTED" else "⚠️"
        inv    = state.get("invoice_data") or {}
        label  = f"{icon} {fname}  ·  {inv.get('invoice_number','?')}  ·  ${inv.get('total',0):,.2f}  ·  {status}"
        with st.expander(label):
            render_result(state, compact=True)


# ── Mode: Processing History ───────────────────────────────────────────────────
def mode_history():
    st.markdown("""
    <div class="main-header">
        <h2>Processing History</h2>
        <p>All invoices processed in this session — pulled live from the local SQLite audit database.</p>
    </div>
    """, unsafe_allow_html=True)

    rows = db_history(limit=50)
    if not rows:
        st.info("No invoices processed yet. Run the pipeline to see results here.")
        return

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


# ── Top-right Reset button (beside Deploy) ─────────────────────────────────────
st.markdown("""
<style>
.reset-btn-wrap {
    position: fixed;
    top: 10px;
    right: 110px;
    z-index: 9999;
}
.reset-btn-wrap a {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: #fff !important;
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(239,68,68,0.35);
    transition: all .15s ease;
    cursor: pointer;
    border: none;
}
.reset-btn-wrap a:hover {
    background: linear-gradient(135deg,#dc2626,#b91c1c);
    box-shadow: 0 4px 10px rgba(239,68,68,0.45);
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)

_reset_key = "top_reset_clicked"
if st.session_state.get(_reset_key):
    db_reset()
    st.session_state[_reset_key] = False
    st.toast("History cleared.", icon="🗑️")
    st.rerun()

top_col_spacer, top_col_btn = st.columns([10, 1])
with top_col_btn:
    if st.button("🗑️ Reset", key="top_reset_btn",
                 help="Clear processed invoice history",
                 type="secondary"):
        st.session_state[_reset_key] = True
        st.rerun()

# ── Dispatch ───────────────────────────────────────────────────────────────────
if mode == "Process Invoice":
    mode_single()
elif mode == "Batch Run":
    mode_batch()
else:
    mode_history()
