#!/usr/bin/env python3
"""Minimal local memory store for the Review Your Thinking skill."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    print(
        "Review Your Thinking requires PyYAML. Install it with: "
        "python -m pip install PyYAML",
        file=sys.stderr,
    )
    raise SystemExit(2)


PROFILE_SECTIONS = (
    "collaboration_preferences",
    "definitions",
    "working_models",
    "recurring_inquiry_moves",
    "unresolved_tensions",
    "long_term_questions",
)
PROFILE_STATUSES = {"observed", "proposed", "confirmed", "retired"}
PATCH_STATUSES = {"pending", "confirmed", "rejected", "applied"}
OPERATIONS = {"add", "update", "retire", "delete"}
THREAD_STATUSES = {"active", "paused", "closed"}

PROFILE_SECTION_FIELDS = {
    "collaboration_preferences": {"statement"},
    "definitions": {"term", "current_definition"},
    "working_models": {"label", "claim", "scope"},
    "recurring_inquiry_moves": {"observation"},
    "unresolved_tensions": {"poles", "current_formulation"},
    "long_term_questions": {"question", "why_it_matters"},
}

SESSION_FIELDS = {
    "session_id",
    "created_at",
    "linked_thread",
    "user_initial_framing",
    "user_final_framing",
    "key_claims",
    "changed_definitions",
    "unresolved_tensions",
    "user_quote_anchors",
    "proposed_profile_patch",
    "next_entry_point",
}

THREAD_FIELDS = {
    "id",
    "title",
    "status",
    "current_question",
    "current_framing",
    "assumptions",
    "tensions",
    "unknowns",
    "next_probe",
    "linked_models",
    "session_refs",
}

PATCH_FIELDS = {
    "patch_id",
    "created_at",
    "base_profile_revision",
    "status",
    "changes",
}

CHANGE_FIELDS = {
    "operation",
    "target_section",
    "target_id",
    "proposed_value",
    "evidence",
    "reason",
}


class StoreError(Exception):
    """A user-facing structural or storage error."""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def load_yaml(path: Path, *, allow_null: bool = False) -> Any:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoreError(f"Missing file: {path}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise StoreError(f"Cannot read YAML from {path}: {exc}") from exc
    if value is None and not allow_null:
        raise StoreError(f"YAML document is empty: {path}")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temp_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temp_path, path)
    except OSError as exc:
        raise StoreError(f"Cannot write {path}: {exc}") from exc
    finally:
        if handle is not None:
            handle.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def parse_session_markdown(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StoreError(f"Session file not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise StoreError(f"Cannot read session file {path}: {exc}") from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise StoreError(f"Session file must start with YAML front matter: {path}")

    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as exc:
        raise StoreError(f"Session front matter has no closing delimiter: {path}") from exc

    front_matter = "\n".join(lines[1:closing_index])
    try:
        document = yaml.safe_load(front_matter)
    except yaml.YAMLError as exc:
        raise StoreError(f"Invalid session YAML front matter in {path}: {exc}") from exc

    if not isinstance(document, dict):
        raise StoreError(f"Session front matter must be a mapping: {path}")
    return document, text


def store_paths(data_dir: Path) -> dict[str, Path]:
    return {
        "root": data_dir,
        "profile": data_dir / "profile.yaml",
        "threads": data_dir / "threads.yaml",
        "pending": data_dir / "pending-profile-patch.yaml",
        "changes": data_dir / "changes.jsonl",
        "sessions": data_dir / "sessions",
        "review": data_dir / "past-review-draft.md",
    }


def missing_keys(document: dict[str, Any], required: set[str]) -> list[str]:
    return sorted(required - set(document))


def validate_profile_entry(
    entry: Any, section: str, index: int, errors: list[str]
) -> None:
    label = f"profile.{section}[{index}]"
    if not isinstance(entry, dict):
        errors.append(f"{label} must be a mapping")
        return

    missing = missing_keys(entry, {"id", "status", "evidence"})
    if missing:
        errors.append(f"{label} is missing: {', '.join(missing)}")

    if not isinstance(entry.get("id"), str) or not entry.get("id", "").strip():
        errors.append(f"{label}.id must be a non-empty string")
    if entry.get("status") not in PROFILE_STATUSES:
        errors.append(
            f"{label}.status must be one of: {', '.join(sorted(PROFILE_STATUSES))}"
        )
    evidence = entry.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        errors.append(f"{label}.evidence must be a non-empty list of session ids")

    for field in PROFILE_SECTION_FIELDS[section]:
        if field not in entry:
            errors.append(f"{label} is missing section field: {field}")


def validate_profile_document(profile: Any, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        errors.append("profile.yaml must contain a mapping")
        return

    if profile.get("schema_version") != 1:
        errors.append("profile.schema_version must be 1")
    revision = profile.get("profile_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        errors.append("profile.profile_revision must be a non-negative integer")
    if not profile.get("updated_at"):
        errors.append("profile.updated_at is required")

    seen_ids: set[str] = set()
    for section in PROFILE_SECTIONS:
        entries = profile.get(section)
        if not isinstance(entries, list):
            errors.append(f"profile.{section} must be a list")
            continue
        for index, entry in enumerate(entries):
            validate_profile_entry(entry, section, index, errors)
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                entry_id = entry["id"]
                if entry_id in seen_ids:
                    errors.append(f"Duplicate Profile entry id: {entry_id}")
                seen_ids.add(entry_id)


def validate_thread_document(thread: Any, label: str, errors: list[str]) -> None:
    if not isinstance(thread, dict):
        errors.append(f"{label} must be a mapping")
        return
    missing = missing_keys(thread, THREAD_FIELDS)
    if missing:
        errors.append(f"{label} is missing: {', '.join(missing)}")
    if thread.get("status") not in THREAD_STATUSES:
        errors.append(f"{label}.status must be active, paused, or closed")
    for field in ("assumptions", "tensions", "unknowns", "linked_models", "session_refs"):
        if field in thread and not isinstance(thread[field], list):
            errors.append(f"{label}.{field} must be a list")


def validate_threads_document(threads: Any, errors: list[str]) -> None:
    if not isinstance(threads, dict):
        errors.append("threads.yaml must contain a mapping")
        return
    if threads.get("schema_version") != 1:
        errors.append("threads.schema_version must be 1")
    items = threads.get("threads")
    if not isinstance(items, list):
        errors.append("threads.threads must be a list")
        return
    seen: set[str] = set()
    for index, thread in enumerate(items):
        validate_thread_document(thread, f"threads[{index}]", errors)
        if isinstance(thread, dict) and isinstance(thread.get("id"), str):
            if thread["id"] in seen:
                errors.append(f"Duplicate Thread id: {thread['id']}")
            seen.add(thread["id"])


def validate_patch_document(patch: Any, label: str, errors: list[str]) -> None:
    if not isinstance(patch, dict):
        errors.append(f"{label} must be a mapping")
        return
    missing = missing_keys(patch, PATCH_FIELDS)
    if missing:
        errors.append(f"{label} is missing: {', '.join(missing)}")
    if patch.get("status") not in PATCH_STATUSES:
        errors.append(
            f"{label}.status must be one of: {', '.join(sorted(PATCH_STATUSES))}"
        )
    revision = patch.get("base_profile_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        errors.append(f"{label}.base_profile_revision must be a non-negative integer")
    changes = patch.get("changes")
    if not isinstance(changes, list) or not changes:
        errors.append(f"{label}.changes must be a non-empty list")
        return

    targets: set[tuple[str, str]] = set()
    for index, change in enumerate(changes):
        change_label = f"{label}.changes[{index}]"
        if not isinstance(change, dict):
            errors.append(f"{change_label} must be a mapping")
            continue
        missing_change = missing_keys(change, CHANGE_FIELDS)
        if missing_change:
            errors.append(f"{change_label} is missing: {', '.join(missing_change)}")
        if change.get("operation") not in OPERATIONS:
            errors.append(f"{change_label}.operation is invalid")
        if change.get("target_section") not in PROFILE_SECTIONS:
            errors.append(f"{change_label}.target_section is invalid")
        if not isinstance(change.get("target_id"), str) or not change.get(
            "target_id", ""
        ).strip():
            errors.append(f"{change_label}.target_id must be a non-empty string")
        evidence = change.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            errors.append(f"{change_label}.evidence must be a non-empty list")
        if not isinstance(change.get("reason"), str) or not change.get(
            "reason", ""
        ).strip():
            errors.append(f"{change_label}.reason must be a non-empty string")

        target = (str(change.get("target_section")), str(change.get("target_id")))
        if target in targets:
            errors.append(f"{label} changes the same target more than once: {target}")
        targets.add(target)


def validate_session_document(session: Any, label: str, errors: list[str]) -> None:
    if not isinstance(session, dict):
        errors.append(f"{label} must be a mapping")
        return
    missing = missing_keys(session, SESSION_FIELDS)
    if missing:
        errors.append(f"{label} is missing: {', '.join(missing)}")

    quotes = session.get("user_quote_anchors")
    if not isinstance(quotes, list) or not 1 <= len(quotes) <= 3:
        errors.append(f"{label}.user_quote_anchors must contain 1 to 3 items")
    elif not all(isinstance(quote, str) and quote.strip() for quote in quotes):
        errors.append(f"{label}.user_quote_anchors must contain non-empty strings")

    for field in ("key_claims", "changed_definitions", "unresolved_tensions"):
        if field in session and not isinstance(session[field], list):
            errors.append(f"{label}.{field} must be a list")

    if "proposed_profile_patch" in session:
        validate_patch_document(
            session["proposed_profile_patch"],
            f"{label}.proposed_profile_patch",
            errors,
        )


def collect_sessions(sessions_dir: Path, errors: list[str]) -> dict[str, Path]:
    sessions: dict[str, Path] = {}
    if not sessions_dir.is_dir():
        return sessions
    for path in sorted(sessions_dir.glob("*.md")):
        try:
            session, _ = parse_session_markdown(path)
        except StoreError as exc:
            errors.append(str(exc))
            continue
        validate_session_document(session, f"session:{path.name}", errors)
        session_id = session.get("session_id")
        if isinstance(session_id, str):
            if session_id in sessions:
                errors.append(f"Duplicate Session id: {session_id}")
            sessions[session_id] = path
    return sessions


def evidence_references(
    profile: Any, threads: Any, pending: Any
) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    if isinstance(profile, dict):
        for section in PROFILE_SECTIONS:
            for entry in profile.get(section, []) if isinstance(profile.get(section), list) else []:
                if isinstance(entry, dict):
                    for session_id in entry.get("evidence", []):
                        if isinstance(session_id, str):
                            references.append((f"profile entry {entry.get('id')}", session_id))
    if isinstance(threads, dict) and isinstance(threads.get("threads"), list):
        for thread in threads["threads"]:
            if isinstance(thread, dict):
                for session_id in thread.get("session_refs", []):
                    if isinstance(session_id, str):
                        references.append((f"thread {thread.get('id')}", session_id))
    if isinstance(pending, dict) and isinstance(pending.get("changes"), list):
        for change in pending["changes"]:
            if isinstance(change, dict):
                for session_id in change.get("evidence", []):
                    if isinstance(session_id, str):
                        references.append((f"patch change {change.get('target_id')}", session_id))
    return references


def validate_change_log(path: Path, errors: list[str]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"Cannot read {path}: {exc}")
        return
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"changes.jsonl line {index} is invalid JSON: {exc}")
            continue
        for field in (
            "timestamp",
            "patch_id",
            "from_revision",
            "to_revision",
            "operation",
            "target_section",
            "target_id",
            "evidence",
            "reason",
        ):
            if field not in record:
                errors.append(f"changes.jsonl line {index} is missing {field}")


def command_init(data_dir: Path) -> None:
    paths = store_paths(data_dir)
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["sessions"].mkdir(parents=True, exist_ok=True)

    initial_documents = {
        paths["profile"]: {
            "schema_version": 1,
            "profile_revision": 0,
            "updated_at": now_iso(),
            **{section: [] for section in PROFILE_SECTIONS},
        },
        paths["threads"]: {"schema_version": 1, "threads": []},
        paths["pending"]: None,
    }

    created: list[str] = []
    preserved: list[str] = []
    for path, document in initial_documents.items():
        if path.exists():
            preserved.append(path.name)
        else:
            atomic_write_text(path, yaml_text(document))
            created.append(path.name)

    if paths["changes"].exists():
        preserved.append(paths["changes"].name)
    else:
        atomic_write_text(paths["changes"], "")
        created.append(paths["changes"].name)

    print(f"Initialized memory store: {paths['root'].resolve()}")
    if created:
        print(f"Created: {', '.join(created)}")
    if preserved:
        print(f"Preserved existing: {', '.join(preserved)}")


def load_store_for_validation(paths: dict[str, Path], errors: list[str]) -> tuple[Any, Any, Any]:
    required_files = ("profile", "threads", "pending", "changes")
    if not paths["root"].is_dir():
        errors.append(f"User data directory does not exist: {paths['root']}")
    for key in required_files:
        if not paths[key].is_file():
            errors.append(f"Missing required file: {paths[key]}")
    if not paths["sessions"].is_dir():
        errors.append(f"Missing required directory: {paths['sessions']}")

    profile = None
    threads = None
    pending = None
    if paths["profile"].is_file():
        try:
            profile = load_yaml(paths["profile"])
        except StoreError as exc:
            errors.append(str(exc))
    if paths["threads"].is_file():
        try:
            threads = load_yaml(paths["threads"])
        except StoreError as exc:
            errors.append(str(exc))
    if paths["pending"].is_file():
        try:
            pending = load_yaml(paths["pending"], allow_null=True)
        except StoreError as exc:
            errors.append(str(exc))
    return profile, threads, pending


def command_validate(data_dir: Path) -> None:
    paths = store_paths(data_dir)
    errors: list[str] = []
    profile, threads, pending = load_store_for_validation(paths, errors)

    if profile is not None:
        validate_profile_document(profile, errors)
    if threads is not None:
        validate_threads_document(threads, errors)
    if pending is not None:
        validate_patch_document(pending, "pending-profile-patch", errors)

    session_ids = collect_sessions(paths["sessions"], errors)

    if isinstance(profile, dict) and isinstance(pending, dict):
        current_revision = profile.get("profile_revision")
        base_revision = pending.get("base_profile_revision")
        patch_status = pending.get("status")
        if isinstance(current_revision, int) and isinstance(base_revision, int):
            if patch_status in {"pending", "confirmed"} and base_revision != current_revision:
                errors.append(
                    "Pending Patch base_profile_revision does not match current profile_revision"
                )
            if patch_status == "applied" and base_revision + 1 != current_revision:
                errors.append(
                    "Applied Patch revision does not correspond to current profile_revision"
                )
            if patch_status == "rejected" and base_revision > current_revision:
                errors.append("Rejected Patch refers to a future Profile revision")

    for owner, session_id in evidence_references(profile, threads, pending):
        if session_id not in session_ids:
            errors.append(f"Untraceable evidence '{session_id}' referenced by {owner}")

    if paths["changes"].is_file():
        validate_change_log(paths["changes"], errors)

    if errors:
        print("Validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)

    revision = profile.get("profile_revision") if isinstance(profile, dict) else "unknown"
    pending_status = pending.get("status") if isinstance(pending, dict) else "none"
    print(
        "Validation passed: "
        f"profile_revision={revision}, sessions={len(session_ids)}, "
        f"pending_patch={pending_status}"
    )


def safe_session_filename(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", session_id).strip(".-")
    if not safe:
        raise StoreError("session_id cannot be converted to a safe filename")
    return f"{safe}.md"


def markdown_value(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def append_markdown_list(lines: list[str], values: Any, empty_text: str = "None recorded.") -> None:
    if not isinstance(values, list) or not values:
        lines.append(empty_text)
        lines.append("")
        return
    for value in values:
        lines.append(f"- {markdown_value(value)}")
    lines.append("")


def render_review_draft(
    session_documents: list[tuple[Path, dict[str, Any]]]
) -> str:
    generated_at = now_iso()
    session_ids = [document["session_id"] for _, document in session_documents]
    linked_threads = list(
        dict.fromkeys(
            markdown_value(document.get("linked_thread"))
            for _, document in session_documents
            if document.get("linked_thread")
        )
    )

    lines = [
        "# Past Conversation Review Draft",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "This draft contains structured source material only. The CLI has not performed semantic interpretation, inferred a stable trait, or changed the Thinking Profile.",
        "",
        "## Review scope",
        "",
        "Explicitly provided Session Records:",
        "",
    ]
    for session_id in session_ids:
        lines.append(f"- `{session_id}`")
    lines.extend(["", "Linked threads:", ""])
    if linked_threads:
        for thread in linked_threads:
            lines.append(f"- `{thread}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Do not treat this set as the user's complete conversation history.",
            "",
            "## Structured Session evidence",
            "",
        ]
    )

    for source_path, document in session_documents:
        lines.extend(
            [
                f"### {document['session_id']}",
                "",
                f"- Source file: `{source_path}`",
                f"- Created at: `{markdown_value(document.get('created_at'))}`",
                f"- Linked thread: `{markdown_value(document.get('linked_thread'))}`",
                "",
                "#### Initial framing",
                "",
                markdown_value(document.get("user_initial_framing")),
                "",
                "#### Final framing",
                "",
                markdown_value(document.get("user_final_framing")),
                "",
                "#### Key claims",
                "",
            ]
        )
        append_markdown_list(lines, document.get("key_claims"))

        lines.extend(["#### Changed definitions", ""])
        definitions = document.get("changed_definitions")
        if isinstance(definitions, list) and definitions:
            for definition in definitions:
                if isinstance(definition, dict):
                    lines.append(
                        "- "
                        f"{markdown_value(definition.get('term'))}: "
                        f"{markdown_value(definition.get('before'))} -> "
                        f"{markdown_value(definition.get('after'))}"
                    )
                else:
                    lines.append(f"- {markdown_value(definition)}")
            lines.append("")
        else:
            lines.extend(["None recorded.", ""])

        lines.extend(["#### Unresolved tensions", ""])
        append_markdown_list(lines, document.get("unresolved_tensions"))
        lines.extend(["#### User quote anchors", ""])
        quotes = document.get("user_quote_anchors")
        if isinstance(quotes, list):
            for quote in quotes:
                lines.append(f"> {markdown_value(quote)}")
                lines.append("")

        patch = document.get("proposed_profile_patch")
        lines.extend(["#### Session Patch candidate", ""])
        if isinstance(patch, dict):
            lines.append(f"- Patch id: `{markdown_value(patch.get('patch_id'))}`")
            lines.append(f"- Status: `{markdown_value(patch.get('status'))}`")
            for change in patch.get("changes", []):
                if isinstance(change, dict):
                    lines.append(
                        "- Target: "
                        f"`{markdown_value(change.get('target_section'))}/"
                        f"{markdown_value(change.get('target_id'))}`"
                    )
            lines.append("")
        else:
            lines.extend(["None recorded.", ""])

    lines.extend(
        [
            "## AI review workspace",
            "",
            "Use the evidence above to prepare a user-facing review. The AI must fill this section semantically; the CLI does not infer these answers.",
            "",
            "### Observed changes",
            "",
            "- Cite a Session id for every statement.",
            "- Compare initial and final framing without inventing missing context.",
            "",
            "### Recurring questions or tensions",
            "",
            "- Distinguish repeated evidence from user confirmation.",
            "- Preserve contradictions and uncertainty.",
            "",
            "### Proposed Profile changes",
            "",
            "- Any candidate must remain a `pending` Patch with proposed values.",
            "- Do not write to the confirmed Thinking Profile without explicit user confirmation.",
            "",
            "### Confirmation status",
            "",
            "No Profile change has been confirmed or applied by this review command.",
            "",
        ]
    )
    return "\n".join(lines)


def command_review(data_dir: Path, session_paths: list[Path]) -> None:
    paths = store_paths(data_dir)
    if not paths["root"].is_dir():
        raise StoreError("Memory store is not initialized. Run the init command first.")

    documents: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    seen_session_ids: set[str] = set()
    for session_path in session_paths:
        try:
            session, _ = parse_session_markdown(session_path)
        except StoreError as exc:
            errors.append(str(exc))
            continue
        validate_session_document(session, f"session:{session_path.name}", errors)
        session_id = session.get("session_id")
        if isinstance(session_id, str):
            if session_id in seen_session_ids:
                errors.append(f"Duplicate Session id in review input: {session_id}")
            seen_session_ids.add(session_id)
        documents.append((session_path, session))

    if errors:
        raise StoreError("Cannot prepare past review:\n- " + "\n- ".join(errors))

    atomic_write_text(paths["review"], render_review_draft(documents))
    print(f"Prepared Past Conversation Review from {len(documents)} Session Record(s)")
    print(f"Review draft: {paths['review']}")
    print("No Profile changes were confirmed or applied.")


def command_close(data_dir: Path, session_path: Path) -> None:
    paths = store_paths(data_dir)
    if not paths["root"].is_dir():
        raise StoreError("Memory store is not initialized. Run the init command first.")

    profile = load_yaml(paths["profile"])
    session, source_text = parse_session_markdown(session_path)
    errors: list[str] = []
    validate_session_document(session, f"session:{session_path.name}", errors)
    patch = session.get("proposed_profile_patch")

    if isinstance(patch, dict) and patch.get("status") != "pending":
        errors.append("Session proposed_profile_patch.status must be pending")
    if isinstance(profile, dict) and isinstance(patch, dict):
        if patch.get("base_profile_revision") != profile.get("profile_revision"):
            errors.append(
                "Session Patch base_profile_revision does not match current profile_revision"
            )
    if errors:
        raise StoreError("Cannot close session:\n- " + "\n- ".join(errors))

    pending = load_yaml(paths["pending"], allow_null=True)
    if isinstance(pending, dict) and pending.get("status") in {"pending", "confirmed"}:
        if pending.get("patch_id") != patch.get("patch_id"):
            raise StoreError(
                "A different unresolved Patch already exists. Confirm or reject it before closing another session."
            )

    session_id = session["session_id"]
    destination = paths["sessions"] / safe_session_filename(session_id)
    if destination.exists():
        existing = destination.read_text(encoding="utf-8")
        if existing != source_text:
            raise StoreError(
                f"Session id already exists with different content: {session_id}"
            )
    else:
        atomic_write_text(destination, source_text)

    atomic_write_text(paths["pending"], yaml_text(patch))
    print(f"Closed session: {session_id}")
    print(f"Stored Session Record: {destination}")
    print(f"Stored pending Patch: {patch['patch_id']}")


def ensure_confirmed_profile_value(
    value: Any, section: str, target_id: str, operation: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StoreError(f"{operation} requires proposed_value to be a mapping")
    if value.get("id") != target_id:
        raise StoreError(
            f"proposed_value.id must match target_id for {section}/{target_id}"
        )
    if value.get("status") != "confirmed":
        raise StoreError(
            f"{operation} proposed_value must have status 'confirmed': {target_id}"
        )
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise StoreError(f"proposed_value must include evidence: {target_id}")
    missing = PROFILE_SECTION_FIELDS[section] - set(value)
    if missing:
        raise StoreError(
            f"proposed_value for {section}/{target_id} is missing: {', '.join(sorted(missing))}"
        )
    return copy.deepcopy(value)


def find_entry(entries: list[Any], target_id: str) -> int | None:
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("id") == target_id:
            return index
    return None


def jsonable(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def apply_change(
    profile: dict[str, Any],
    change: dict[str, Any],
    patch: dict[str, Any],
    from_revision: int,
    to_revision: int,
) -> dict[str, Any]:
    operation = change["operation"]
    section = change["target_section"]
    target_id = change["target_id"]
    entries = profile[section]
    index = find_entry(entries, target_id)
    before: Any = None
    after: Any = None

    if operation == "add":
        if index is not None:
            raise StoreError(f"Cannot add existing Profile entry: {section}/{target_id}")
        after = ensure_confirmed_profile_value(
            change["proposed_value"], section, target_id, operation
        )
        entries.append(after)
    elif operation == "update":
        if index is None:
            raise StoreError(f"Cannot update missing Profile entry: {section}/{target_id}")
        before = copy.deepcopy(entries[index])
        after = ensure_confirmed_profile_value(
            change["proposed_value"], section, target_id, operation
        )
        entries[index] = after
    elif operation == "retire":
        if index is None:
            raise StoreError(f"Cannot retire missing Profile entry: {section}/{target_id}")
        before = copy.deepcopy(entries[index])
        after = copy.deepcopy(entries[index])
        proposed = change.get("proposed_value")
        if isinstance(proposed, dict):
            for key, value in proposed.items():
                if key not in {"id", "status"}:
                    after[key] = copy.deepcopy(value)
        after["id"] = target_id
        after["status"] = "retired"
        after["evidence"] = list(
            dict.fromkeys([*after.get("evidence", []), *change["evidence"]])
        )
        entries[index] = after
    elif operation == "delete":
        if index is None:
            raise StoreError(f"Cannot delete missing Profile entry: {section}/{target_id}")
        removed = entries.pop(index)
        before = {
            "id": target_id,
            "status": removed.get("status") if isinstance(removed, dict) else None,
            "content_removed": True,
        }
        after = None
    else:
        raise StoreError(f"Unsupported operation: {operation}")

    return {
        "timestamp": now_iso(),
        "patch_id": patch["patch_id"],
        "from_revision": from_revision,
        "to_revision": to_revision,
        "operation": operation,
        "target_section": section,
        "target_id": target_id,
        "before": before,
        "after": after,
        "evidence": change["evidence"],
        "reason": change["reason"],
    }


def command_apply(data_dir: Path, patch_path: Path) -> None:
    paths = store_paths(data_dir)
    if not paths["root"].is_dir():
        raise StoreError("Memory store is not initialized. Run the init command first.")

    profile = load_yaml(paths["profile"])
    patch = load_yaml(patch_path)
    errors: list[str] = []
    validate_profile_document(profile, errors)
    validate_patch_document(patch, f"patch:{patch_path.name}", errors)
    if errors:
        raise StoreError("Cannot apply Patch:\n- " + "\n- ".join(errors))

    if patch["status"] != "confirmed":
        raise StoreError("Only a Patch with status 'confirmed' can be applied.")

    current_revision = profile["profile_revision"]
    if patch["base_profile_revision"] != current_revision:
        raise StoreError(
            "Profile revision conflict: "
            f"Patch expects {patch['base_profile_revision']}, current Profile is {current_revision}."
        )

    session_errors: list[str] = []
    session_ids = collect_sessions(paths["sessions"], session_errors)
    if session_errors:
        raise StoreError("Cannot verify Session evidence:\n- " + "\n- ".join(session_errors))
    for change in patch["changes"]:
        for session_id in change["evidence"]:
            if session_id not in session_ids:
                raise StoreError(
                    f"Cannot apply untraceable evidence '{session_id}' for {change['target_id']}"
                )

    updated_profile = copy.deepcopy(profile)
    next_revision = current_revision + 1
    log_records: list[dict[str, Any]] = []
    for change in patch["changes"]:
        log_records.append(
            apply_change(
                updated_profile,
                change,
                patch,
                current_revision,
                next_revision,
            )
        )

    updated_profile["profile_revision"] = next_revision
    updated_profile["updated_at"] = now_iso()

    final_errors: list[str] = []
    validate_profile_document(updated_profile, final_errors)
    if final_errors:
        raise StoreError(
            "Applied result would create an invalid Profile:\n- " + "\n- ".join(final_errors)
        )

    pending = load_yaml(paths["pending"], allow_null=True)
    updated_pending = pending
    if isinstance(pending, dict) and pending.get("patch_id") == patch["patch_id"]:
        updated_pending = copy.deepcopy(pending)
        updated_pending["status"] = "applied"
        updated_pending["applied_at"] = now_iso()

    old_profile_text = paths["profile"].read_text(encoding="utf-8")
    old_changes_text = paths["changes"].read_text(encoding="utf-8")
    old_pending_text = paths["pending"].read_text(encoding="utf-8")
    new_log_lines = "".join(
        json.dumps(jsonable(record), ensure_ascii=False, sort_keys=True) + "\n"
        for record in log_records
    )

    try:
        atomic_write_text(paths["profile"], yaml_text(updated_profile))
        atomic_write_text(paths["changes"], old_changes_text + new_log_lines)
        if updated_pending is not pending:
            atomic_write_text(paths["pending"], yaml_text(updated_pending))
    except StoreError:
        atomic_write_text(paths["profile"], old_profile_text)
        atomic_write_text(paths["changes"], old_changes_text)
        atomic_write_text(paths["pending"], old_pending_text)
        raise

    print(f"Applied Patch: {patch['patch_id']}")
    print(f"Profile revision: {current_revision} -> {next_revision}")
    print(f"Changes recorded: {len(log_records)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage a local Review Your Thinking memory store."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(".review-your-thinking"),
        help="User data directory (default: .review-your-thinking in the current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Initialize a local memory store")
    subparsers.add_parser("validate", help="Validate the local memory store")

    close_parser = subparsers.add_parser(
        "close", help="Store a Session Record and its pending Patch"
    )
    close_parser.add_argument("session_file", type=Path)

    apply_parser = subparsers.add_parser(
        "apply", help="Apply an explicitly confirmed Patch to the Profile"
    )
    apply_parser.add_argument("patch_file", type=Path)

    review_parser = subparsers.add_parser(
        "review", help="Prepare a structured draft from past Session Records"
    )
    review_parser.add_argument("session_files", type=Path, nargs="+")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    data_dir = args.data_dir
    try:
        if args.command == "init":
            command_init(data_dir)
        elif args.command == "validate":
            command_validate(data_dir)
        elif args.command == "close":
            command_close(data_dir, args.session_file)
        elif args.command == "apply":
            command_apply(data_dir, args.patch_file)
        elif args.command == "review":
            command_review(data_dir, args.session_files)
        else:
            parser.error(f"Unknown command: {args.command}")
    except StoreError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
