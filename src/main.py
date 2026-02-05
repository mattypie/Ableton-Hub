"""Main entry point for Ableton Hub application."""

import os
import sys

# Ensure the src package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import AbletonHubApp


def main():
    """Run the Ableton Hub application."""
    app = AbletonHubApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
