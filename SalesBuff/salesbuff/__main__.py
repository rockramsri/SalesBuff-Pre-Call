"""Single entry point — run a sales due-diligence scenario."""

from __future__ import annotations

import argparse
import asyncio
import json
import textwrap

from salesbuff.container import Container
from salesbuff.domain.framing import get_sales_frame
from salesbuff.metrics import UsageMetrics, current_metrics
from salesbuff.models.brief import BriefCategory, SalesBrief
from salesbuff.models.entities import SalesContext
from salesbuff.pipeline import PipelineResult, run_scenario

# Human-readable label per category (e.g. "opening_move" -> "Opening move").
_CATEGORY_LABELS: dict[BriefCategory, str] = {
    category: category.value.replace("_", " ").capitalize() for category in BriefCategory
}

DEFAULT_PROMPT = (
    "I'm a pharma sales rep at PharmaLink pitching a 2-day-delivery distribution "
    "service to Mount Sinai Hospital in New York. They currently buy pharma distribution "
    "from McKesson Corporation. I'm meeting with Dr. Sarah Chen, VP of Pharmacy. "
    "Help me find weaknesses in McKesson so I can win this deal."
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sales due-diligence")
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT, help="Rep's sales prompt")
    parser.add_argument("--json", action="store_true", help="Print SalesBrief as JSON")
    args = parser.parse_args(argv)
    asyncio.run(_async_main(args.prompt, json_output=args.json))


async def _async_main(prompt: str, *, json_output: bool) -> None:
    container = Container.from_config()
    metrics = UsageMetrics()
    metrics_token = current_metrics.set(metrics)
    try:
        print(f"\n{'=' * 70}")
        print("SCENARIO:")
        print(f"  {textwrap.fill(prompt, 80, subsequent_indent='  ')}")
        print(f"{'=' * 70}\n")

        print("[ 1/4 ] Resolving entities (LLM + Tavily search)...")
        result = await run_scenario(prompt, container.pipeline)
        _print_context(result.context)

        print("[ 2/4 ] Deep research complete (web + legal lanes).")
        _print_research_counts(result)
        _print_confirmation_warnings(result)

        print("[ 3/4 ] Findings summary...")
        _print_findings(result)

        print("[ 4/4 ] Card brief...")
        if json_output and result.brief:
            print(json.dumps(result.brief.model_dump(mode="json"), indent=2))
        else:
            _print_brief(result.brief)
            if result.dropped_cards:
                print(f"  [accountability] dropped {len(result.dropped_cards)} uncited card(s):")
                for title in result.dropped_cards:
                    print(f"    - {title}")
                print()

        _run_checks(result)
        metrics.snapshot("done")
        metrics.log_summary("cli")
    finally:
        current_metrics.reset(metrics_token)
        await container.aclose()


def _print_context(ctx: SalesContext) -> None:
    print(f"  Prospect   : {ctx.prospect.name} ({ctx.prospect.industry or 'unknown industry'})")
    print(f"  Contact    : {ctx.contact.full_name} ({ctx.contact.title or 'unknown title'})")
    if ctx.incumbent:
        print(
            f"  Incumbent  : {ctx.incumbent.name} "
            f"({ctx.incumbent.product_category or 'unknown category'})"
        )
    else:
        print("  Incumbent  : (none mentioned)")
    if ctx.rep_product:
        print(f"  Rep sells  : {ctx.rep_product}")
    if ctx.prospect.aliases:
        print(f"  Aliases    : prospect={', '.join(ctx.prospect.aliases)}")
    if ctx.incumbent and ctx.incumbent.aliases:
        print(f"             : incumbent={', '.join(ctx.incumbent.aliases)}")
    if ctx.resolution_note:
        print(f"  Note       : {ctx.resolution_note}")
    print()


def _print_research_counts(result: PipelineResult) -> None:
    web = result.web
    print(
        f"        Web: prospect={web.prospect.total if web.prospect else 0}, "
        f"contact={web.contact.total if web.contact else 0}, "
        f"incumbent={web.incumbent.total if web.incumbent else 0}"
    )
    if result.incumbent_legal:
        print(f"        Legal (incumbent): ~{result.incumbent_legal.total_count} cases")
    if result.prospect_legal:
        print(f"        Legal (prospect): ~{result.prospect_legal.total_count} cases")


def _print_confirmation_warnings(result: PipelineResult) -> None:
    ctx = result.context
    web = result.web
    checks = [
        ("prospect", ctx.prospect.name, web.prospect),
        ("contact", ctx.contact.full_name, web.contact),
    ]
    if ctx.incumbent:
        checks.append(("incumbent", ctx.incumbent.name, web.incumbent))
    for label, name, findings in checks:
        if not findings or findings.total == 0:
            print(f"        WARNING: could not confirm {label} {name!r} from web — treat cautiously.")


def _print_findings(result: PipelineResult) -> None:
    web = result.web
    incumbent_legal = result.incumbent_legal
    prospect_legal = result.prospect_legal

    if incumbent_legal:
        print(f"\n--- INCUMBENT LEGAL (~{incumbent_legal.total_count} total) ---")
        if incumbent_legal.no_cases:
            print("    (no verified cases)")
        for case in incumbent_legal.cases:
            frame = get_sales_frame(case.risk_type)
            print(f"  [{frame['label']}] {case.case_name}")
            if case.details:
                print(f"    ↳ {case.details}")
            print(f"    {case.url}")

    if prospect_legal and not prospect_legal.no_cases:
        print(f"\n--- PROSPECT LEGAL (~{prospect_legal.total_count} total) ---")
        for case in prospect_legal.cases[:5]:
            frame = get_sales_frame(case.risk_type)
            print(f"  [{frame['label']}] {case.case_name} | {case.date_filed or 'n/a'}")

    for label, findings in (
        ("INCUMBENT WEB", web.incumbent),
        ("PROSPECT WEB", web.prospect),
        ("CONTACT WEB", web.contact),
    ):
        if findings and findings.total:
            print(f"\n--- {label} ({findings.total} results) ---")
            for cat, results in findings.categories.items():
                if results:
                    print(f"  [{cat}] {len(results)} result(s)")
                    for r in results[:2]:
                        print(f"    - {r.title}")
    print()


def _print_brief(brief: SalesBrief | None) -> None:
    print("\n" + "=" * 70)
    print("SALES CARD BRIEF")
    print("=" * 70)
    if not brief:
        print("(brief unavailable)\n")
        return

    if brief.opening_line:
        print(f"\nOPENING LINE:\n  {brief.opening_line}")

    grouped = brief.grouped()
    for category in BriefCategory:
        cards = grouped.get(category)
        if not cards:
            continue
        print(f"\n{_CATEGORY_LABELS[category].upper()}:")
        for card in cards:
            conf = f" [{card.confidence}]" if card.confidence else ""
            pri = f" priority={card.priority}" if card.priority else ""
            print(f"  • {card.title}{conf}{pri}")
            print(f"    {card.preview}")
            if card.detail and card.detail != card.preview:
                print(f"    ↳ {card.detail}")
            for citation in card.citations:
                print(f"      [{citation.source}] {citation.url}")
    print()


def _run_checks(result: PipelineResult) -> None:
    ctx = result.context
    web = result.web
    checks = [
        ("prospect name extracted", bool(ctx.prospect.name)),
        ("contact person extracted", bool(ctx.contact.full_name)),
        ("web: prospect results", web.prospect is not None and web.prospect.total > 0),
        ("web: contact results", web.contact is not None and web.contact.total > 0),
    ]
    if ctx.incumbent:
        checks.append(
            ("web: incumbent results", web.incumbent is not None and web.incumbent.total > 0)
        )
    checks.append(
        (
            "brief generated",
            result.brief is not None and result.brief.card_count > 0,
        )
    )
    print("=== CHECKS ===")
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print()


if __name__ == "__main__":
    main()
