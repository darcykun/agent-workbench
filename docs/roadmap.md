# Capability roadmap

## v0.1 — current local candidate

Bounded runtime, scoped read/calculator tools, approvals, event journal, fixture CLI,
Ollama adapter contract tests, packaging and CI. Publication is pending owner review.

## v0.2 — runtime hardening

1. Durable operation journal: pending/succeeded/unknown outcomes; crash injection tests.
2. Real installed-model smoke run: record model digest, output usage and failure behavior.
3. Process-isolated tool worker with hard cancellation and resource-limit tests.
4. Prompt-injection fixture suite crossing a real MCP client boundary.

## v0.3 — integration

Build `mcp-toolbox` with the official SDK only after v0.1 is reviewed. Exercise schema
introspection, session lifecycle and read scopes through a real protocol client.
Then add a small licensed retrieval corpus with hand-checked metric cases in
`rag-eval-lab`. No placeholder repositories or scheduled activity commits.
