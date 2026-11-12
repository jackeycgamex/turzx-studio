"""Windowless per-user startup entry. Never opens the controller or a terminal."""
from pathlib import Path
import json
import sys
import traceback
import urllib.request

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime'


def main():
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / 'background-start.log').open('a', encoding='utf-8', buffering=1) as log:
        sys.stdout = sys.stderr = log
        try:
            try:
                with urllib.request.urlopen('http://127.0.0.1:8765/api/state', timeout=2) as response:
                    state = json.load(response)
                if state.get('device', {}).get('vid') == '1CBE':
                    return 0
            except (OSError, ValueError):
                pass
            from server import main as serve
            serve()
            return 0
        except Exception:
            traceback.print_exc(file=log)
            return 1
        finally:
            sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__


if __name__ == '__main__':
    raise SystemExit(main())
