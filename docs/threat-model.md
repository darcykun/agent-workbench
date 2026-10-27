# Threat model

Treat model responses and document contents as untrusted data. They cannot modify the
Policy or register tools. The caller creates these trusted objects outside the provider.
No built-in tool executes a shell, writes files, or accesses the network. A document
can ask the model to run forbidden tools; the allowlist still denies those requests.

The document reader rejects absolute paths, traversal, empty components, backslashes,
symlinks at every descendant component, nonregular files and files over 8192 bytes.
The root is operator-controlled and must be a real directory, not a symlink. It uses
POSIX APIs and is intentionally unsupported on Windows. Allowed documents go to the
selected model; metadata logging does not make that model input private.

The journal omits prompts and results. Tool names and hashed call IDs/arguments are still metadata:
protect the database with filesystem access controls. Hashes of predictable arguments can be guessed. There is no encryption at
rest, authentication service, tenant isolation, or durable exactly-once side effects.
Delete trace.sqlite3 to remove a local journal; manage backups separately.

Budgets rely on cooperative async code and accurate provider usage. They are not a
CPU/memory sandbox or a billing meter. No paid provider is configured. Approvals must
be issued by a trusted operator after inspecting normalized arguments; never allow
the model to construct approvals or supply the execution policy.
