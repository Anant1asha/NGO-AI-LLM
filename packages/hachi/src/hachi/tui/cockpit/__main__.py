"""Run the Hachi Cockpit as a standalone surface.

    python -m hachi.tui.cockpit                          # offline / placeholder data
    python -m hachi.tui.cockpit --base-url URL --token T # live, against a gateway

The cockpit is REST-only: with ``--base-url`` (or ``HACHI_GATEWAY_URL``) it talks
to a running ``hachi gateway`` over HTTP; without one it renders representative
placeholder data so the surface is always demonstrable.

This is the self-contained entry point for Phase A. Wiring ``hachi run`` to launch
the cockpit is a one-line follow-up in ``hachi.cli.main`` once that module settles.
"""

from __future__ import annotations

import argparse
import os

from hachi.tui.cockpit.app import CockpitApp


def main() -> None:
    """Parse arguments and run the cockpit app."""
    parser = argparse.ArgumentParser(
        prog="python -m hachi.tui.cockpit",
        description="Run the Hachi Cockpit terminal UI.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("HACHI_GATEWAY_URL"),
        help="Gateway base URL (e.g. http://127.0.0.1:8787). "
        "Falls back to $HACHI_GATEWAY_URL; omit for offline placeholder mode.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HACHI_GATEWAY_TOKEN"),
        help="Bearer token for the gateway. Falls back to $HACHI_GATEWAY_TOKEN.",
    )
    args = parser.parse_args()

    CockpitApp(base_url=args.base_url, token=args.token).run()


if __name__ == "__main__":
    main()
