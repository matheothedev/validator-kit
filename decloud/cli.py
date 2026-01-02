#!/usr/bin/env python3
"""
DECLOUD Validator CLI
=====================

Command-line interface for DECLOUD validators.
"""

import os
import sys
import argparse
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich import box

from .config import Config
from .dataset_manager import DatasetManager, DatasetCategory
from .validator import Validator

console = Console()


def print_banner():
    """Print beautiful DECLOUD banner"""
    
    logo = """
    ██████╗ ███████╗ ██████╗██╗      ██████╗ ██╗   ██╗██████╗ 
    ██╔══██╗██╔════╝██╔════╝██║     ██╔═══██╗██║   ██║██╔══██╗
    ██║  ██║█████╗  ██║     ██║     ██║   ██║██║   ██║██║  ██║
    ██║  ██║██╔══╝  ██║     ██║     ██║   ██║██║   ██║██║  ██║
    ██████╔╝███████╗╚██████╗███████╗╚██████╔╝╚██████╔╝██████╔╝
    ╚═════╝ ╚══════╝ ╚═════╝╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝ """
    
    # Gradient colors for logo
    gradient = ["#00d4ff", "#00b4ff", "#0094ff", "#0074ff", "#0054ff"]
    
    lines = logo.strip().split('\n')
    styled_logo = Text()
    
    for i, line in enumerate(lines):
        color = gradient[i % len(gradient)]
        styled_logo.append(line + "\n", style=color)
    
    panel = Panel(
        Align.center(styled_logo),
        subtitle="[dim]Decentralized Cloud for AI Training[/dim]",
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(panel)


def print_status_badge(status: str) -> str:
    """Get colored status badge"""
    status_styles = {
        "waitingValidator": "[black on yellow] WAITING [/]",
        "waitingTrainers": "[black on cyan] RECRUITING [/]",
        "training": "[black on blue] TRAINING [/]",
        "validating": "[black on magenta] VALIDATING [/]",
        "completed": "[black on green] COMPLETED [/]",
        "cancelled": "[white on red] CANCELLED [/]",
        "expired": "[white on dark_red] EXPIRED [/]",
    }
    return status_styles.get(status, f"[dim]{status}[/dim]")


def cmd_login(args):
    """Login command"""
    config = Config.load()
    validator = Validator(config)
    
    with console.status("[bold blue]Connecting to Solana...", spinner="dots"):
        if args.keyfile:
            success = validator.login_from_file(args.keyfile)
        else:
            success = validator.login(args.private_key)
    
    if success:
        console.print(Panel(
            f"[green]✓[/green] Logged in as: [cyan]{validator.public_key[:30]}...[/cyan]\n"
            f"[green]◎[/green] Balance: [yellow]{validator.balance:.4f} SOL[/yellow]",
            title="[bold green]Authentication Successful[/]",
            border_style="green",
        ))
        
        if args.save:
            config.private_key = args.private_key
            config.save()
            console.print("[dim]✓ Credentials saved to config[/dim]")
    else:
        console.print("[red]✗ Login failed[/red]")
    
    return 0 if success else 1


def cmd_datasets_download(args):
    """Download datasets with progress bars"""
    config = Config.load()
    manager = DatasetManager(config.data_dir)
    
    console.print()
    
    if args.minimal:
        console.print(Panel(
            "[cyan]Downloading minimal dataset pack[/cyan]\n"
            "[dim]~500MB - Essential datasets for validation[/dim]",
            title="📦 Dataset Download",
            border_style="blue",
        ))
        manager.download_minimal()
        
    elif args.category:
        try:
            cat = DatasetCategory(args.category)
            console.print(f"[blue]📦 Downloading {args.category} datasets...[/blue]")
            manager.download_category(cat)
        except ValueError:
            console.print(f"[red]✗ Unknown category: {args.category}[/red]")
            console.print("\n[dim]Available categories:[/dim]")
            for c in DatasetCategory:
                console.print(f"  [cyan]•[/cyan] {c.value}")
            return 1
            
    elif args.dataset:
        console.print(f"[blue]📦 Downloading {args.dataset}...[/blue]")
        manager.download(args.dataset)
        
    else:
        console.print(Panel(
            "[cyan]Downloading all datasets[/cyan]\n"
            "[dim]~50GB - This may take a while[/dim]",
            title="📦 Dataset Download",
            border_style="blue",
        ))
        manager.download_all(skip_large=not args.include_large)
    
    console.print("\n[green]✓ Download complete![/green]")
    return 0


def cmd_datasets_list(args):
    """List datasets with beautiful table"""
    config = Config.load()
    manager = DatasetManager(config.data_dir)
    
    console.print()
    
    if args.status:
        # Detailed status table
        table = Table(
            title="📊 Dataset Status",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="blue",
        )
        
        table.add_column("Dataset", style="white")
        table.add_column("Category", style="dim")
        table.add_column("Size", justify="right")
        table.add_column("Status", justify="center")
        
        for name in sorted(manager.list_datasets()):
            is_downloaded = manager.is_downloaded(name)
            info = manager.get_dataset_info(name)
            
            status = "[green]✓ Ready[/green]" if is_downloaded else "[dim]○ Not downloaded[/dim]"
            category = info.get("category", "unknown") if info else "?"
            size = info.get("size", "?") if info else "?"
            
            table.add_row(name, category, size, status)
        
        console.print(table)
        
        # Summary
        downloaded = sum(1 for d in manager.list_datasets() if manager.is_downloaded(d))
        total = len(manager.list_datasets())
        
        console.print(Panel(
            f"[green]{downloaded}[/green] / [cyan]{total}[/cyan] datasets ready\n"
            f"[dim]Storage: {config.data_dir}[/dim]",
            title="Summary",
            border_style="dim",
        ))
        
    else:
        # Category overview
        categories = manager.list_categories()
        
        table = Table(
            title="📊 DECLOUD Supported Datasets",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="blue",
        )
        
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="yellow")
        table.add_column("Datasets", style="dim")
        
        for cat, datasets in sorted(categories.items()):
            preview = ", ".join(datasets[:3])
            if len(datasets) > 3:
                preview += f" +{len(datasets)-3} more"
            table.add_row(cat, str(len(datasets)), preview)
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(manager.list_datasets())} datasets • Est. size: {manager.estimate_total_size()}[/dim]")
    
    return 0


def cmd_validate_start(args):
    """Start validator with beautiful output"""
    config = Config.from_env()
    
    # Apply CLI args
    if args.min_reward:
        config.min_reward = args.min_reward
    if args.max_reward:
        config.max_reward = args.max_reward
    if args.dataset:
        config.allowed_datasets = [args.dataset]
    if args.no_websocket:
        config.use_websocket = False
    if args.dry_run:
        config.dry_run = True
    if args.no_auto_claim:
        config.auto_claim = False
    
    # Get private key
    private_key = args.private_key or config.private_key or os.getenv("DECLOUD_PRIVATE_KEY")
    
    if not private_key:
        console.print(Panel(
            "[red]No private key provided[/red]\n\n"
            "[dim]Use one of these methods:[/dim]\n"
            "  [cyan]decloud validate start --private-key <key>[/cyan]\n"
            "  [cyan]export DECLOUD_PRIVATE_KEY=<key>[/cyan]",
            title="[red]✗ Authentication Required[/]",
            border_style="red",
        ))
        return 1
    
    validator = Validator(config)
    
    print_banner()
    
    with console.status("[bold blue]Authenticating...", spinner="dots"):
        if not validator.login(private_key):
            return 1
    
    # Show validator info panel
    mode = "[yellow]DRY RUN[/yellow] (monitor only)" if config.dry_run else "[green]LIVE[/green]"
    
    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column(style="dim")
    info_table.add_column(style="white")
    
    info_table.add_row("Validator", f"[cyan]{validator.public_key[:40]}...[/cyan]")
    info_table.add_row("Balance", f"[yellow]{validator.balance:.4f} SOL[/yellow]")
    info_table.add_row("Network", f"[blue]{config.network}[/blue]")
    info_table.add_row("Mode", mode)
    info_table.add_row("", "")
    info_table.add_row("Min Reward", f"{config.min_reward} SOL")
    info_table.add_row("Max Reward", f"{config.max_reward} SOL" if config.max_reward != float('inf') else "∞")
    info_table.add_row("Datasets", str(config.allowed_datasets or "all"))
    
    console.print(Panel(
        info_table,
        title="[bold]🚀 Validator Starting[/]",
        border_style="green",
    ))
    
    console.print("\n[dim]Listening for rounds... Press Ctrl+C to stop[/dim]\n")
    
    validator.start()
    
    return 0


def cmd_rounds_list(args):
    """List rounds with beautiful table"""
    config = Config.load()
    validator = Validator(config)
    
    with console.status("[bold blue]Fetching rounds...", spinner="dots"):
        rounds = validator.get_all_rounds()
    
    console.print()
    
    table = Table(
        title="📋 DECLOUD Rounds",
        box=box.ROUNDED,
        header_style="bold white on blue",
        border_style="blue",
    )
    
    table.add_column("ID", justify="right", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Dataset", style="cyan")
    table.add_column("Reward", justify="right", style="yellow")
    table.add_column("Trainers", justify="center")
    table.add_column("Ready", justify="center")
    
    for r in sorted(rounds, key=lambda x: x.id, reverse=True):
        reward = f"{r.reward_amount / 1e9:.4f} ◎"
        trainers = f"{r.submissions_count}/{r.trainers_count}"
        
        has_dataset = validator.datasets.is_downloaded(r.dataset)
        ready = "[green]✓[/green]" if has_dataset else "[dim]○[/dim]"
        
        table.add_row(
            str(r.id),
            print_status_badge(r.status),
            r.dataset,
            reward,
            trainers,
            ready,
        )
    
    console.print(table)
    
    # Summary panel
    available = sum(1 for r in rounds if r.status == "waitingValidator")
    training = sum(1 for r in rounds if r.status in ("training", "validating"))
    completed = sum(1 for r in rounds if r.status == "completed")
    
    console.print(Panel(
        f"[yellow]{available}[/yellow] waiting • "
        f"[blue]{training}[/blue] active • "
        f"[green]{completed}[/green] completed • "
        f"[dim]{len(rounds)} total[/dim]",
        border_style="dim",
    ))
    
    # Missing datasets hint
    missing = validator.get_missing_datasets()
    if missing:
        console.print(Panel(
            f"[yellow]Missing datasets for available rounds:[/yellow]\n"
            f"[cyan]{', '.join(missing[:5])}[/cyan]\n\n"
            f"[dim]Run: decloud datasets download --dataset <n>[/dim]",
            title="💡 Tip",
            border_style="yellow",
        ))
    
    return 0


def cmd_config_show(args):
    """Show configuration with beautiful panels"""
    config = Config.load()
    
    console.print()
    
    # Network section
    network_table = Table(box=None, show_header=False, padding=(0, 2))
    network_table.add_column(style="dim", width=15)
    network_table.add_column(style="white")
    
    network_table.add_row("Network", f"[cyan]{config.network}[/cyan]")
    network_table.add_row("RPC URL", f"[dim]{config.rpc_url}[/dim]")
    network_table.add_row("WS URL", f"[dim]{config.ws_url}[/dim]")
    network_table.add_row("Program", f"[dim]{config.program_id[:30]}...[/dim]")
    
    console.print(Panel(network_table, title="[bold]🌐 Network[/]", border_style="blue"))
    
    # Filters section
    filters_table = Table(box=None, show_header=False, padding=(0, 2))
    filters_table.add_column(style="dim", width=15)
    filters_table.add_column(style="white")
    
    filters_table.add_row("Min Reward", f"[yellow]{config.min_reward} SOL[/yellow]")
    filters_table.add_row("Max Reward", f"[yellow]{config.max_reward} SOL[/yellow]" if config.max_reward != float('inf') else "[dim]∞[/dim]")
    filters_table.add_row("Datasets", str(config.allowed_datasets) if config.allowed_datasets else "[dim]all[/dim]")
    filters_table.add_row("Only Downloaded", "[green]yes[/green]" if config.only_downloaded else "[red]no[/red]")
    
    console.print(Panel(filters_table, title="[bold]🎯 Filters[/]", border_style="yellow"))
    
    # Automation section
    auto_table = Table(box=None, show_header=False, padding=(0, 2))
    auto_table.add_column(style="dim", width=15)
    auto_table.add_column(style="white")
    
    def bool_badge(val):
        return "[green]ON[/green]" if val else "[red]OFF[/red]"
    
    auto_table.add_row("Auto Claim", bool_badge(config.auto_claim))
    auto_table.add_row("Auto Start", bool_badge(config.auto_start))
    auto_table.add_row("Auto Validate", bool_badge(config.auto_validate))
    auto_table.add_row("Dry Run", bool_badge(config.dry_run))
    auto_table.add_row("Max Concurrent", str(config.max_concurrent_rounds))
    
    console.print(Panel(auto_table, title="[bold]⚡ Automation[/]", border_style="green"))
    
    # Referral section
    ref_table = Table(box=None, show_header=False, padding=(0, 2))
    ref_table.add_column(style="dim", width=15)
    ref_table.add_column(style="white")
    
    if config.referrer:
        ref_table.add_row("Referrer", f"[cyan]{config.referrer[:20]}...[/cyan]")
    else:
        ref_table.add_row("Referrer", "[dim]Not set[/dim]")
    
    console.print(Panel(ref_table, title="[bold]🤝 Referral[/]", border_style="cyan"))
    
    # Paths section
    paths_table = Table(box=None, show_header=False, padding=(0, 2))
    paths_table.add_column(style="dim", width=15)
    paths_table.add_column(style="cyan")
    
    paths_table.add_row("Data Dir", config.data_dir)
    paths_table.add_row("IDL Path", config.idl_path)
    paths_table.add_row("Config", config.config_path)
    
    console.print(Panel(paths_table, title="[bold]📁 Paths[/]", border_style="magenta"))
    
    return 0


def cmd_config_set(args):
    """Set configuration value"""
    config = Config.load()
    
    key = args.key
    value = args.value
    
    if hasattr(config, key):
        field_type = type(getattr(config, key))
        if field_type == bool:
            value = value.lower() in ("true", "1", "yes")
        elif field_type == int:
            value = int(value)
        elif field_type == float:
            value = float(value)
        
        setattr(config, key, value)
        config.save()
        console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = [yellow]{value}[/yellow]")
    else:
        console.print(f"[red]✗ Unknown config key: {key}[/red]")
        return 1
    
    return 0


def cmd_abort(args):
    """Abort round and refund creator"""
    config = Config.load()
    validator = Validator(config)
    
    # Login
    if config.private_key:
        validator.login(config.private_key)
    else:
        console.print("[red]✗ Not logged in. Run: decloud login[/red]")
        return 1
    
    round_id = args.round_id
    
    # Get round info to find creator
    console.print(f"[yellow]⚠ Aborting round #{round_id}...[/yellow]")
    
    try:
        rounds = validator.get_all_rounds()
        round_data = next((r for r in rounds if r.id == round_id), None)
        
        if not round_data:
            console.print(f"[red]✗ Round #{round_id} not found[/red]")
            return 1
        
        if round_data.validator != validator.public_key:
            console.print(f"[red]✗ You are not the validator of this round[/red]")
            return 1
        
        if round_data.status not in ("waitingTrainers", "training", "validating"):
            console.print(f"[red]✗ Cannot abort round in status: {round_data.status}[/red]")
            return 1
        
        tx = validator.abort_round(round_id, round_data.creator)
        console.print(Panel(
            f"[green]✓ Round #{round_id} aborted![/green]\n\n"
            f"[dim]All funds refunded to creator[/dim]\n"
            f"[dim]TX: {tx[:40]}...[/dim]",
            title="Round Aborted",
            border_style="green",
        ))
        
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return 1
    
    return 0


def cmd_info(args):
    """Show system info"""
    print_banner()
    
    config = Config.load()
    manager = DatasetManager(config.data_dir)
    
    downloaded = sum(1 for d in manager.list_datasets() if manager.is_downloaded(d))
    total = len(manager.list_datasets())
    
    info_table = Table(box=None, show_header=False, padding=(0, 2))
    info_table.add_column(style="dim", width=12)
    info_table.add_column(style="white")
    
    info_table.add_row("Network", f"[cyan]{config.network}[/cyan]")
    info_table.add_row("RPC", f"[dim]{config.rpc_url}[/dim]")
    info_table.add_row("Datasets", f"[green]{downloaded}[/green] / [cyan]{total}[/cyan] ready")
    info_table.add_row("Data Dir", f"[dim]{config.data_dir}[/dim]")
    
    console.print(Panel(
        info_table,
        title="[bold]System Info[/]",
        border_style="blue",
    ))
    
    console.print()
    return 0


def cmd_config_list(args):
    """List all config options"""
    console.print()
    
    table = Table(
        title="⚙️ Configuration Options",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="blue",
    )
    
    table.add_column("Key", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Description")
    
    options = [
        ("network", "str", "Network name (devnet/mainnet-beta)"),
        ("rpc_url", "str", "RPC endpoint URL"),
        ("ws_url", "str", "WebSocket endpoint URL"),
        ("referrer", "str", "Referral wallet address (gets 50% of fee)"),
        ("min_reward", "float", "Minimum reward in SOL"),
        ("max_reward", "float", "Maximum reward in SOL"),
        ("only_downloaded", "bool", "Only claim if dataset downloaded"),
        ("auto_claim", "bool", "Auto-claim matching rounds"),
        ("auto_start", "bool", "Auto-start training"),
        ("auto_validate", "bool", "Auto-validate submissions"),
        ("max_concurrent_rounds", "int", "Max concurrent rounds"),
        ("dry_run", "bool", "Monitor only, don't claim"),
        ("poll_interval", "int", "Seconds between polls"),
        ("claim_delay", "float", "Delay before claiming"),
        ("data_dir", "str", "Dataset directory"),
        ("idl_path", "str", "IDL file path"),
    ]
    
    for key, type_, desc in options:
        table.add_row(key, type_, desc)
    
    console.print(table)
    console.print("\n[dim]Set with: decloud config set <key> <value>[/dim]")
    
    return 0


def cmd_setup(args):
    """Interactive setup wizard"""
    print_banner()
    
    console.print(Panel(
        "[cyan]Welcome to DECLOUD Validator Setup![/cyan]\n\n"
        "[dim]This wizard will help you configure your validator.[/dim]",
        title="🚀 Setup Wizard",
        border_style="blue",
    ))
    console.print()
    
    config = Config.load()
    
    # 1. Network selection
    console.print("[bold]1. Select Network[/bold]")
    console.print("   [dim]1)[/dim] devnet (testing)")
    console.print("   [dim]2)[/dim] mainnet-beta (production)")
    
    network_choice = console.input("\n   [cyan]Choice [1/2]:[/cyan] ").strip()
    if network_choice == "2":
        config.set_network("mainnet-beta")
        console.print("   [green]✓[/green] Using mainnet-beta")
    else:
        config.set_network("devnet")
        console.print("   [green]✓[/green] Using devnet")
    
    console.print()
    
    # 2. Private key
    console.print("[bold]2. Wallet Configuration[/bold]")
    console.print("   [dim]Enter your private key (base58) or path to keypair file[/dim]")
    
    key_input = console.input("\n   [cyan]Private key or path:[/cyan] ").strip()
    
    if key_input:
        if key_input.endswith(".json"):
            # It's a file path
            import os
            if os.path.exists(key_input):
                try:
                    from .validator import Validator
                    v = Validator(config)
                    if v.login_from_file(key_input):
                        config.private_key = v._private_key
                        console.print(f"   [green]✓[/green] Wallet loaded: {v.public_key[:20]}...")
                    else:
                        console.print("   [red]✗[/red] Failed to load keypair")
                except Exception as e:
                    console.print(f"   [red]✗[/red] Error: {e}")
            else:
                console.print(f"   [red]✗[/red] File not found: {key_input}")
        else:
            # It's a base58 private key
            config.private_key = key_input
            console.print("   [green]✓[/green] Private key saved")
    
    console.print()
    
    # 3. Referrer
    console.print("[bold]3. Referral (Optional)[/bold]")
    console.print("   [dim]If someone referred you, enter their Solana wallet address.[/dim]")
    console.print("   [dim]They will receive 50% of the platform fee (1% of your earnings).[/dim]")
    
    referrer_input = console.input("\n   [cyan]Referrer wallet (or press Enter to skip):[/cyan] ").strip()
    
    if referrer_input:
        # Basic validation - Solana addresses are 32-44 chars base58
        if len(referrer_input) >= 32 and len(referrer_input) <= 44:
            config.referrer = referrer_input
            console.print(f"   [green]✓[/green] Referrer set: {referrer_input[:20]}...")
        else:
            console.print("   [yellow]⚠[/yellow] Invalid address format, skipping")
    else:
        console.print("   [dim]○ No referrer set[/dim]")
    
    console.print()
    
    # 4. Auto settings
    console.print("[bold]4. Automation Settings[/bold]")
    
    auto_claim = console.input("   [cyan]Auto-claim rounds? [Y/n]:[/cyan] ").strip().lower()
    config.auto_claim = auto_claim != "n"
    
    auto_start = console.input("   [cyan]Auto-start training? [Y/n]:[/cyan] ").strip().lower()
    config.auto_start = auto_start != "n"
    
    auto_validate = console.input("   [cyan]Auto-validate submissions? [Y/n]:[/cyan] ").strip().lower()
    config.auto_validate = auto_validate != "n"
    
    console.print()
    
    # 5. Filters
    console.print("[bold]5. Reward Filters[/bold]")
    
    min_reward = console.input("   [cyan]Minimum reward in SOL (default 0):[/cyan] ").strip()
    if min_reward:
        try:
            config.min_reward = float(min_reward)
        except ValueError:
            pass
    
    max_reward = console.input("   [cyan]Maximum reward in SOL (default unlimited):[/cyan] ").strip()
    if max_reward:
        try:
            config.max_reward = float(max_reward)
        except ValueError:
            pass
    
    console.print()
    
    # Save config
    config.save()
    
    console.print(Panel(
        "[green]✓ Configuration saved![/green]\n\n"
        f"[dim]Network:[/dim] {config.network}\n"
        f"[dim]Referrer:[/dim] {config.referrer or 'None'}\n"
        f"[dim]Auto-claim:[/dim] {config.auto_claim}\n"
        f"[dim]Min reward:[/dim] {config.min_reward} SOL\n\n"
        "[cyan]Run [bold]decloud validate start[/bold] to begin![/cyan]",
        title="🎉 Setup Complete",
        border_style="green",
    ))
    
    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        prog="decloud",
        description="DECLOUD Validator CLI - Decentralized Cloud for AI Training"
    )
    parser.add_argument("--version", action="version", version="DECLOUD 0.1.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Login
    login_parser = subparsers.add_parser("login", help="Login with private key")
    login_parser.add_argument("private_key", nargs="?", help="Base58 private key")
    login_parser.add_argument("--keyfile", "-f", help="Path to keypair JSON file")
    login_parser.add_argument("--save", "-s", action="store_true", help="Save to config")
    login_parser.set_defaults(func=cmd_login)
    
    # Datasets
    datasets_parser = subparsers.add_parser("datasets", help="Manage datasets")
    datasets_sub = datasets_parser.add_subparsers(dest="datasets_cmd")
    
    dl_parser = datasets_sub.add_parser("download", help="Download datasets")
    dl_parser.add_argument("--minimal", "-m", action="store_true", help="Download minimal pack")
    dl_parser.add_argument("--category", "-c", help="Download specific category")
    dl_parser.add_argument("--dataset", "-d", help="Download specific dataset")
    dl_parser.add_argument("--include-large", action="store_true", help="Include large datasets")
    dl_parser.set_defaults(func=cmd_datasets_download)
    
    list_parser = datasets_sub.add_parser("list", help="List datasets")
    list_parser.add_argument("--status", "-s", action="store_true", help="Show download status")
    list_parser.set_defaults(func=cmd_datasets_list)
    
    # Validate
    validate_parser = subparsers.add_parser("validate", help="Validator operations")
    validate_sub = validate_parser.add_subparsers(dest="validate_cmd")
    
    start_parser = validate_sub.add_parser("start", help="Start validator")
    start_parser.add_argument("--private-key", "-k", help="Private key")
    start_parser.add_argument("--min-reward", type=float, help="Minimum reward filter (SOL)")
    start_parser.add_argument("--max-reward", type=float, help="Maximum reward filter (SOL)")
    start_parser.add_argument("--dataset", "-d", help="Filter by specific dataset")
    start_parser.add_argument("--dry-run", action="store_true", help="Monitor only")
    start_parser.add_argument("--no-websocket", action="store_true", help="Use polling")
    start_parser.add_argument("--no-auto-claim", action="store_true", help="Disable auto-claim")
    start_parser.set_defaults(func=cmd_validate_start)
    
    # Rounds
    rounds_parser = subparsers.add_parser("rounds", help="Round operations")
    rounds_sub = rounds_parser.add_subparsers(dest="rounds_cmd")
    
    rlist_parser = rounds_sub.add_parser("list", help="List all rounds")
    rlist_parser.set_defaults(func=cmd_rounds_list)
    
    # Abort
    abort_parser = subparsers.add_parser("abort", help="Abort round and refund creator")
    abort_parser.add_argument("round_id", type=int, help="Round ID to abort")
    abort_parser.set_defaults(func=cmd_abort)
    
    # Config
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_sub = config_parser.add_subparsers(dest="config_cmd")
    
    show_parser = config_sub.add_parser("show", help="Show configuration")
    show_parser.set_defaults(func=cmd_config_show)
    
    set_parser = config_sub.add_parser("set", help="Set configuration value")
    set_parser.add_argument("key", help="Config key")
    set_parser.add_argument("value", help="Config value")
    set_parser.set_defaults(func=cmd_config_set)
    
    clist_parser = config_sub.add_parser("list", help="List all config options")
    clist_parser.set_defaults(func=cmd_config_list)
    
    # Info
    info_parser = subparsers.add_parser("info", help="Show system info")
    info_parser.set_defaults(func=cmd_info)
    
    # Setup
    setup_parser = subparsers.add_parser("setup", help="Initial setup wizard")
    setup_parser.set_defaults(func=cmd_setup)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not args.command:
        cmd_info(args)
        console.print()
        parser.print_help()
        return 0
    
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())