# ADR 1: Offline core, SQLite metadata, explicit contracts

Status: accepted for the local v0.1 candidate.

An offline fixture makes failure cases reproducible without keys, cost or nondeterminism.
It is visibly distinguished from the real, opt-in loopback Ollama adapter.
SQLite gives an inspectable single-file event journal without service dependencies.
Storing only metadata reduces accidental prompt/document disclosure but prevents full
computation replay. Schemas plus explicit policies keep authorization in application
code, independent of model obedience. Async functions make cancellation testable, but
untrusted blocking extensions require a future process boundary.
