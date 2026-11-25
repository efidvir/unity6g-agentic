# Makefile: the commands of AGENTS.md (guide Sections 24.8 and 26.2)
.PHONY: setup gen check dev-up dev-down it conformance bench images sbom scan sign publish
RUST := --manifest-path runtime/rust/Cargo.toml

setup:
	uv sync --all-packages
	cargo fetch $(RUST)
	buf dep update
	uv run pre-commit install

gen:
	@if [ -n "$$(find proto -name '*.proto' -print -quit)" ]; then buf generate; \
	  else echo "buf: no .proto files under proto/; nothing to generate"; fi
	uv run python -m u6g.tools.gen_models schemas runtime/python/u6g/generated
	cargo run -q $(RUST) -p u6g-typegen -- schemas runtime/rust/u6g-types/src

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
