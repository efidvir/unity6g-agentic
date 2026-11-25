"""Entry point of the u6g command line. The commands arrive with their work items (guide Annex F.13)."""

import argparse
import sys

import u6g


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u6g", description="UNITY-6G agentic framework command line")
    parser.add_argument("--version", action="version", version=f"u6g {u6g.__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
