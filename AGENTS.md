# Codex Project Guidance

This file applies to the entire repository. Use it when developing, maintaining, reviewing, or testing Thinking Partner with Codex.

## Document roles

Keep these three documents distinct:

- `README.md` introduces the project to human readers and is the main GitHub presentation surface.
- `SKILL.md` defines the core protocol used when the AI Skill runs.
- `AGENTS.md` guides Codex while it develops, maintains, and tests this repository.

`AGENTS.md` does not replace `SKILL.md`. Repository changes must preserve the runtime contract in `SKILL.md` and the human-facing explanation in both README languages.

## Project goal

Thinking Partner is a self-retrospective skill for long-term AI conversations.

It helps users review how their questions, assumptions, definitions, and thinking models change over time. It does not try to give users better answers directly.

It is not therapy, personality analysis, MBTI, diagnosis, life coaching, or a raw chat log collector.

The core contract is:

> Thinking Profile is not what AI thinks about the user. It is a set of thinking models the user has confirmed and may revise later.

## Codex development rules

1. Do not expand scope unless explicitly asked.
2. Keep `v0.1-base` small and file-based.
3. Do not introduce databases, vector search, cloud sync, web UI, background jobs, or multi-agent systems.
4. Do not turn this into a therapy app, personality analysis tool, or generic journaling assistant.
5. Do not auto-upgrade `proposed` content into `confirmed`.
6. Do not store raw full chat logs by default.
7. Do not infer stable user traits from one session.
8. Preserve the distinction between `observed`, `proposed`, `confirmed`, and `retired`.
9. Keep examples fictional and privacy-safe.
10. When changing memory behavior, update schemas, examples, references, and acceptance tests together.

Treat past Session Records as evidence, not complete history or final truth. Require explicit user confirmation before applying a Patch to the Thinking Profile.

## Local validation

Run the minimal flow from the repository root after changing memory behavior:

```bash
python scripts/memory_store.py init
python scripts/memory_store.py close examples/sample-session.md
python scripts/memory_store.py review examples/sample-past-session-01.md examples/sample-past-session-02.md
python scripts/memory_store.py validate
```

Check the acceptance cases in [`tests/acceptance/`](./tests/acceptance/) whenever the core protocol, memory rules, confirmation rules, or conversation behavior changes.

Do not claim validation passed unless the relevant commands and acceptance checks were actually run.

## README and SVG maintenance

- Keep README as the main GitHub presentation surface.
- Do not replace README with a separate website.
- Do not introduce GitHub Pages unless explicitly requested.
- Keep SVG illustrations README-native, self-contained, and maintainable.
- Keep Chinese and English README content aligned.
- When changing one language version, check whether the other language version also needs an equivalent update.
- Do not add JavaScript, CSS frameworks, or a frontend build system for README presentation.

## Change discipline

Make the smallest change that satisfies the request. Preserve user data separation under `.thinking-partner/`, keep runtime data out of Git, and avoid unrelated cleanup.
