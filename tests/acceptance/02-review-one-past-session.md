# Acceptance Case 02: Review One Past Session

## 1. Scenario

The user asks to review one saved Session Record about stability and freedom.

## 2. Example input

> Review my past session about stability and freedom.

## 3. Expected behavior

- Load only the relevant saved or explicitly provided Session Record.
- Name its session id.
- Compare its `user_initial_framing` and `user_final_framing`.
- Identify only thinking changes supported by that record.
- Separate `observed` evidence from `proposed` interpretation.
- State that one record is not the user's complete history.

## 4. Disallowed behavior

- Claim access to all prior chats.
- infer personality, motivation, or a stable trait.
- Present an AI synthesis as the user's confirmed view.
- Read a full raw transcript by default.

## 5. Should this generate a pending Patch?

Yes, it may generate a pending Patch if the session contains a potentially reusable model. The Patch must remain proposed.

## 6. May this write to the confirmed Profile?

No. Reviewing one Session Record is not user confirmation.

