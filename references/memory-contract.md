# Memory Contract

Memory exists to preserve continuity without turning conversation history into a hidden assessment of the user.

## Program and data separation

Keep Skill files in the project or installed Skill directory. Keep user data in `.thinking-partner/` under the active workspace by default.

Never store user Profile data inside `SKILL.md`, `references/`, `schemas/`, `scripts/`, or `examples/`. Skill upgrades must not overwrite user memory.

The default data layout is:

```text
.thinking-partner/
├── profile.yaml
├── threads.yaml
├── pending-profile-patch.yaml
├── changes.jsonl
└── sessions/
```

## Four memory layers

### Working State

Temporary state for the current conversation. It may contain a problem map, candidate distinctions, and the next probe. It is not persistent and is not part of the Thinking Profile.

### Session Record

An immutable, structured record created when a conversation closes. It preserves the user's initial and final framing, key claims, changed definitions, unresolved tensions, one to three user quote anchors, a proposed Patch, and a next entry point.

A Session Record is evidence. It is not a full chat transcript.

### Thinking Profile

The current collection of long-term models the user explicitly confirmed. It contains revisable definitions, working models, recurring inquiry moves, unresolved tensions, long-term questions, and collaboration preferences.

The Profile is a current projection, not a personality report.

### Change Log

An append-only JSON Lines audit trail. Each applied change records its Patch, revision transition, operation, target, evidence, reason, and before/after state where appropriate.

For deletion, keep only a non-content tombstone. Do not preserve deleted sensitive content in the log.

## Data minimization

- Do not save full transcripts.
- Save no more than three short user quote anchors in a Session Record.
- Copy quote anchors only from the user's own words.
- Do not store a paraphrase as a quote.
- Do not store sensitive third-party details in the Profile.
- Keep one-off expressions in Session evidence; do not convert them into stable Profile entries.

## User control

Support these user actions:

- **View**: show the current Profile, active Threads, and pending Patch.
- **Revise**: create a Patch that corrects or replaces an inaccurate entry.
- **Reject**: mark a proposed Patch as rejected without applying it.
- **Delete**: remove requested content and log a content-free tombstone.
- **Skip**: close a conversation without persistent storage.

Do not argue with a user's correction to their own Profile.

## Retrieval limits

Load the relevant Thread, its linked Profile entries, and at most three recent linked Session Records by default. Expand the search only when the user asks for a broader historical comparison.

When the record is missing or ambiguous, say so. Do not fill gaps with invented continuity.

## Past Conversation Review

Treat past Session Records as evidence records, not raw memory dumps and not final truth. Review only records that the user explicitly provides, imports, or has saved under `.thinking-partner/sessions/`. Never claim access to conversations outside that set.

For one-session review:

- identify the session id;
- show its initial and final framing;
- describe only changes supported inside that record;
- avoid turning a one-session expression into a stable trait.

For multi-session review:

- load the smallest relevant set, normally no more than three records unless the user asks for a wider review;
- cite session ids beside comparisons;
- distinguish repeated wording from confirmed continuity;
- name contradictions and uncertainty instead of smoothing them away;
- use the records only to support `observed` findings or a `proposed` Patch.

Past review must never create `confirmed` Profile content. It may prepare a `pending` Patch for user review. The user decides whether that Patch represents their current thinking.
