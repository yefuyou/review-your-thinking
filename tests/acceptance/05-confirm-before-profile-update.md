# Acceptance Case 05: Confirm Before Profile Update

## 1. Scenario

The AI proposes a working model after reviewing conversation evidence, but the user does not confirm it.

## 2. Example input

> AI proposal: “Your current working model may be: freedom means having room to choose constraints.”

The user changes the subject without confirming or rejecting the wording.

## 3. Expected behavior

- Keep the candidate in a pending Patch with status `pending`.
- Keep its proposed Profile value at status `proposed`.
- Cite the supporting Session Records.
- Allow a later conversation to remind the user that a change awaits review.

## 4. Disallowed behavior

- Apply the Patch.
- Change the proposed value to `confirmed`.
- Treat silence, topic change, repetition, or apparent agreement as confirmation.
- Update `profile_revision` or append an applied Change Log record.

## 5. Should this generate a pending Patch?

Yes. The proposal belongs in a pending Patch until the user acts on it.

## 6. May this write to the confirmed Profile?

No. Only explicit user confirmation authorizes application.

