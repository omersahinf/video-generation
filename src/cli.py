#!/usr/bin/env python3
"""CLI entry point for the explainer video generator."""
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent))


@click.command()
@click.argument("prompt", required=False)
@click.option("--style", "-s", default="whiteboard", help="Visual style name")
@click.option("--output", "-o", default=None, type=Path, help="Output MP4 path")
@click.option("--scenes", "-n", default=5, type=int, help="Number of scenes (3-8)")
@click.option("--list-styles", "list_styles", is_flag=True, help="List available styles")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
def main(
    prompt: str | None,
    style: str,
    output: Path | None,
    scenes: int,
    list_styles: bool,
    quiet: bool,
) -> None:
    """Generate an explainer video from a text prompt.

    Examples:\n
      python src/cli.py "Explain how DNS works"\n
      python src/cli.py "What is machine learning" --style chalkboard_color\n
      python src/cli.py --list-styles
    """
    if list_styles:
        from styles.registry import list_styles as _ls
        click.echo("\nAvailable styles:\n")
        canvas = [(k, n, c) for k, n, c in _ls() if c == "canvas"]
        sketch = [(k, n, c) for k, n, c in _ls() if c == "sketch"]
        click.echo("  CANVAS STYLES")
        for key, name, _ in canvas:
            click.echo(f"    {key:<22} — {name}")
        click.echo("\n  SKETCH STYLES")
        for key, name, _ in sketch:
            click.echo(f"    {key:<22} — {name}")
        click.echo()
        return

    if not prompt:
        click.echo("Error: provide a PROMPT or use --list-styles.", err=True)
        sys.exit(1)

    scenes = max(3, min(8, scenes))

    from pipeline import run
    try:
        output_path = run(
            prompt=prompt,
            style_name=style,
            output_path=output,
            num_scenes=scenes,
            verbose=not quiet,
        )
        click.echo(f"\nVideo: {output_path}")
    except RuntimeError as e:
        click.echo(f"\nError: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
