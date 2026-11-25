"""Generate the Python code of the Protocol Buffers: messages, gRPC stubs and their type stubs.

Usage: python -m u6g.tools.gen_grpc <proto_dir> <python_root>

Every file under proto_dir is compiled with the protoc that grpcio-tools bundles and the plugins of
mypy-protobuf, so that generation needs no network and its versions are pinned by uv.lock. The modules land
at the path of their package under python_root: proto/u6g/logic/v1/logic.proto becomes the module
u6g.logic.v1.logic_pb2, with logic_pb2_grpc for the service and .pyi stubs for both. Generated modules found
under python_root/u6g are removed first, so that a removed proto leaves no stale module."""

import shutil
import sys
from importlib import resources
from pathlib import Path

from grpc_tools import protoc

SUFFIXES = ("_pb2.py", "_pb2.pyi", "_pb2_grpc.py", "_pb2_grpc.pyi")
INIT = '"""Generated from the Protocol Buffers under proto/ by u6g.tools.gen_grpc."""\n'


def plugin(name: str) -> str:
    found = shutil.which(name, path=str(Path(sys.executable).parent))
    if found is None:
        raise SystemExit(f"gen_grpc: the plugin {name} is missing; run make setup")
    return found


def clean(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name.endswith(SUFFIXES):
            path.unlink()


def mark_packages(python_root: Path, generated: list[Path]) -> None:
    """Give every directory of a generated module an __init__.py, keeping those that exist."""
    for module in generated:
        directory = module.parent
        while directory != python_root:
            init = directory / "__init__.py"
            if not init.exists():
                init.write_text(INIT)
            directory = directory.parent


def generate(proto_dir: Path, python_root: Path) -> int:
    files = sorted(p.relative_to(proto_dir).as_posix() for p in proto_dir.rglob("*.proto"))
    clean(python_root / "u6g")
    if not files:
        print(f"gen_grpc: no proto files under {proto_dir}; nothing to generate")
        return 0
    include = resources.files("grpc_tools") / "_proto"
    out = str(python_root)
    args = [
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"-I{include}",
        f"--plugin=protoc-gen-mypy={plugin('protoc-gen-mypy')}",
        f"--plugin=protoc-gen-mypy_grpc={plugin('protoc-gen-mypy_grpc')}",
        f"--python_out={out}",
        f"--grpc_python_out={out}",
        f"--mypy_out={out}",
        f"--mypy_grpc_out={out}",
        *files,
    ]
    status = protoc.main(args)
    if status != 0:
        print(f"gen_grpc: protoc failed with status {status}", file=sys.stderr)
        return int(status)
    generated = sorted(p for p in (python_root / "u6g").rglob("*") if p.name.endswith(SUFFIXES))
    mark_packages(python_root, generated)
    print(f"gen_grpc: {len(files)} proto files -> {len(generated)} modules and stubs under {python_root}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return generate(Path(argv[0]), Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
