# Makefile: the commands of AGENTS.md (guide Sections 24.8 and 26.2)
.PHONY: setup gen check dev-up dev-down it conformance bench images sbom scan sign publish
RUST := --manifest-path runtime/rust/Cargo.toml

setup:
	uv sync --all-packages --locked
	cargo fetch $(RUST)
	buf dep update
	uv run pre-commit install

# The semantic objects' proto form first, then the Python models, the Python protobuf and gRPC code, and the
# Rust types; no step needs the network (docs/design/contracts-and-generation.md).
gen:
	uv run python -m u6g.tools.gen_proto schemas proto
	uv run python -m u6g.tools.gen_models schemas runtime/python/u6g/generated
	uv run python -m u6g.tools.gen_grpc proto runtime/python
	cargo run -q $(RUST) -p u6g-typegen -- schemas proto runtime/rust/u6g-types/src

check:
	uv run pre-commit run --all-files
	uv run mypy .
	uv run pytest -m "not integration"
	cargo test -q $(RUST)
	$(MAKE) gen
	git diff --exit-code

dev-up:       ; uv run u6g dev up
dev-down:     ; uv run u6g dev down
it:           ; uv run pytest -m integration conformance/sequences
conformance:  ; uv run u6g test --conformance --faults all
bench:        ; uv run pytest conformance/bench --benchmark-compare && cargo bench $(RUST) -p u6g-runtime-rt
images sbom scan sign publish: ; uv run u6g build --stage $@    # guide Section 19.3
