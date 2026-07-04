# Thinking Memory Documents

The memory model uses four document types. Their machine-readable definitions live in `schemas/`.

## Profile

`profile.yaml` is the current, revisioned projection of the user's explicitly confirmed long-term thinking models.

It contains six sections:

- `collaboration_preferences`;
- `definitions`;
- `working_models`;
- `recurring_inquiry_moves`;
- `unresolved_tensions`;
- `long_term_questions`.

Every entry has an `id`, `status`, and one or more `evidence` session ids. Although the schema recognizes `observed`, `proposed`, `confirmed`, and `retired`, new active Profile content must enter as `confirmed`. `observed` and `proposed` belong in session or Patch review until the user confirms them.

`profile_revision` increments once for each successfully applied Patch.

## Thread

A Thread represents one concrete line of inquiry, such as "stability and freedom at work." It stores the current question, framing, assumptions, tensions, unknowns, next probe, linked Profile models, and Session references.

Threads are operational context. They are separate from the Profile so that temporary projects and unfinished questions do not become long-term claims about the user.

The runtime `threads.yaml` file is a container:

```yaml
schema_version: 1
threads: []
```

Each item in `threads` conforms to `schemas/thread.schema.json`.

## Session

A Session Record is immutable evidence from one closed conversation. It records a structured transition from the user's initial framing to their final framing.

Session Markdown files use YAML front matter whose fields conform to `schemas/session.schema.json`. The Markdown body may contain a short human-readable note, but it must not contain a full transcript.

The `user_quote_anchors` field contains one to three short verbatim excerpts written by the user. AI summaries must never be stored as user quotes.

## Patch

A Patch is a reviewable set of candidate changes to the Profile. Its lifecycle is:

```text
pending -> confirmed -> applied
        \-> rejected
```

`pending` means the AI has proposed the change. `confirmed` means the user explicitly accepted it. Only a `confirmed` Patch can be applied. `applied` means the CLI committed it at the expected Profile revision.

Each change names an operation, target section, target id, proposed value, evidence, and reason. A Patch is tied to `base_profile_revision` to prevent stale writes.

## Relationship

```text
Thread ---- references ----> Session
  |                         evidence
  |                            |
  +---- links -----------> Profile <---- confirmed Patch
                                  |
                                  +---- Change Log
```

Sessions provide evidence. Patches propose or confirm mutations. The Profile represents current confirmed state. Threads preserve the active path through a specific question.

A Past Conversation Review may compare one or more Sessions and prepare a pending Patch. The comparison does not change the Profile and does not turn repeated historical evidence into confirmation.
