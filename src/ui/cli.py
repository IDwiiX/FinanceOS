# src/ui/cli.py
"""Terminal UI skeleton. Replace the bodies with your own."""
from __future__ import annotations
import typer

app = typer.Typer()

@app.command()
def menu() -> None:
    """Launch the interactive finance menu."""
    # TODO: build your menu here.
    print("FinanceOS CLI — menu not implemented yet.")

if __name__ == "__main__":
    app()
