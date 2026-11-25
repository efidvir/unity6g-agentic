"""Work item 0.1: the tree of guide Section 26.1, with an importable package in every directory."""

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    "AGENTS.md",
    "STATE.md",
    "README.md",
    "Makefile",
    "pyproject.toml",
    "rust-toolchain.toml",
    "buf.yaml",
    "buf.gen.yaml",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    "runtime/rust/Cargo.toml",
]

DIRECTORIES = [
    "schemas",
    "proto",
    "openapi",
    "crds",
    "catalog",
    "runtime/python/u6g",
    "runtime/rust/u6g-runtime-rt",
    "runtime/rust/u6g-types",
    "services",
    "adapters",
    "cli",
    "conformance",
    "deploy/dev",
    "deploy/lab",
    "deploy/testbed",
    "observability",
    "examples/agents",
    "docs/design",
]

RUNTIME = ["runtime", "sdk", "ms", "ae", "de", "act", "cond", "state", "authority", "generated", "tools"]
SERVICES = [
    "admission",
    "registry",
    "catalog",
    "eval",
    "agenthost",
    "idmo_ext",
    "mediator",
    "dt",
    "mockctl",
    "mockorch",
]
ADAPTERS = ["sources", "southbound", "ran", "idmo"]

PACKAGES = (
    ["u6g"]
    + [f"u6g.{name}" for name in RUNTIME]
    + [f"u6g_{name}" for name in SERVICES]
    + [f"u6g_adapters_{name}" for name in ADAPTERS]
    + ["u6g_cli", "u6g_conformance"]
)


@pytest.mark.parametrize("name", FILES)
def test_file_present(name: str) -> None:
    assert (ROOT / name).is_file(), name


@pytest.mark.parametrize("name", DIRECTORIES)
def test_directory_present(name: str) -> None:
    assert (ROOT / name).is_dir(), name


@pytest.mark.parametrize("module", PACKAGES)
def test_package_imports(module: str) -> None:
    importlib.import_module(module)


def test_cli_reports_its_version(capsys: pytest.CaptureFixture[str]) -> None:
    from u6g_cli.main import main

    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.startswith("u6g 0.1.0")
