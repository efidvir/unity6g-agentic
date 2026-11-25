"""Generate the Python models from the JSON Schemas of the contracts.

Usage: python -m u6g.tools.gen_models <schemas_dir> <out_dir>

The models are Pydantic models made by datamodel-code-generator (guide Section 19.2), one module per schema
file: schemas/envelope/intent.schema.json becomes u6g.generated.envelope.intent_schema. Shared string types
become type aliases, so that fields hold plain values; JSON names become snake_case attributes with the JSON
name as alias; fields that the platform computes keep their readOnly mark in json_schema_extra.

The output directory is emptied first, so that a removed schema leaves no stale module. The result is
checked in, and the regeneration check of make check compares it with the schemas."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OPTIONS = [
    "--input-file-type",
    "jsonschema",
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--target-python-version",
    "3.12",
    "--use-standard-collections",
    "--use-union-operator",
    "--use-annotated",
    "--field-constraints",
    "--snake-case-field",
    "--allow-population-by-field-name",
    "--use-title-as-name",
    "--use-schema-description",
    "--use-field-description",
    "--output-datetime-class",
    "AwareDatetime",
    "--enum-field-as-literal",
    "all",
    "--field-extra-keys",
    "readOnly",
    "--use-type-alias",
    "--strict-nullable",
    "--disable-timestamp",
    "--formatters",
    "black",
    "isort",
]

EMPTY_PACKAGE = '"""Models generated from schemas/; none yet."""\n'


def generate(schemas: Path, out: Path) -> int:
    if out.name != "generated":
        print(f"gen_models: refusing to empty {out}: the directory must be named generated", file=sys.stderr)
        return 2
    found = sorted(schemas.rglob("*.schema.json"))
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if not found:
        (out / "__init__.py").write_text(EMPTY_PACKAGE)
        print(f"gen_models: no schemas under {schemas}; nothing to generate")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "schemas"
        for path in found:
            target = staged / path.relative_to(schemas)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        command = [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(staged),
            "--output",
            str(out),
            *OPTIONS,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        return result.returncode
    modules = sorted(out.rglob("*.py"))
    print(f"gen_models: {len(found)} schemas -> {len(modules)} modules in {out}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return generate(Path(argv[0]), Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
