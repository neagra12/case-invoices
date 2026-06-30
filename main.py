"""
Invoice Processing System — CLI entry point

Usage:
  python main.py --invoice_path data/invoices/invoice_1001.txt
  python main.py --batch data/invoices/
  python main.py --invoice_path data/invoices/invoice_1003.txt --verbose
"""

import argparse
import glob
import json
import os
import sys
import time

# Force UTF-8 on Windows so Rich can render box-drawing and status chars
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

load_dotenv()

console = Console(force_terminal=True, legacy_windows=False)

SUPPORTED_EXTENSIONS = {".txt", ".json", ".csv", ".xml", ".pdf"}

STATUS_ICONS = {
    "paid":     "[green]✓ PAID[/green]",
    "rejected": "[red]✗ REJECTED[/red]",
    "error":    "[yellow]⚠ ERROR[/yellow]",
    "skipped":  "[dim]— SKIPPED[/dim]",
}


# ── Single invoice ─────────────────────────────────────────────────────────────

def run_single(path: str, verbose: bool = False) -> dict:
    from orchestrator import process_invoice

    if not os.path.exists(path):
        console.print(f"[red]File not found:[/red] {path}")
        sys.exit(1)

    console.print()
    console.rule(f"[bold cyan]Processing {os.path.basename(path)}[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("Running pipeline...", total=None)
        t0 = time.time()
        result = process_invoice(path)
        elapsed = time.time() - t0

    _print_result(result, verbose=verbose)
    console.print(f"\n[dim]Completed in {elapsed:.2f}s[/dim]")
    return result


def _print_result(state: dict, verbose: bool = False) -> None:
    invoice_data     = state.get("invoice_data")     or {}
    validation_result = state.get("validation_result") or {}
    approval_result  = state.get("approval_result")  or {}
    payment_result   = state.get("payment_result")   or {}
    error            = state.get("error")
    log              = state.get("processing_log")   or []

    inv_num  = invoice_data.get("invoice_number", "?")
    vendor   = invoice_data.get("vendor", "?")
    total    = invoice_data.get("total", 0)
    currency = invoice_data.get("currency", "USD")

    # ── Header panel ──────────────────────────────────────────────────────────
    if invoice_data:
        header = (
            f"[bold]{inv_num}[/bold]  |  {vendor}  |  "
            f"[cyan]{currency} {total:,.2f}[/cyan]"
        )
    else:
        header = "[bold red]Ingestion failed[/bold red]"

    console.print(Panel(header, expand=False))

    # ── Stage table ───────────────────────────────────────────────────────────
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Stage",  style="bold", width=14)
    table.add_column("Status", width=6)
    table.add_column("Detail")

    # Ingestion
    if error and not invoice_data:
        table.add_row("INGESTION", "[red]✗[/red]", f"[red]{error}[/red]")
    elif invoice_data:
        conf = invoice_data.get("confidence", 1.0)
        flags = invoice_data.get("ingestion_flags", [])
        flag_str = f"  ⚠ {flags[0]}" if flags else ""
        table.add_row(
            "INGESTION",
            "[green]✓[/green]",
            f"Confidence {conf:.0%}{flag_str}",
        )

    # Validation
    if validation_result:
        vflags = validation_result.get("flags", [])
        errors   = [f for f in vflags if f.get("severity") == "error"]
        warnings = [f for f in vflags if f.get("severity") == "warning"]
        is_dup   = validation_result.get("is_duplicate", False)

        if is_dup:
            table.add_row("VALIDATION", "[red]✗[/red]", "[red]Duplicate invoice — rejected[/red]")
        elif errors:
            table.add_row(
                "VALIDATION",
                "[red]✗[/red]",
                f"[red]{len(errors)} error(s)[/red]"
                + (f", {len(warnings)} warning(s)" if warnings else ""),
            )
        else:
            table.add_row(
                "VALIDATION",
                "[green]✓[/green]" if not warnings else "[yellow]⚠[/yellow]",
                "Passed" + (f" ({len(warnings)} warning(s))" if warnings else ""),
            )
    elif invoice_data:
        table.add_row("VALIDATION", "[dim]—[/dim]", "[dim]Not reached[/dim]")

    # Approval
    if approval_result:
        approved = approval_result.get("approved", False)
        scrutiny = approval_result.get("requires_scrutiny", False)
        label    = "[green]✓ APPROVED[/green]" if approved else "[red]✗ REJECTED[/red]"
        detail   = label + (" [yellow](high-value scrutiny applied)[/yellow]" if scrutiny else "")
        table.add_row("APPROVAL", "[green]✓[/green]" if approved else "[red]✗[/red]", detail)
    elif validation_result:
        table.add_row("APPROVAL", "[dim]—[/dim]", "[dim]Not reached[/dim]")

    # Payment
    if payment_result:
        status = payment_result.get("status", "")
        table.add_row(
            "PAYMENT",
            "[green]✓[/green]" if status == "paid" else "[red]✗[/red]",
            STATUS_ICONS.get(status, status),
        )
    elif approval_result:
        table.add_row("PAYMENT", "[dim]—[/dim]", "[dim]Not reached[/dim]")

    console.print(table)

    # ── Verbose: full reasoning + log ─────────────────────────────────────────
    if verbose:
        if approval_result and approval_result.get("reasoning"):
            console.print("\n[bold]Approval Reasoning:[/bold]")
            console.print(approval_result["reasoning"])
            console.print("\n[bold]Self-Critique:[/bold]")
            console.print(approval_result.get("critique", ""))

        if validation_result and validation_result.get("flags"):
            console.print("\n[bold]Validation Flags:[/bold]")
            for f in validation_result["flags"]:
                sev = f["severity"]
                colour = "red" if sev == "error" else ("yellow" if sev == "warning" else "blue")
                console.print(f"  [{colour}][{sev.upper()}][/{colour}] {f['message']}")

        console.print("\n[bold]Processing Log:[/bold]")
        for line in log:
            console.print(f"  [dim]{line}[/dim]")


# ── Batch mode ─────────────────────────────────────────────────────────────────

def run_batch(directory: str, verbose: bool = False) -> None:
    from orchestrator import process_invoice

    files = sorted([
        f for f in glob.glob(os.path.join(directory, "*"))
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    ])

    if not files:
        console.print(f"[yellow]No supported invoice files found in {directory}[/yellow]")
        sys.exit(0)

    console.print()
    console.rule("[bold cyan]Batch Invoice Processing[/bold cyan]")
    console.print(f"  Found [bold]{len(files)}[/bold] invoice files\n")

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=len(files))
        for path in files:
            progress.update(task, description=f"  {os.path.basename(path)}")
            t0 = time.time()
            state = process_invoice(path)
            elapsed = time.time() - t0
            results.append((path, state, elapsed))
            progress.advance(task)

    _print_batch_summary(results, verbose=verbose)


def _print_batch_summary(results: list, verbose: bool = False) -> None:
    table = Table(title="Batch Results", box=box.ROUNDED)
    table.add_column("File",     style="cyan",  no_wrap=True)
    table.add_column("Invoice",  style="bold")
    table.add_column("Vendor")
    table.add_column("Amount",   justify="right")
    table.add_column("Status",   justify="center")
    table.add_column("Flags",    justify="right")
    table.add_column("Time",     justify="right", style="dim")

    paid_total = 0.0
    paid_count = 0
    rejected_count = 0
    error_count = 0

    for path, state, elapsed in results:
        inv  = state.get("invoice_data") or {}
        pay  = state.get("payment_result") or {}
        vr   = state.get("validation_result") or {}

        fname    = os.path.basename(path)
        inv_num  = inv.get("invoice_number", "?")
        vendor   = (inv.get("vendor") or "?")[:20]
        currency = inv.get("currency", "USD")
        total    = inv.get("total", 0)
        status   = pay.get("status") or ("error" if state.get("error") else "skipped")
        n_flags  = len(vr.get("flags", []))

        status_cell = STATUS_ICONS.get(status, status)

        if status == "paid":
            paid_total += total
            paid_count += 1
        elif status == "rejected":
            rejected_count += 1
        else:
            error_count += 1

        table.add_row(
            fname,
            inv_num,
            vendor,
            f"{currency} {total:,.2f}",
            status_cell,
            str(n_flags) if n_flags else "[dim]0[/dim]",
            f"{elapsed:.1f}s",
        )

    console.print(table)

    # Summary stats
    console.print()
    console.print(f"  [green]✓ Paid:    {paid_count}  (${paid_total:,.2f} total)[/green]")
    console.print(f"  [red]✗ Rejected: {rejected_count}[/red]")
    if error_count:
        console.print(f"  [yellow]⚠ Errors:  {error_count}[/yellow]")

    # Export JSON results
    export_path = "batch_results.json"
    export_data = []
    for path, state, elapsed in results:
        inv = state.get("invoice_data") or {}
        pay = state.get("payment_result") or {}
        export_data.append({
            "file": os.path.basename(path),
            "invoice_number": inv.get("invoice_number"),
            "vendor": inv.get("vendor"),
            "total": inv.get("total"),
            "currency": inv.get("currency"),
            "status": pay.get("status") or ("error" if state.get("error") else "skipped"),
            "error": state.get("error"),
            "elapsed_s": round(elapsed, 2),
        })
    with open(export_path, "w") as f:
        json.dump(export_data, f, indent=2)
    console.print(f"\n  [dim]Results exported to {export_path}[/dim]")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Acme Corp Invoice Processing Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --invoice_path data/invoices/invoice_1001.txt
  python main.py --invoice_path data/invoices/invoice_1003.txt --verbose
  python main.py --batch data/invoices/
        """,
    )
    parser.add_argument("--invoice_path", help="Path to a single invoice file")
    parser.add_argument("--batch",        help="Directory of invoices to process in bulk")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full reasoning and logs")

    args = parser.parse_args()

    if not args.invoice_path and not args.batch:
        parser.print_help()
        sys.exit(1)

    if args.invoice_path and args.batch:
        console.print("[red]Error:[/red] Specify either --invoice_path or --batch, not both.")
        sys.exit(1)

    if args.invoice_path:
        run_single(args.invoice_path, verbose=args.verbose)
    else:
        run_batch(args.batch, verbose=args.verbose)


if __name__ == "__main__":
    main()
