"""Command-line interface (CLI) for tennis-trading-bot powered by Typer and Rich."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tennis_trading_bot import KALSHI_REFERRAL_URL, __version__
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.engine import TradingEngine

app = typer.Typer(
    name="tennis-bot",
    help="Autonomous algorithmic trading bot for Kalshi prediction markets powered by iPredictSport.",
    add_completion=False,
)
console = Console(safe_box=True)


def print_banner() -> None:
    """Display welcome banner with referral credits callout."""
    banner_text = (
        f"[bold cyan]tennis-trading-bot[/bold cyan] [green]v{__version__}[/green]\n"
        "[white]Turnkey Algorithmic Tennis Trading on Kalshi Prediction Markets[/white]\n"
        "[dim]Powered by open quantitative machine learning models from [link=https://ipredictsport.com]iPredictSport.com[/link][/dim]\n\n"
        f"[yellow]>> Need a Kalshi account?[/yellow] [bold underline cyan][link={KALSHI_REFERRAL_URL}]Sign up with partner link for fee credits[/link][/bold underline cyan]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


@app.command()
def run(
    mode: str | None = typer.Option(
        None, "--mode", "-m", help="Execution mode: 'paper' (default) or 'kalshi'"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview signals without placing paper or exchange orders"
    ),
    once: bool = typer.Option(
        False, "--once", help="Run a single evaluation cycle and exit"
    ),
    interval: int | None = typer.Option(
        None, "--interval", "-i", help="Polling interval in seconds for continuous loop"
    ),
) -> None:
    """Execute the trading bot in paper or live mode."""
    print_banner()
    config = BotConfig.load()
    if mode:
        config.trade_mode = mode.lower()  # type: ignore

    engine = TradingEngine(config)
    console.print(
        f"[bold]Active Mode:[/bold] [magenta]{config.trade_mode.upper()}[/magenta] | "
        f"[bold]Bankroll:[/bold] [green]${config.bankroll_usd:,.2f}[/green] | "
        f"[bold]Min Edge:[/bold] [yellow]{config.min_edge_pp:.1f}pp[/yellow]"
    )

    if once or dry_run:
        result = engine.run_once(dry_run=dry_run)
        signals = result["signals"]
        orders = result["orders"]

        if signals:
            table = Table(title=f"Detected Trading Edges ({len(signals)} found)", border_style="green")
            table.add_column("Ticker", style="dim")
            table.add_column("Match", style="bold")
            table.add_column("Pick", style="cyan")
            table.add_column("Model %", justify="right")
            table.add_column("Ask", justify="right")
            table.add_column("Edge", justify="right", style="bold green")
            table.add_column("¼-Kelly", justify="right")
            table.add_column("Stake", justify="right", style="green")
            table.add_column("Status", style="bold")

            for i, sig in enumerate(signals):
                status = "Dry-Run" if dry_run else (orders[i].status.upper() if i < len(orders) else "Simulated")
                table.add_row(
                    sig.event_ticker,
                    sig.match,
                    f"{sig.pick} ({sig.side})",
                    f"{sig.model_prob*100:.1f}%",
                    f"{sig.market_price*100:.0f}¢",
                    f"{sig.edge_pp:+.1f}pp",
                    f"{sig.kelly_fraction*100:.1f}%",
                    f"${sig.stake_usd:.2f} ({sig.contracts}x)",
                    f"[green]{status}[/green]" if status in ("FILLED", "Simulated") else f"[yellow]{status}[/yellow]",
                )
            console.print(table)
        else:
            console.print("[yellow]No positive-EV trading opportunities found exceeding threshold.[/yellow]")

        if result.get("skip_reasons"):
            console.print(f"[dim]Skip reasons: {result['skip_reasons']}[/dim]")

        # Portfolio Summary
        port = result["portfolio"]
        console.print(
            Panel(
                f"[bold]Total Equity:[/bold] ${port['total_equity_usd']:.2f}  |  "
                f"[bold]Cash Available:[/bold] ${port['cash_usd']:.2f}  |  "
                f"[bold]Active Positions:[/bold] {port['open_positions_count']}",
                title="Portfolio Telemetry",
                border_style="cyan",
            )
        )
    else:
        engine.run_loop(poll_interval=interval, dry_run=False)


@app.command()
def paper(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview signals only"),
    once: bool = typer.Option(True, "--once/--loop", help="Run once (default) or loop"),
) -> None:
    """Run bot in zero-risk Paper Trading mode (alias for 'run --mode paper')."""
    run(mode="paper", dry_run=dry_run, once=once, interval=None)


@app.command()
def status() -> None:
    """Inspect active portfolio, bankroll equity, and open positions."""
    print_banner()
    config = BotConfig.load()
    engine = TradingEngine(config)
    port = engine.broker.sync_portfolio()

    console.print(
        Panel(
            f"[bold]Broker:[/bold] {port['broker'].upper()}\n"
            f"[bold]Cash Available:[/bold] [green]${port['cash_usd']:.2f}[/green]\n"
            f"[bold]Invested Capital:[/bold] ${port.get('invested_usd', 0.0):.2f}\n"
            f"[bold]Total Portfolio Equity:[/bold] [bold cyan]${port['total_equity_usd']:.2f}[/bold cyan]\n"
            f"[bold]Open Positions:[/bold] {port['open_positions_count']}",
            title="Account Summary",
            border_style="cyan",
        )
    )

    open_positions = engine.broker.get_open_positions()
    if open_positions:
        table = Table(title="Active Open Positions", border_style="green")
        table.add_column("Ticker", style="dim")
        table.add_column("Match", style="bold")
        table.add_column("Side")
        table.add_column("Entry Price", justify="right")
        table.add_column("Contracts", justify="right")
        table.add_column("Stake", justify="right", style="green")
        table.add_column("Opened At (UTC)", style="dim")

        for p in open_positions:
            table.add_row(
                p.ticker,
                p.match,
                p.side,
                f"{p.entry_price*100:.0f}¢",
                str(p.contracts),
                f"${p.stake_usd:.2f}",
                p.opened_at_utc[:19].replace("T", " "),
            )
        console.print(table)
    else:
        console.print("[dim]No active open positions.[/dim]")


@app.command()
def setup() -> None:
    """Interactive onboarding wizard to configure settings and referral credentials."""
    print_banner()
    console.print("[bold yellow]Welcome to the tennis-trading-bot Setup Wizard![/bold yellow]\n")

    has_kalshi = Confirm.ask("Do you already have a funded Kalshi account?", default=False)
    if not has_kalshi:
        console.print(
            Panel(
                f"[bold green]Claim Your Sign-Up Fee Credits & Bonus:[/bold green]\n"
                f"Sign up on Kalshi via our partner link:\n"
                f"[bold underline cyan]{KALSHI_REFERRAL_URL}[/bold underline cyan]\n\n"
                "[dim]You can test in Paper mode with zero funds first, then add API keys when ready.[/dim]",
                title="Partner Referral Onboarding",
                border_style="yellow",
            )
        )

    mode = Prompt.ask("Select trading mode", choices=["paper", "kalshi"], default="paper")
    bankroll = Prompt.ask("Enter your starting bankroll (USD)", default="1000.0")
    min_edge = Prompt.ask("Minimum fee-aware edge in percentage points (e.g. 8.0)", default="8.0")

    kalshi_key = ""
    kalshi_key_path = ""
    use_demo = "true"

    if mode == "kalshi":
        kalshi_key = Prompt.ask("Kalshi API Key ID (UUID)", default="")
        kalshi_key_path = Prompt.ask("Path to Kalshi private key (.key/.pem)", default="")
        use_demo = "true" if Confirm.ask("Use Kalshi Demo environment?", default=True) else "false"

    # Write .env file
    env_content = (
        f"TRADE_MODE={mode}\n"
        f"BANKROLL_USD={bankroll}\n"
        f"MIN_EDGE_PP={min_edge}\n"
        f"MAX_SPREAD=0.15\n"
        f"MIN_CONFIDENCE=medium_plus\n"
        f"PREDICTIONS_FEED_URL=https://ipredictsport.com/predictions.json\n"
        f"KALSHI_API_KEY_ID={kalshi_key}\n"
        f"KALSHI_PRIVATE_KEY_PATH={kalshi_key_path}\n"
        f"KALSHI_USE_DEMO={use_demo}\n"
    )

    env_path = Path(".env")
    env_path.write_text(env_content, encoding="utf-8")
    console.print(f"\n[bold green][OK] Configuration successfully saved to {env_path.resolve()}[/bold green]")
    console.print("\n[bold]Next Step:[/bold] Run [cyan]tennis-bot run --mode paper --dry-run[/cyan] to test your strategy!")


@app.command()
def mcp() -> None:
    """Display instructions for connecting Claude Desktop or Cursor to the MCP server."""
    print_banner()
    console.print(
        Panel(
            "[bold green]iPredictSport Model Context Protocol (MCP) Server[/bold green]\n\n"
            "Connect Claude Desktop, Cursor, or Zed to live tennis predictions and +EV betting edges.\n\n"
            "[bold]Add this to your claude_desktop_config.json:[/bold]\n"
            "```json\n"
            "{\n"
            '  "mcpServers": {\n'
            '    "tennis-predict": {\n'
            '      "command": "python",\n'
            '      "args": ["-m", "scripts.mcp_server"]\n'
            "    }\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "[dim]Full docs: https://ipredictsport.com/for-robots.html[/dim]",
            title="MCP Agent Integration",
            border_style="cyan",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
