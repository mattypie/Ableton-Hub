"""
Ableton Hub Launcher (No Console Window)
This file can be double-clicked to run Ableton Hub without showing a console window.
Rename this file to .pyw extension if needed (Windows will recognize .pyw files).
"""

import sys
import os

# Ensure the src package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import AbletonHubApp

if __name__ == "__main__":
    app = AbletonHubApp(sys.argv)
    sys.exit(app.run())
