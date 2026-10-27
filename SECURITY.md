# Security reporting

Only the current unreleased candidate is maintained. Do not open public issues with
credentials or exploit payloads containing private data. Once the repository is public,
use GitHub's private vulnerability reporting if enabled; no private inbox is claimed
until it is configured. For now, share a redacted report directly with the maintainer.

The runtime trusts installed Python tools. See docs/threat-model.md before using it.
Report authorization bypasses, filesystem scope escapes and accidental data retention.
