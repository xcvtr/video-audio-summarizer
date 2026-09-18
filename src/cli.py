"""CLI interface for video summarizer."""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from src.config import Config, ConfigurationError
from src.processor import VideoProcessor


console = Console()


def display_banner() -> None:
    """Display application banner."""
    banner = """
[bold cyan]Video Summarizer[/bold cyan]
Automatic video summarization with AI
    """
    console.print(Panel(banner, border_style="cyan"))


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Automatic video summarization with speech recognition and AI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "files",
        nargs="+",
        help="Path(s) to video or audio file(s) to process"
    )
    
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Base directory for output (overrides config.yaml)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--debug-screenshots",
        help="Debug mode: only generate screenshots from existing results directory"
    )
    
    parser.add_argument(
        "--reprocess-ai",
        help="Reprocess AI summary from existing transcript directory"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point for CLI application.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    display_banner()
    
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Load configuration
        console.print(f"[cyan]Loading configuration from {args.config}...[/cyan]")
        try:
            config = Config.load(args.config)
        except ConfigurationError as e:
            console.print(f"[bold red]Configuration Error:[/bold red] {e}")
            return 1
        
        # Override output directory if specified
        if args.output_dir:
            config.output_base_dir = args.output_dir
        
        console.print("[green][OK][/green] Configuration loaded successfully")
        
        # Initialize processor
        console.print("[cyan]Initializing video processor...[/cyan]")
        try:
            processor = VideoProcessor(config)
        except Exception as e:
            console.print(f"[bold red]Initialization Error:[/bold red] {e}")
            return 1
        
        console.print("[green][OK][/green] Processor initialized")
        
        # Check for debug mode
        if args.debug_screenshots:
            console.print(f"\n[bold]Debug mode: Generating screenshots from existing results[/bold]")
            result = processor.debug_generate_screenshots(args.debug_screenshots, args.files[0])
            results = [result]
        elif args.reprocess_ai:
            console.print(f"\n[bold]Reprocessing AI summary from existing transcript[/bold]")
            result = processor.reprocess_ai_summary(args.reprocess_ai, args.files[0])
            results = [result]
        else:
            # Process files (video or audio)
            console.print(f"\n[bold]Processing {len(args.files)} file(s)...[/bold]")
            results = processor.process_multiple(args.files)
        
        # Check if any processing succeeded
        success_count = sum(1 for r in results if r.success)
        
        if success_count == 0:
            console.print("\n[bold red]All videos failed to process[/bold red]")
            return 1
        
        console.print("\n[bold green]Processing completed successfully![/bold green]")
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Processing interrupted by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if args.verbose if 'args' in locals() else False:
            import traceback
            console.print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
