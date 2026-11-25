"""Generate the Python models from the JSON Schemas of the contracts.

Usage: python -m u6g.tools.gen_models <schemas_dir> <out_dir>

Work item 0.1 provides the entry point; work item 0.2 adds the generation, so that `make gen` and the
regeneration check of `make check` run from the first commit."""

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    schemas, out = Path(argv[0]), Path(argv[1])
    found = sorted(schemas.rglob("*.schema.json"))
    if found:
        print(
            f"gen_models: {len(found)} schemas found, and the generator arrives with work item 0.2",
            file=sys.stderr,
        )
        return 1
    out.mkdir(parents=True, exist_ok=True)
    print(f"gen_models: no schemas under {schemas}; nothing to generate")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
