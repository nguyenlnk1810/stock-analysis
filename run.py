#!/usr/bin/env python3
"""AI Stock Analyst - Entry point"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from src.app import main
    main()
