"""The catalog's command line.

python -m u6g_catalog build <catalog_dir> --out <dir>     validate, index and archive the catalog
python -m u6g_catalog keygen --out <dir>                  a signing key pair for a development machine
python -m u6g_catalog sign <snapshot> --key <pem>         write <snapshot>.sig.json
python -m u6g_catalog verify <snapshot> --pub <pem>       check <snapshot>.sig.json
python -m u6g_catalog serve --index <index.json>          serve the index over REST
python -m u6g_catalog import-tfs <tfs_dir> --source <owner/repo@commit> --binding <entry.yaml>
                                                          write what TeraFlowSDN declares into a binding"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from u6g_catalog.build import build_index, load
from u6g_catalog.snapshot import archive, keygen, sha256, sign, verify

SNAPSHOT = "catalog-snapshot.tar.gz"


def cmd_build(args: argparse.Namespace) -> int:
    catalog = load(args.catalog_dir)
    for f in catalog.findings:
        print(f"{f.path}: [{f.rule}] {f.message}", file=sys.stderr)
    if catalog.findings:
        print(f"u6g-catalog: {len(catalog.findings)} findings; nothing written", file=sys.stderr)
        return 1
    index = build_index(catalog)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    snapshot = archive(catalog, index)
    (args.out / SNAPSHOT).write_bytes(snapshot)
    print(f"u6g-catalog: {len(index['entries'])} entries; {SNAPSHOT} {sha256(snapshot)}")
    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    private_pem, public_pem = keygen()
    args.out.mkdir(parents=True, exist_ok=True)
    key = args.out / "catalog-signing.key"
    key.write_bytes(private_pem)
    os.chmod(key, 0o600)
    (args.out / "catalog-signing.pub").write_bytes(public_pem)
    print(f"u6g-catalog: {key} and catalog-signing.pub written; keep the private key out of the repository")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    signature = sign(args.snapshot.read_bytes(), args.key.read_bytes())
    target = args.snapshot.with_name(args.snapshot.name + ".sig.json")
    target.write_text(json.dumps(signature, indent=2) + "\n")
    print(f"u6g-catalog: {target} for {signature['digest']}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    signature = json.loads(args.snapshot.with_name(args.snapshot.name + ".sig.json").read_text())
    try:
        verify(args.snapshot.read_bytes(), signature, args.pub.read_bytes())
    except ValueError as err:
        print(f"u6g-catalog: {err}", file=sys.stderr)
        return 1
    print(f"u6g-catalog: the signature holds for {signature['digest']}")
    return 0


def cmd_import_tfs(args: argparse.Namespace) -> int:
    """Write what a TeraFlowSDN source tree declares into the model of a controller binding entry."""
    from u6g_catalog.tfs import read_model

    entry = yaml.safe_load(args.binding.read_text())
    model = {"source": args.source, **read_model(args.tfs_dir)}
    if entry.get("model") == model:
        print(f"u6g-catalog: {args.binding} already holds the model of {args.source}")
        return 0
    if args.check:
        print(f"u6g-catalog: {args.binding} differs from the model of {args.source}", file=sys.stderr)
        return 1
    entry["model"] = model
    args.binding.write_text(yaml.safe_dump(entry, sort_keys=False, allow_unicode=True, width=110))
    counts = ", ".join(f"{len(v)} {k}" for k, v in model.items() if isinstance(v, list))
    print(f"u6g-catalog: {args.binding} now holds the model of {args.source}: {counts}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from u6g_catalog.app import create_app

    text = args.index.read_bytes()
    uvicorn.run(create_app(json.loads(text), sha256(text)), host=args.host, port=args.port)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="u6g-catalog", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("catalog_dir", type=Path)
    build.add_argument("--out", type=Path, required=True)
    build.set_defaults(run=cmd_build)
    gen = commands.add_parser("keygen")
    gen.add_argument("--out", type=Path, required=True)
    gen.set_defaults(run=cmd_keygen)
    sgn = commands.add_parser("sign")
    sgn.add_argument("snapshot", type=Path)
    sgn.add_argument("--key", type=Path, required=True)
    sgn.set_defaults(run=cmd_sign)
    ver = commands.add_parser("verify")
    ver.add_argument("snapshot", type=Path)
    ver.add_argument("--pub", type=Path, required=True)
    ver.set_defaults(run=cmd_verify)
    imp = commands.add_parser("import-tfs")
    imp.add_argument("tfs_dir", type=Path)
    imp.add_argument("--source", required=True, help="the repository and commit read, as owner/repo@commit")
    imp.add_argument("--binding", type=Path, required=True, help="the controller binding entry to write")
    imp.add_argument("--check", action="store_true", help="report a difference and write nothing")
    imp.set_defaults(run=cmd_import_tfs)
    serve = commands.add_parser("serve")
    serve.add_argument("--index", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8081)
    serve.set_defaults(run=cmd_serve)
    args = parser.parse_args(argv)
    status: int = args.run(args)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
