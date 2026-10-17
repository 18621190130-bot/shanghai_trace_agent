"""Explicit opt-in live DeepSeek intent extraction; no provider call for other modes."""

# Support direct execution from any working directory.
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tools.demos.route_entry_demo import main


if __name__ == "__main__":
    raise SystemExit(main(live=True))
