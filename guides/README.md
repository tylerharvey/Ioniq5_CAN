# Documentation translations

`translate_docs.py` translates the rendered text of the manuals and install
guides in this repo (.md and .tex) while preserving all markup, so the
translated files still compile and render correctly. Originals are never
modified: output is written next to the source as `basename.<lang><ext>`.

## Requirements

- Python 3 (stdlib only for the free/paid-v2 endpoints)
- `google-cloud-translate` (`pip install google-cloud-translate`) for the
  v3 workflows (plain `--v3` and Adaptive MT) — uses Application Default
  Credentials (`gcloud auth application-default login`)
- `gpg` only if you use encrypted `--api-key-file`
- `pandoc` (.md -> PDF) or `pdflatex` (.tex -> PDF) for `--compile`

## Usage

Prefer `--config` for complex/adaptive runs — see `translate_docs.example.json`:

```sh
# single file (free endpoint, no key)
./translate_docs.py --to de guides/manuals/preconditioning_manual.tex

# whole tree, custom output dir
./translate_docs.py --to es --all -o /tmp/out

# v3 without adaptive (plain) + optional model
./translate_docs.py --v3 --project my-proj --to de guides/manuals/preconditioning_manual.tex
./translate_docs.py --v3 --project my-proj --model general/translation-llm --to de FILE

# adaptive + config file (German example)
./translate_docs.py --config translate_de.json guides/manuals/preconditioning_manual.tex

# also compile to PDF, or just compile existing translations
./translate_docs.py --to fr --compile --all
./translate_docs.py --compile-only --all

# preview without calling Google
./translate_docs.py --to nl --dry-run FILE
```

## Available languages

`--to` accepts these codes; for `.tex` files the babel package is patched
automatically for each one (use `--no-babel` to disable).

| Code   | Language              |
|--------|-----------------------|
| `cs`   | Czech                 |
| `da`   | Danish                |
| `de`   | German                |
| `el`   | Greek                 |
| `en`   | English               |
| `es`   | Spanish               |
| `fi`   | Finnish               |
| `fr`   | French                |
| `hu`   | Hungarian             |
| `it`   | Italian               |
| `ja`   | Japanese              |
| `ko`   | Korean                |
| `nl`   | Dutch                 |
| `pl`   | Polish                |
| `pt`   | Portuguese            |
| `pt-br`| Brazilian Portuguese  |
| `ro`   | Romanian              |
| `ru`   | Russian               |
| `sv`   | Swedish               |
| `tr`   | Turkish               |
| `zh-cn`| Chinese (Simplified)  |

Markdown files are not babel-patched, so they can use any language code the
Google Translate API supports, not just the ones listed above.

## Notes

### What is translated / kept verbatim

- **Markdown rendered text:** headings, paragraphs, list items, link labels,
  image alt text. Section links are updated — each translated heading gets
  an explicit `{#slug}` id and every `[text](#old-slug)` is rewritten.
- **LaTeX rendered text:** body prose, section titles, captions, `\item`
  text, `\href` display text, `\title`/`\author`, abstract.
- **Kept verbatim — Markdown:** code spans/fences, URLs, image paths, HTML
  tags, formatting.
- **Kept verbatim — LaTeX:** preamble, every command, `\label`/`\ref`/`\cite`,
  math, file paths, URLs, emails, `\includegraphics`, bibliography, comments.

### Workflow details

1. After translating, sanity-check that no Private-Use-Area placeholders
   remain: `rg -n $'\ue000-\uf8ff' file.fr.tex` should produce no output.
2. Compile to PDF (`--compile` or `--compile-only`; `pandoc` for `.md`,
   `pdflatex` for `.tex`; LaTeX needs `babel` for the target language).
3. Spot-check a few sections — machine translation is not perfect.

### Endpoints and config

- **Config file:** ` --config FILE` reads JSON with keys mirroring long
  option names (`--adaptive-example` → `adaptive_example`); CLI overrides
  config. Minimal v3 example `translate_de.json`:
  ```json
  {
    "to": "de",
    "project": "my-gcp-project",
    "adaptive_example": "guides/manuals/preconditioning_manual_2a57ad.tex",
    "files": ["guides/manuals/preconditioning_manual.tex"]
  }
  ```
  Boolean flags use `true`/`false`, source files as `files`. A personal
  config with tokens should stay out of git — see
  `translate_docs.example.json`.
- **Free endpoint (default):** `https://translate.googleapis.com/translate_a/single?client=gtx`
  — no key, keep `--delay` modest.
- **Paid v2:** `--api-key` / `--api-key-file` / `$GOOGLE_TRANSLATE_API_KEY`
  uses `https://translation.googleapis.com/language/translate/v2` with
  `model=nmt` (500k chars/mo free, $20/M after; higher rate limits). `gpg -d`
  keeps the key out of history.
- **Plain v3:** `--v3 --project PROJECT` uses
  `https://translation.googleapis.com/v3/projects/PROJECT/locations/LOCATION:translateText`
  via `translate_v3` (no adaptive reference; `--model` selects
  `general/nmt` or `general/translation-llm`).
- **Adaptive v3:** `--adaptive-example` + `--project` uses
  `https://translation.googleapis.com/v3/projects/PROJECT/locations/LOCATION:adaptiveMtTranslate`
  via the `translate_v3` library. Reference sentence pairs are extracted from
  the example pair and the 5 most relevant are sent per request. Requires a
  GCP project and Application Default Credentials (`gcloud auth
  application-default login`). For German use `preconditioning_manual_2a57ad.*`
  as example; dataset mode via `--adaptive-dataset` is also supported. `--v3`
  and `--adaptive-*` are mutually exclusive.

### Change detection and git

- Each output embeds a comment with source path and git commit
  (`% translate_docs: FILE @ COMMIT` / `<!-- ... -->`). Re-running skips
  translation if the source hasn't changed; `--compile-only` skips compiling
  if the embedded commit still matches.
- Only `git`–tracked files are processed; untracked files are skipped.
  Outside a git repo all filtering is disabled.

### LaTeX babel

For `.tex`, if the target language is in the table above the preamble is
patched to select it (`--no-babel` disables).
