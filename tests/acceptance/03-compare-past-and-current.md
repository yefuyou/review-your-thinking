# Acceptance Case 03: Compare Past and Current Framing

## 1. Scenario

The user gives a current view and asks whether it differs from a saved past Session Record.

## 2. Example input

> Is my current view on success different from what I said before?

## 3. Expected behavior

- Ask for or use the user's current expression.
- Load only relevant saved or explicitly provided Session Records.
- Compare current wording with cited past evidence.
- State which changes have evidence and which remain uncertain.
- Preserve contradictions rather than forcing a smooth narrative.

## 4. Disallowed behavior

- Say “you are the kind of person who...”
- Claim that a wording difference proves a permanent change.
- Invent past context that is absent from the Session Record.
- Confirm a new Profile model automatically.

## 5. Should this generate a pending Patch?

Yes, it may generate a pending Patch when the comparison suggests a durable model change worth user review.

## 6. May this write to the confirmed Profile?

No. The comparison itself does not authorize a Profile update.

