# ObjectGraph Conformance Suite

This directory contains a machine-verifiable conformance suite for the ObjectGraph (`.og`) file format as defined in `../og-spec-v1.0.md`. Third-party parser implementers should run these checks to verify their implementation agrees with the reference parser.

The suite consists of three fixture files in `fixtures/` and a declaration file `conformance.json` that specifies the expected parse results for each fixture. Each fixture exercises a specific slice of the spec: `01-minimal.og` covers the smallest valid file, `02-full-node.og` exercises every node-level tag, and `03-scoped.og` verifies scope-filtering behaviour. A conforming parser must parse all three fixtures without error and satisfy every assertion listed in `conformance.json`. Assertions use dot-notation paths (e.g., `meta.title`) and array indexing (e.g., `nodes[0].name`) with two condition types: `equals` for exact matches and `contains` for substring/membership checks.

To run the suite against the reference implementation, execute:

```
uv run python -m pytest tests/test_p5_01_conformance.py -v
```
