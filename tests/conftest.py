import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Enable approximation-based fallbacks while running the lightweight test suite.
os.environ.setdefault("ASTROLOGY_SOFTWARE_ALLOW_APPROX", "1")
