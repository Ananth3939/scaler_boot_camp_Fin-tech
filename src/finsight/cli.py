from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from finsight.agents.financial_data import compute_key_ratios
from finsight.models import FinSightModel
from finsight.orchestration.workflow import run_research
from finsight.services import create_market_data_service, create_news_service
from finsight.tools.market_data import DataProviderError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finsight",
        description="Fetch source-aware financial data for a company ticker.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("price", "company", "statements", "ratios", "news"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("ticker", help="Company ticker, for example AAPL")
        if command == "news":
            subparser.add_argument("--limit", type=int, default=10, choices=range(1, 51))
    research = subparsers.add_parser(
        "research", help="Run a complete in-process research workflow."
    )
    research.add_argument("ticker", help="Company ticker, for example AAPL")
    research.add_argument(
        "--json", action="store_true", help="Print the full structured response as JSON"
    )
    return parser


def _print_model(model: FinSightModel) -> None:
    print(model.model_dump_json(indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "news":
            _print_model(create_news_service().search_recent_news(args.ticker, args.limit))
            return 0
        if args.command == "research":
            response = run_research(args.ticker)
            if args.json:
                _print_model(response)
            else:
                print(f"Request ID: {response.request_id} | Status: {response.status}\n")
                print(response.markdown_report)
            return 0 if response.status != "failed" else 1

        service = create_market_data_service()
        if args.command == "price":
            _print_model(service.get_stock_price(args.ticker))
        elif args.command == "company":
            _print_model(service.get_company_info(args.ticker))
        elif args.command == "statements":
            _print_model(service.get_financial_statements(args.ticker))
        else:
            statements = service.get_financial_statements(args.ticker)
            _print_model(compute_key_ratios(statements))
        return 0
    except (DataProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
