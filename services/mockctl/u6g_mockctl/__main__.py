"""Run the mock controller: python -m u6g_mockctl --config <file> [--host H] [--port P]."""

import argparse
import sys
from pathlib import Path

import uvicorn

from u6g_mockctl.app import create_app
from u6g_mockctl.config import load_config

TOPOLOGIES = Path(__file__).parent / "topologies"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="u6g-mockctl", description=__doc__)
    parser.add_argument(
        "--config", type=Path, required=True, help=f"a configuration; examples in {TOPOLOGIES}"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(load_config(args.config)), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
