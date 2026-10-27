# Runtime architecture

`Provider.respond(messages, tools, max_tokens)` yields a validated `Turn`. The runtime
checks aggregate usage before executing calls. A response with no calls terminates.
Each call passes allowlist, registry lookup, input validation and argument hashing.
Side effects additionally need a trusted `Approval` with exact run/call/tool/hash scope.
Only then is the tool awaited. The output schema and byte budget are enforced before
returning content to the provider. Reusing a call ID with different arguments is an error.

A session is single-use. Provider instances are per run; share the registry only when
its handlers are safe for concurrent use. The event callback runs synchronously and
must be fast and nonthrowing. SQLite writes complete before the callback is invoked.
One EventStore connection belongs to its creating thread. The composite run/sequence
primary key and ordered replay separate concurrent runs.

The outer timeout covers providers and async tools. Cancellation wakes a second task,
cancels the execution task and awaits cleanup. Cooperative cancellation cannot stop
blocking or cancellation-suppressing third-party Python code. Use process isolation for
untrusted extensions; this release intentionally has no plugin loader or shell tool.

Events contain a schema version, run ID, sequence, event name, tool identifier,
hashed call identifier, SHA-256 of normalized arguments and stable result code. They do not
contain message text or outputs. Approval reason text stays in the trusted caller's
policy; the event records `operator_approved` and the reviewed argument digest.
Call identifiers are hashed before persistence; provider-supplied identifiers cannot
copy raw personal data into the journal. Hashes still permit correlation.
