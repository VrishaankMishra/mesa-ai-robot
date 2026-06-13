"""MeSA 2.0 orchestrator entry point.

Phase 0 stub. The full event-bus orchestrator (ENG-004, Week 6) will launch the
vision, audio, and decision-engine workers, all communicating over a single
``multiprocessing.Queue``. For now this just loads config and reports readiness.
"""

from __future__ import annotations

from mesa import __version__
from mesa.config import load_config


def main() -> None:
    config = load_config()
    print(f"MeSA {__version__} — config loaded.")
    print(f"  wake word        : {config.get('voice', {}).get('wake_word')}")
    print(f"  detection conf   : {config.get('detection', {}).get('confidence_threshold')}")
    print(f"  lying trigger (s): {config.get('pose', {}).get('lying_trigger_seconds')}")
    print("Subsystems not yet wired up — see docs/IMPLEMENTATION.md (Week 6, ENG-004).")


if __name__ == "__main__":
    main()
