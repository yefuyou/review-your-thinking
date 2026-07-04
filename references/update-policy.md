# Update Policy

Use this policy before creating or applying a Thinking Profile Patch.

## Epistemic states

- `observed`: directly traceable to the user's words or an explicit change between two user framings.
- `proposed`: organized or inferred by the AI and awaiting review.
- `confirmed`: explicitly accepted by the user as representing their current thinking.
- `retired`: previously confirmed, but no longer current.

Do not mix these states. Never describe a proposal as an observation, and never promote a proposal to confirmed without the user's explicit confirmation.

## When to propose a Patch

Propose a Patch when a session produces a potentially reusable item, such as:

- a definition the user wants to retain;
- a working model the user says represents their current view;
- a recurring inquiry move worth making visible;
- a durable unresolved tension;
- a long-term question;
- a collaboration preference for future conversations.

Keep the candidate in a `pending` Patch. Explain the reason and cite one or more Session ids as evidence.

Do not propose a stable Profile item from a passing mood, a single unexamined phrase, an AI guess about motive, a psychological interpretation, or third-party sensitive information.

## When to write to the Profile

Write only when all of the following are true:

1. the user explicitly confirmed the Patch;
2. the Patch status is `confirmed`;
3. `base_profile_revision` equals the current `profile_revision`;
4. every change has evidence that can be traced to a stored Session Record;
5. an `add` or `update` value has status `confirmed`;
6. the target id and operation are structurally valid.

After a successful application, increment `profile_revision`, append the Change Log, and mark the matching pending Patch as `applied`.

## Repetition is not confirmation

Repeated expressions can make a candidate worth raising again. They cannot establish that the user endorses an AI formulation. Contexts change, repeated wording can have different meanings, and the user remains the authority on what belongs in the Profile.

Use repetition to improve the evidence list of a proposal, never to bypass confirmation.

Multiple past Session Records can increase the evidential basis for proposing a Patch. Cite every supporting session and note conflicting records. More evidence may justify a clearer proposal, but it does not increase the Patch beyond `pending` status.

A Patch produced by Past Conversation Review must remain `pending` until the user explicitly confirms its wording. Repeated evidence never equals user confirmation.

## Conflicts and revisions

Do not silently overwrite an older view.

- Use `update` when the same object remains useful but its current formulation changes.
- Use `retire` when an older object should remain historically visible but no longer represents the current view.
- Use `supersedes` in a new definition or model when it replaces a distinct older object.
- Record before and after values in the Change Log for updates and retirements.
- Stop on a Profile revision conflict and rebuild the Patch from the latest state.

## Deletion

Use `delete` when the user asks to forget an entry or when retention is no longer appropriate.

Remove the object from the Profile. In the Change Log, record the Patch id, operation, target id, evidence, reason, and revision transition, but replace the removed content with a content-free tombstone. Do not retain deleted sensitive text in history.

Delete or redact linked Session content as well when the user's request includes the underlying evidence, then repair references before validation.
