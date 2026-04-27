---
inclusion: auto
---

# Bilingual Documentation Rules

This project maintains all documentation in both Japanese and English. Follow these rules whenever creating or editing Markdown files.

## File Naming Convention

Every project `.md` file has two versions:

| Version  | Suffix   | Example                |
|----------|----------|------------------------|
| Japanese | `.md`    | `README.md`            |
| English  | `_en.md` | `README_en.md`         |

The Japanese file (`.md`) is the default. The English file (`_en.md`) is the counterpart.

Examples:
- `README.md` (Japanese) ↔ `README_en.md` (English)
- `testing.md` (Japanese) ↔ `testing_en.md` (English)
- `report.md` (Japanese) ↔ `report_en.md` (English)

## Sync Rules

- When a `.md` file is created, the corresponding `_en.md` file must also be created.
- When a `.md` file is updated, the corresponding `_en.md` file must also be updated.
- The Japanese and English versions must always be in sync content-wise. They contain the same information, just in different languages.

## Exceptions

`.kiro/` spec files are **English only** — no Japanese/English pair is needed for:
- `.kiro/specs/**/requirements.md`
- `.kiro/specs/**/design.md`
- `.kiro/specs/**/tasks.md`
- `.kiro/steering/*.md`
- `.kiro/hooks/*.json`

These files are internal tooling configuration and do not require bilingual counterparts.

## When Generating Documentation

1. Always produce both the Japanese `.md` and the English `_en.md` together.
2. Write the Japanese version first, then create the English version with the same structure and content.
3. Do not leave one version out of date — if you edit one, edit both.
