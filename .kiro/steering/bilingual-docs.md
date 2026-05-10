---
inclusion: auto
---

# Bilingual Documentation Rules

This project maintains documentation in both Japanese (default) and English (personal reference). Follow these rules whenever creating or editing Markdown files.

## File Naming Convention

| Version  | Suffix   | Example                | Committed to Git? |
|----------|----------|------------------------|-------------------|
| Japanese | `.md`    | `README.md`            | ✅ Yes            |
| English  | `_en.md` | `README_en.md`         | ❌ No (.gitignore)|

The Japanese file (`.md`) is the **default** and what the team/senior sees. The English file (`_en.md`) is for personal reference only and is gitignored.

Examples:
- `README.md` (Japanese, committed) ↔ `README_en.md` (English, gitignored)
- `infra/README.md` (Japanese, committed) ↔ `infra/README_en.md` (English, gitignored)
- `infra/architecture.md` (Japanese, committed) ↔ `infra/architecture_en.md` (English, gitignored)
- `pending.md` (Japanese, committed) ↔ `pending_en.md` (English, gitignored)

## Sync Rules

- When creating a documentation file, always create the Japanese `.md` version first.
- Create the English `_en.md` counterpart for personal reference.
- Both versions must contain the same information.
- If you edit one, edit both.

## Exceptions

`.kiro/` spec files are **English only** — no Japanese counterpart needed for:
- `.kiro/specs/**/*.md`
- `.kiro/steering/*.md`
- `.kiro/hooks/*.json`

## When Generating Documentation

1. Always produce both Japanese and English versions together.
2. Write the Japanese version as the primary (`.md`).
3. Create the English version as `_en.md` for personal reference.
4. Do not leave one version out of date — if you edit one, edit both.
