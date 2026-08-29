#!/usr/bin/env python3
"""Translate rendered text in .md and .tex files via Google Translate,
preserving all markup so the translated files still render correctly.

What is translated (the "rendered" text only):
  - Markdown: headings, paragraphs, list items, link labels, image alt text.
    Section links are updated too: each translated heading gets an explicit
    {#slug} id (matching GitHub and pandoc) and every [text](#old-slug)
    reference is rewritten to the new slug.
  - LaTeX: body prose, section titles, captions, \\item text, \\href display
    text, \\title/\\author, abstract text.
What is kept verbatim:
  - Markdown: code spans/fences, URLs, image paths, HTML tags, formatting.
  - LaTeX: preamble, every command, \\label/\\ref/\\cite, math, file paths,
    URLs, emails, \\includegraphics, bibliography, comments.

Workflow
--------
  1. Translate one or more files (or an entire tree) to a language:

       ./translate_docs.py --to fr guides/manuals/preconditioning_manual.tex
       ./translate_docs.py --to de --all
       ./translate_docs.py --to es -o /tmp/translations guides/manuals/*.tex guides/cars/*/*/*.md

  2. Sanity check: no Private-Use-Area placeholder characters should remain.

       rg -n $'\ue000-\uf8ff' preconditioning_manual.fr.tex   # expect no output

  3. Compile to PDF and inspect: add --compile to the translate command, or
     use --compile-only on files that are already translated:

       ./translate_docs.py --to fr --compile manuals/welcome_precon.tex
       ./translate_docs.py --compile-only --all

     .md files compile with `pandoc <file>.md -o <file>.pdf`, .tex files with
     `pdflatex`. LaTeX output requires the babel module for the target
     language (use --no-babel if it is missing).

  4. Spot check a few translated sections by eye; machine translation is
     not perfect.

Quick examples
--------------
     # free endpoint (no key needed)
     ./translate_docs.py --to de guides/manuals/preconditioning_manual.tex

     # paid API, key from env var
     GOOGLE_TRANSLATE_API_KEY=$KEY ./translate_docs.py --to es --all

     # paid API, key in a GPG-encrypted file
     echo -n "$KEY" | gpg -c -o api_key.gpg
     ./translate_docs.py --api-key-file api_key.gpg --to fr -o /tmp/translations guides/manuals/*.tex guides/cars/*/*/*.md

     # translate and compile to PDF in one go
     ./translate_docs.py --api-key-file api_key.gpg --to it --compile guides/manuals/welcome_precon.tex

     # just compile existing translated files, no translation
     ./translate_docs.py --compile-only --all

     # see what would be done without calling Google
      ./translate_docs.py --to nl --dry-run guides/manuals/preconditioning_manual.tex

     # adaptive translation using a hand-polished example for German
      ./translate_docs.py --to de --adaptive-example guides/manuals/preconditioning_manual_2a57ad.tex \
          --project my-gcp-project guides/manuals/preconditioning_manual.tex

     # same run, but parameters read from a JSON config file
      ./translate_docs.py --config translate_de.json guides/manuals/preconditioning_manual.tex

Notes
-----
  * Run parameters can be read from a JSON config file with --config. Keys
    mirror the long option names with dashes turned into underscores, e.g.
    --adaptive-example becomes "adaptive_example". Any option you pass on the
    command line overrides the config value; config values act as defaults.
    For the adaptive example above, translate_de.json could contain:

        {
          "to": "de",
          "source": "en",
          "delay": 0.5,
          "adaptive_example": "guides/manuals/preconditioning_manual_2a57ad.tex",
          "project": "my-gcp-project",
          "location": "us-central1",
          "access_token_file": "token.gpg"
        }

    Boolean flags (e.g. "compile", "dry_run") accept true/false, and the
    source files can be given as "files". A personal config holding access
    tokens is best kept out of git.
  * Defaults to the free/unofficial endpoint
    https://translate.googleapis.com/translate_a/single?client=gtx
    No API key required; keep --delay modest to avoid rate limits.
  * With --api-key, --api-key-file, or the GOOGLE_TRANSLATE_API_KEY
    environment variable the paid Google Cloud Translation API v2 endpoint
    https://translation.googleapis.com/language/translate/v2 is used instead.
    The request pins model=nmt (Neural Machine Translation), the
    price-optimized product: the first 500,000 characters/month are free and
    it costs $20/million characters after that (vs $80/M for Custom
    Translation and $25/M each way for Adaptive Translation).
    --api-key-file decrypts the key with `gpg -d FILE`, keeping it out of
    shell history. The paid endpoint has higher rate limits and counts against
    your billing quota.
  * With --adaptive-example and --project, the Google Cloud Translation
    Adaptive MT (LLM) endpoint
    https://translation.googleapis.com/v3/projects/PROJECT/locations/LOCATION:adaptiveMtTranslate
    is used. The request pins model=llm (the LLM-based adaptive translation
    model) and carries the reference sentence pairs. The script extracts
    reference sentence pairs from the example pair (e.g.
    guides/manuals/preconditioning_manual_2a57ad.tex and its .de.tex
    hand-polished German translation for --to de) and sends the 5 most
    relevant pairs per request to tailor the translation. Requires a GCP
    project and OAuth token (--access-token, $GOOGLE_OAUTH_ACCESS_TOKEN,
    or `gcloud auth print-access-token`). For the German translation the
    preconditioning_manual_2a57ad.* pair is the recommended example; inline
    reference pairs are used (no dataset creation needed), or specify
    --adaptive-dataset for a pre-created dataset.
  * Originals are never modified: output is written to
    basename.<lang><ext> next to the source (or into --out-dir).
  * Change detection: each translated output embeds a comment tagging the
    source file and the git commit it was translated from
    (`% translate_docs: FILE @ COMMIT` / `<!-- translate_docs: ... -->`).
    Re-running `--to` on an output whose source has not changed since that
    commit skips translation; `--compile-only` skips compiling a translated
    file whose embedded commit still matches its working-tree content.
    This requires a git repo; outside one, everything is always processed.
  * Only files tracked by git are processed: untracked files are skipped.
    All git-based features (tracking filter, change detection, embedded
    commit tags) require a git repo; outside one, only files explicitly
    listed as arguments are translated.
  * For .tex, if the target language is known to babel the preamble is patched
    to select that language (--no-babel disables this).
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

API_PAID = "https://translation.googleapis.com/language/translate/v2"
API_FREE = "https://translate.googleapis.com/translate_a/single"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) translate_docs"}
API_KEY_ENV = "GOOGLE_TRANSLATE_API_KEY"
PUA_START = 0xE000
PUA_END = 0xF8FF
PUA_RE = re.compile(r"[\ue000-\uf8ff]")
MAX_CHARS = 1500
MAX_ATTEMPTS = 3
BABEL = {
    "en": "english", "fr": "french", "de": "german", "es": "spanish",
    "it": "italian", "pt": "portuguese", "pt-br": "brazilian",
    "nl": "dutch", "pl": "polish", "ru": "russian", "zh-cn": "chinese",
    "ja": "japanese", "ko": "korean", "sv": "swedish", "da": "danish",
    "fi": "finnish", "cs": "czech", "tr": "turkish", "ro": "romanian",
    "el": "greek", "hu": "hungarian",
}

# ---------------------------------------------------------------------------
# Adaptive translation helpers (Google Cloud Translation Adaptive MT)
# ---------------------------------------------------------------------------

def _words(text):
    return re.findall(r"[A-Za-z]+", text.lower())


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _sim(a, b):
    A, B = set(_words(a)), set(_words(b))
    if not A or not B:
        return 0.0
    return 2.0 * len(A & B) / (len(A) + len(B))


def _align_units(a, b, sim=_sim):
    n, m = len(a), len(b)
    gap, neg = -0.9, -1e9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i * gap
    for j in range(m + 1):
        dp[0][j] = j * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = max(dp[i - 1][j - 1] + sim(a[i - 1], b[j - 1]),
                           dp[i - 1][j] + gap, dp[i][j - 1] + gap)
    i, j, pairs = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + sim(a[i - 1], b[j - 1]):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + gap:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    pairs.reverse()
    return pairs


def _body_blocks(text):
    start = text.find("\\begin{document}")
    body = text[start:] if start != -1 else text
    return [b for b in re.split(r"\n[ \t]*\n", body) if b.strip()]


_ABBREV_RE = re.compile(
    r"\b(?:Fig|Abb|e\.g|i\.e|etc|vs|Dr|Mr|Ms|No|cf|et al)\.")


def _pure_sentences(block, rules):
    """Extract pure-text sentences from a block (markup stripped).

    Protected spans are elided to a single space so they never split a
    sentence into fragments, and known abbreviations (Fig., e.g., ...) are
    guarded so they are not mistaken for sentence boundaries."""
    prot = Protector()
    protected = prot.protect(block, rules)
    pure = re.sub(r"\s+", " ", PUA_RE.sub(" ", protected)).strip()
    pure = _ABBREV_RE.sub(lambda m: m.group(0)[:-1] + "\u00b7", pure)
    sents = []
    for s in re.split(r"(?<=[.!?])\s+", pure):
        s = s.replace("\u00b7", ".").strip()
        if s and _has_letters(s):
            sents.append(s)
    return sents


def _extract_reference_pairs(src_path, tgt_path, rules):
    src_text = open(src_path, encoding="utf-8").read()
    tgt_text = open(tgt_path, encoding="utf-8").read()
    if rules is TEX_RULES:
        src_blocks = _body_blocks(src_text)
        tgt_blocks = _body_blocks(tgt_text)
    else:
        src_blocks = [b.strip() for b in re.split(r"\n[ \t]*\n", src_text) if b.strip()]
        tgt_blocks = [b.strip() for b in re.split(r"\n[ \t]*\n", tgt_text) if b.strip()]
    pairs = []
    for s_blk, t_blk in zip(src_blocks, tgt_blocks):
        s_sents = _pure_sentences(s_blk, rules)
        t_sents = _pure_sentences(t_blk, rules)
        if not s_sents or not t_sents:
            continue
        aligned = _align_units(s_sents, t_sents)
        groups = []
        cur = None
        for ai, bi in aligned:
            if ai is not None:
                cur = ai
                groups.append([ai, []])
            if bi is not None and cur is not None:
                groups[-1][1].append(bi)
        for ai, bi_list in groups:
            if not bi_list:
                continue
            s_raw = s_sents[ai].strip()
            t_raw = " ".join(t_sents[bi].strip() for bi in bi_list)
            if not s_raw or not t_raw:
                continue
            if len(s_raw) + len(t_raw) > 512 or len(s_raw) > 400 or len(t_raw) > 400:
                continue
            pairs.append((s_raw, t_raw))
    # Fallback: if too few, try line-level pure sentences
    if len(pairs) < 5:
        for s_blk, t_blk in zip(src_blocks, tgt_blocks):
            sp, tp = Protector(), Protector()
            s_lines = [p.strip() for p in sp.protect(s_blk, rules).split("\n") if p.strip() and _has_letters(p)]
            t_lines = [p.strip() for p in tp.protect(t_blk, rules).split("\n") if p.strip() and _has_letters(p)]
            # Map protected lines back to pure text for pairing
            s_pure = []
            for ln in s_lines:
                # ln is protected line, get pure text by stripping PUA
                pure = PUA_RE.sub(" ", ln).strip()
                pure = re.sub(r"\s+", " ", pure)
                if pure and _has_letters(ln):
                    s_pure.append(pure)
            t_pure = []
            for ln in t_lines:
                pure = PUA_RE.sub(" ", ln).strip()
                pure = re.sub(r"\s+", " ", pure)
                if pure and _has_letters(ln):
                    t_pure.append(pure)
            aligned = _align_units(s_pure, t_pure)
            groups = []
            cur = None
            for ai, bi in aligned:
                if ai is not None:
                    cur = ai
                    groups.append([ai, []])
                if bi is not None and cur is not None:
                    groups[-1][1].append(bi)
            for ai, bi_list in groups:
                s_raw = s_pure[ai]
                t_raw = " ".join(t_pure[bi] for bi in bi_list)
                if s_raw and t_raw and len(s_raw) + len(t_raw) <= 512:
                    key = _normalize(s_raw)
                    if key not in { _normalize(p[0]) for p in pairs }:
                        pairs.append((s_raw, t_raw))
    return pairs


def _select_reference_pairs(query, pairs, k=5):
    scored = sorted(((_sim(query, src), src, tgt) for src, tgt in pairs),
                    key=lambda x: -x[0])
    # Always return at least min(k, len(pairs)) even if similarity low
    return [(s, t) for _, s, t in scored[:k]]


def _get_access_token(explicit=None):
    if explicit:
        if os.path.isfile(explicit):
            try:
                with open(explicit, encoding="utf-8") as fh:
                    tok = fh.read().strip()
                    if tok:
                        return tok
            except Exception:
                pass
        tok = explicit.strip()
        if tok:
            return tok
    for env in ("GOOGLE_OAUTH_ACCESS_TOKEN", "GOOGLE_CLOUD_ACCESS_TOKEN", "GCLOUD_ACCESS_TOKEN"):
        tok = os.environ.get(env)
        if tok:
            return tok.strip()
    for cmd in (["gcloud", "auth", "print-access-token"],
                ["gcloud", "auth", "application-default", "print-access-token"]):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            continue
    return None


def _get_gcp_project(explicit=None):
    if explicit:
        return explicit.strip()
    for env in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT", "GOOGLE_PROJECT_ID", "GOOGLE_CLOUD_PROJECT_ID"):
        v = os.environ.get(env)
        if v:
            return v.strip()
    try:
        res = subprocess.run(["gcloud", "config", "get-value", "project"],
                             capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "(unset)":
            return res.stdout.strip()
    except Exception:
        pass
    return None


def _adaptive_gtx(text, source, target, adaptive_cfg, reference_pairs=None):
    project = adaptive_cfg.get("project")
    location = adaptive_cfg.get("location", "us-central1")
    dataset = adaptive_cfg.get("dataset")
    access_token = adaptive_cfg.get("access_token")
    if not project or not access_token:
        raise RuntimeError("adaptive translation requires --project and OAuth access token (via --access-token, $GOOGLE_OAUTH_ACCESS_TOKEN, or gcloud auth)")
    parent = f"projects/{project}/locations/{location}"
    url = f"https://translation.googleapis.com/v3/{parent}:adaptiveMtTranslate"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": HEADERS["User-Agent"],
        "x-goog-user-project": project,
    }
    model = adaptive_cfg.get("model", "llm")
    if dataset:
        # Expand short dataset ID to full resource name if needed
        if "/" not in dataset:
            dataset = f"{parent}/adaptiveMtDatasets/{dataset}"
        body = {"model": model, "dataset": dataset, "content": [text]}
    else:
        if reference_pairs is None:
            reference_pairs = adaptive_cfg.get("reference_pairs") or []
            # Select top 5 most relevant for this chunk
            reference_pairs = _select_reference_pairs(text, reference_pairs, k=5)
        # Google requires source/target language codes in referenceSentenceConfig
        src_code = source if source != "auto" else "en"
        body = {
            "model": model,
            "referenceSentenceConfig": {
                "referenceSentencePairLists": [
                    {"referenceSentencePairs": [
                        {"sourceSentence": s, "targetSentence": t}
                        for s, t in reference_pairs
                    ]}
                ],
                "sourceLanguageCode": src_code,
                "targetLanguageCode": target,
            },
            "content": [text],
        }
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            # Response: {"translations": [{"translatedText": "..."}]}
            if "translations" in resp_data and resp_data["translations"]:
                return resp_data["translations"][0].get("translatedText", "")
            # Fallback for other shapes
            if "adaptiveMtTranslations" in resp_data:
                return resp_data["adaptiveMtTranslations"][0].get("translatedText", "")
            return resp_data.get("translatedText", "") or json.dumps(resp_data)
        except Exception as exc:  # noqa: BLE001
            last = exc
            # Try to parse error body for diagnostics (HTTPError has .read())
            try:
                read = getattr(exc, "read", None)
                if callable(read):
                    err = read().decode("utf-8", errors="ignore")  # type: ignore[attr-defined]
                    last = f"{exc} :: {err}"  # type: ignore[assignment]
            except Exception:
                pass
            time.sleep(1.0 * attempt)
    raise RuntimeError(f"Adaptive translation request failed: {last}")

MD_RULES = [
    (r"`[^`\n]+`", re.M),                      # inline code
    (r"<[^>\n]+>", re.M),                      # html tags
    (r"!\[[^\]]*\]\([^)]+\)", re.M),           # images (whole)
    "links",                                   # protect link targets
    (r"\bhttps?://[^\s)\]>\"'<]+", re.M),      # bare urls
    (r"\bmailto:[^\s)\]>\"'<]+", re.M),        # email urls
    (r"\bwww\.[^\s)\]>\"'<]+", re.M),          # bare www
    (r"\{#[^}\n]*\}", 0),                      # header attributes / anchors
    (r"\\[^\s\w]", 0),                         # backslash escapes like \-
    (r"\*\*", 0), (r"__", 0), (r"~~", 0),      # emphasis markers
    (r"^#{1,6}[ \t]*", re.M),                  # atx headings
    (r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+", re.M), # list bullets / numbers
    (r"^[ \t]*(?:>[ \t]*)+", re.M),            # blockquotes
    (r"[ \t]{2,}$", re.M),                     # hard line breaks
]

TEX_RULES = [
    (r"%.*?$", re.M),                          # comments
    (r"\\begin\{verbatim\}.*?\\end\{verbatim\}", re.S),
    (r"\\begin\{(?:align|align\*|equation|equation\*|gather|gather\*|"
     r"multline|multline\*|displaymath|math)\}.*?\\end\{[a-zA-Z*]+\}", re.S),
    (r"\\begin\{[a-zA-Z*]+\}", 0),             # environment openers
    (r"\\end\{[a-zA-Z*]+\}", 0),               # environment closers
    (r"\\includegraphics(?:\[[^\]]*\])?\{[^{}]*\}", 0),
    (r"\\(?:label|ref|eqref|pageref|vref|Vref|autoref|cref|Cref|"
     r"cite|citet|Citep|parencite)\{[^{}]*\}", 0),
    (r"\\url\{[^{}]*\}", 0),
    (r"\\email\{[^{}]*\}", 0),
    (r"\\href\{[^{}]*\}", 0),                  # keep url, translate display text
    (r"\\texttt\{[^{}]*\}", 0),
    (r"\\verb\|[^|]*\|", 0),
    (r"\\bibliographystyle\{[^{}]*\}", 0),
    (r"\\bibliography\{[^{}]*\}", 0),
    (r"\$[^$\n]+\$", re.M),                    # inline math
    (r"\\\[.*?\\\]", re.S),                    # display math
    (r"\\\(.*?\\\)", re.S),                    # inline math
    (r"\\[^a-zA-Z]", 0),                       # escaped chars like \#
    (r"\\([a-zA-Z]+)\*?", 0),                  # command names
    (r"\[[!a-zA-Z]+\]", 0),                    # float specs / labels like [h]
    (r"[{}[\]]", 0),                           # braces / brackets
]


class Protector:
    """Replaces protected spans with unique Private-Use-Area placeholder
    characters. Single codepoints are used so adjacent placeholders can never
    share (and thus lose) a boundary character during translation."""

    def __init__(self):
        self.tokens = {}  # placeholder char -> original text

    def _ph(self, text):
        ch = chr(PUA_START + len(self.tokens))
        self.tokens[ch] = text
        return ch

    def protect(self, text, rules):
        for rule in rules:
            if rule == "links":
                text = re.sub(
                    r"\[([^\]]+)\]\(([^)]+)\)",
                    lambda m: "[" + m.group(1) + "]"
                              + self._ph("(" + m.group(2) + ")"),
                    text)
            else:
                pat, flags = rule
                text = re.sub(pat, lambda m: self._ph(m.group(0)), text,
                              flags=flags)
        return text

    def restore(self, text):
        for ch in sorted(self.tokens, key=ord, reverse=True):
            text = text.replace(ch, self.tokens[ch])
        return text


def gtx(text, source, target, api_key=None):
    """Translate `text` from `source` to `target`. With an API key the paid
    Google Cloud Translation API v2 is used; otherwise the free endpoint."""
    if api_key:
        params = {"q": text, "target": target, "format": "text",
                  "model": "nmt"}
        if source != "auto":
            params["source"] = source
        url = "{}?key={}&{}".format(
            API_PAID, urllib.parse.quote(api_key),
            urllib.parse.urlencode(params))
    else:
        params = {"client": "gtx", "sl": source, "tl": target,
                  "dt": "t", "q": text}
        url = "{}?{}".format(API_FREE, urllib.parse.urlencode(params))
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if api_key:
                return html.unescape(
                    data["data"]["translations"][0]["translatedText"])
            return "".join(seg[0] for seg in data[0])
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last = exc
            time.sleep(1.0 * attempt)
    raise RuntimeError("Google Translate request failed: {}".format(last))


def _split(text):
    if len(text) <= MAX_CHARS:
        return [text]
    pieces, buf = [], ""
    for part in re.split(r"(?<=[.!?])\s+", text):
        if buf and len(buf) + 1 + len(part) > MAX_CHARS:
            pieces.append(buf)
            buf = part
        else:
            buf = (buf + " " + part) if buf else part
    if buf:
        pieces.append(buf)
    return pieces


def translate(text, source, target, delay, api_key=None, adaptive_cfg=None):
    pieces = _split(text)
    out = []
    for i, piece in enumerate(pieces):
        if adaptive_cfg is not None:
            # Select reference pairs most relevant to this piece
            ref_pairs = adaptive_cfg.get("reference_pairs") or []
            sel = _select_reference_pairs(piece, ref_pairs, k=5) if ref_pairs and not adaptive_cfg.get("dataset") else None
            out.append(_adaptive_gtx(piece, source, target, adaptive_cfg, reference_pairs=sel))
        else:
            out.append(gtx(piece, source, target, api_key=api_key))
        if i < len(pieces) - 1:
            time.sleep(delay)
    return " ".join(out)


def _has_letters(text):
    return re.search(r"[^\W\d_]", PUA_RE.sub("", text)) is not None


def translate_spans(protected, source, target, delay, api_key=None, adaptive_cfg=None):
    """Translate only the pure-text spans of a protected block. Protected
    (PUA-placeholder) spans and punctuation-only spans are kept verbatim, so
    Google never sees markup and cannot drop or reorder it."""
    parts = re.split(r"([\ue000-\uf8ff]+)", protected)
    out = []
    for part in parts:
        if not part:
            continue
        if PUA_RE.fullmatch(part) or not _has_letters(part):
            out.append(part)
        else:
            lead = part[:len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()):]
            core = part.strip()
            out.append(lead + translate(core, source, target, delay,
                                        api_key=api_key, adaptive_cfg=adaptive_cfg) + trail)
    return "".join(out)


def translate_block(block, rules, source, target, delay, api_key=None, adaptive_cfg=None):
    """Protect, translate, restore one block. Falls back to per-line
    translation if Google collapses/expands the number of newlines."""
    prot = Protector()
    protected = prot.protect(block, rules)
    if not _has_letters(protected):
        return block
    translated = translate_spans(protected, source, target, delay,
                                 api_key=api_key, adaptive_cfg=adaptive_cfg)
    if translated.count("\n") != block.count("\n"):
        lines = []
        for line in block.split("\n"):
            p = Protector()
            t = p.restore(translate_spans(p.protect(line, rules), source,
                                          target, delay, api_key=api_key,
                                          adaptive_cfg=adaptive_cfg))
            lines.append(t)
            time.sleep(delay)
        translated = "\n".join(lines)
    return prot.restore(translated)


HEADER_ATTR_RE = re.compile(r"\{#[^}]*\}\s*$")


def slugify(text):
    """GitHub-style slug: lower-case, keep runs of word characters, join with
    '-'. Matches pandoc's auto_identifiers for typical headings too."""
    return "-".join(re.findall(r"[\w]+", HEADER_ATTR_RE.sub("", text).lower(),
                               re.UNICODE))


def heading_lines(block):
    """Find ATX heading lines inside a (possibly multi-line) markdown block.
    Returns (line_index, level, heading_text) for each."""
    found = []
    for i, line in enumerate(block.split("\n")):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            found.append((i, len(m.group(1)),
                          HEADER_ATTR_RE.sub("", m.group(2)).strip()))
    return found


def translated_heading_texts(block, line_indices):
    """Extract the translated heading texts from a translated block at the
    given (preserved) line positions."""
    lines = block.split("\n")
    texts = []
    for i in line_indices:
        if i >= len(lines):
            texts.append(None)
            continue
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[i])
        texts.append(HEADER_ATTR_RE.sub("", m.group(2)).strip() if m else None)
    return texts


def build_slug_mapping(headings, trans_texts):
    """headings: (line_index, level, orig_text); trans_texts: parallel list.
    Returns (orig_slug -> trans_slug mapping, trans_slugs parallel list)."""
    ocount, tcount = {}, {}
    mapping, trans_slugs = {}, []
    for (_, _, orig_text), trans_text in zip(headings, trans_texts):
        o = slugify(orig_text)
        oc = ocount.get(o, 0)
        ocount[o] = oc + 1
        orig_slug = o if oc == 0 else "{}-{}".format(o, oc)
        if trans_text is None:
            trans_slugs.append(None)
            continue
        t = slugify(trans_text)
        tc = tcount.get(t, 0)
        tcount[t] = tc + 1
        trans_slug = t if tc == 0 else "{}-{}".format(t, tc)
        trans_slugs.append(trans_slug)
        mapping[orig_slug] = trans_slug
    return mapping, trans_slugs


def inject_header_ids(out_blocks, headings, trans_slugs):
    """Append explicit {#slug} attributes to translated headings that do not
    already carry one, so GitHub and pandoc both use the same identifier.
    headings: (block_index, line_index, orig_text)."""
    for (bi, li, _), ts in zip(headings, trans_slugs):
        if ts is None:
            continue
        lines = out_blocks[bi].split("\n")
        if li < len(lines) and not HEADER_ATTR_RE.search(lines[li]):
            lines[li] += " {#" + ts + "}"
            out_blocks[bi] = "\n".join(lines)


def replace_anchors(text, mapping):
    """Rewrite [text](#old-slug) references to the translated slugs. Longest
    slugs first and a non-slug lookahead avoid partial/prefix matches; a '{'
    lookbehind skips explicit {#id} attributes."""
    for old in sorted(mapping, key=len, reverse=True):
        text = re.sub(r"(?<![{])#" + re.escape(old) + r"(?![a-z0-9_\-])",
                      "#" + mapping[old], text)
    return text


def patch_babel(tex_text, lang):
    if lang.lower() not in BABEL:
        return tex_text
    name = BABEL[lang.lower()]
    tex_text = re.sub(
        r"\\usepackage(\[[^\]]*\])?\{babel\}",
        lambda m: "\\usepackage[" + name + "]{babel}",
        tex_text, count=1)
    tex_text = re.sub(
        r"\\definelanguagealias\{[a-zA-Z-]*\}\{[^{}]*\}",
        lambda m: "\\definelanguagealias{" + lang + "}{" + name + "}",
        tex_text, count=1)
    if re.search(r"\\selectlanguage\{" + re.escape(lang) + r"\}", tex_text) is None:
        tex_text = re.sub(
            r"\\begin\{document\}",
            lambda m: "\\begin{document}\n\\selectlanguage{" + lang + "}",
            tex_text, count=1)
    return tex_text


def translate_markdown(text, source, target, delay, update_anchors=True,
                       api_key=None, adaptive_cfg=None):
    blocks = re.split(r"\n[ \t]*\n", text)
    headings, trans_texts, out = [], [], []
    for bi, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped or re.match(r"^\s*(```|~~~)", stripped):
            out.append(block)
            continue
        hl = heading_lines(block)
        translated = translate_block(block, MD_RULES, source, target, delay,
                                     api_key=api_key, adaptive_cfg=adaptive_cfg)
        out.append(translated)
        if hl:
            for line_no, _, orig_text in hl:
                headings.append((bi, line_no, orig_text))
            trans_texts.extend(translated_heading_texts(
                translated, [l for l, _, _ in hl]))
    mapping = {}
    if update_anchors and headings:
        mapping, trans_slugs = build_slug_mapping(headings, trans_texts)
        inject_header_ids(out, headings, trans_slugs)
    result = "\n\n".join(out)
    if mapping:
        result = replace_anchors(result, mapping)
    return result


def translate_tex(text, source, target, delay, patch_babel_flag=True,
                  api_key=None, adaptive_cfg=None):
    marker = "\\begin{document}"
    start = text.find(marker)
    if start == -1:
        raise ValueError("no \\begin{document} found (is this a .tex file?)")
    body = text[start:]
    body = "\n\n".join(
        translate_block(b, TEX_RULES, source, target, delay, api_key=api_key,
                        adaptive_cfg=adaptive_cfg)
        for b in re.split(r"\n[ \t]*\n", body))
    result = text[:start] + body
    if patch_babel_flag:
        result = patch_babel(result, target)
    return result


def out_path(src, lang, out_dir):
    base = os.path.basename(src)
    stem, ext = os.path.splitext(base)
    name = stem + "." + lang + ext
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, name)
    return os.path.join(os.path.dirname(src) or ".", name)


def compile_pdf(src):
    """Compile a .md (pandoc) or .tex (pdflatex) file to PDF. Returns
    (ok, detail) where detail is the PDF path or an error message."""
    src = os.path.abspath(src)
    ext = os.path.splitext(src)[1].lower()
    d = os.path.dirname(src)
    base = os.path.basename(src)
    pdf = os.path.splitext(src)[0] + ".pdf"
    if ext == ".md":
        cmd = ["pandoc", base, "-o", os.path.basename(pdf)]
    elif ext == ".tex":
        jobname = os.path.splitext(base)[0]
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
               "-jobname", jobname, "-output-directory", d, base]
    else:
        return False, "not a .md or .tex file"
    try:
        res = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    except FileNotFoundError:
        return False, "compiler not found (need pandoc for .md, pdflatex for .tex)"
    if res.returncode != 0:
        tail = (res.stdout + "\n" + res.stderr).strip().splitlines()[-15:]
        return False, "; ".join(tail)
    return True, pdf


def collect_all(include_translated=False):
    """Collect every .md/.tex under the current dir. When translating,
    already-translated files (e.g. manual.fr.tex) are skipped so they are not
    re-translated; when compiling everything, they are included."""
    found = []
    already = re.compile(r"\.([a-z]{2}(-[a-z]{2})?)\.(md|tex)$") \
        if not include_translated else None
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".git", ".ipynb_checkpoints",
                                                "__pycache__")]
        for fn in files:
            if fn.endswith((".md", ".tex")) and (
                    include_translated or already is None
                    or not already.search(fn)):
                found.append(os.path.join(root, fn))
    return sorted(found)


TAG_RE = re.compile(
    r"^(?:%|<!--) translate_docs: (\S+) @ ([0-9a-f]{40,})(?: -->)?\s*$",
    re.MULTILINE)


def _git(args):
    """Run a git subcommand in the script's working dir; None on failure."""
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True)
    except OSError:
        return None


def git_repo():
    """True if running inside a git work tree."""
    r = _git(["rev-parse", "--is-inside-work-tree"])
    return r is not None and r.returncode == 0 \
        and r.stdout.strip() == "true"


def git_commit_of(path):
    """Full commit hash that last touched `path` at HEAD, or None."""
    r = _git(["log", "-1", "--format=%H", "--", path])
    if r is None or r.returncode != 0:
        return None
    return r.stdout.strip() or None


def git_tracked(path):
    """True if `path` is tracked by git (in the index at HEAD)."""
    r = _git(["ls-files", "--error-unmatch", "--", path])
    return r is not None and r.returncode == 0


def git_unchanged_since(path, commit):
    """True if the working-tree content of `path` is identical to its state
    at `commit` (tracked, and no committed or uncommitted changes since)."""
    if not commit:
        return False
    r = _git(["ls-files", "--error-unmatch", "--", path])
    if r is None or r.returncode != 0:
        return False
    d = _git(["diff", "--quiet", commit, "--", path])
    return d is not None and d.returncode == 0


def git_unmodified(path):
    """True if `path` is tracked and has no uncommitted changes (its working
    tree matches HEAD)."""
    r = _git(["ls-files", "--error-unmatch", "--", path])
    if r is None or r.returncode != 0:
        return False
    d = _git(["diff", "--quiet", "HEAD", "--", path])
    return d is not None and d.returncode == 0


def read_tag(text):
    """Extract the embedded (src, commit) tag from translated text."""
    m = TAG_RE.search(text)
    return (m.group(1), m.group(2)) if m else None


def prepend_tag(ext, text, src, commit):
    """Prefix `text` with an invisible comment recording the source path and
    the git commit it was translated from."""
    if ext == ".md":
        return "<!-- translate_docs: {} @ {} -->\n\n{}".format(src, commit, text)
    return "% translate_docs: {} @ {}\n{}".format(src, commit, text)


def _config_defaults(ap):
    """Map option dest -> the value it has when *not* given on the command
    line, so a config file can act as defaults without overriding explicit
    CLI arguments. (argparse reports `None` for nargs='*' actions even though
    parsing yields `[]`.)"""
    out = {}
    for action in ap._actions:
        dest = action.dest
        if not dest or dest == "config":
            continue
        if action.default is not None:
            out[dest] = action.default
        elif action.nargs == argparse.ZERO_OR_MORE:
            out[dest] = []
        else:
            out[dest] = None
    return out


def _load_config(path):
    """Load and validate a JSON run-parameter file."""
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except OSError as exc:
        raise ValueError("cannot read config {}: {}".format(path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("config {} is not valid JSON: {}".format(path, exc)) from exc
    if not isinstance(cfg, dict):
        raise ValueError("config {} must be a JSON object, not {}".format(
            path, type(cfg).__name__))
    return cfg


def _apply_config(args, ap, cfg):
    """Overlay config-file values as defaults; CLI arguments always win."""
    defaults = _config_defaults(ap)
    for key, value in cfg.items():
        if key not in defaults:
            raise ValueError("unknown config key {!r} (valid: {})".format(
                key, ", ".join(sorted(defaults))))
        if getattr(args, key) == defaults[key]:
            setattr(args, key, value)
    return args


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Translate rendered text in .md/.tex files, preserving "
                    "markup.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("files", nargs="*", metavar="FILE",
                    help=".md or .tex files to translate")
    ap.add_argument("--config", metavar="FILE",
                    help="read run parameters from a JSON config file "
                         "(keys mirror the long option names, dashes become "
                         "underscores); explicit command-line options override "
                         "config values")
    ap.add_argument("-t", "--to", metavar="LANG",
                    help="target language code, e.g. fr, de, es, pt-BR "
                         "(required unless --compile-only)")
    ap.add_argument("-s", "--from", dest="source", default="auto",
                    metavar="LANG", help="source language code (default auto)")
    ap.add_argument("-k", "--api-key", metavar="KEY",
                    help="Google Cloud Translation API key; overrides "
                         "$GOOGLE_TRANSLATE_API_KEY. Uses the paid v2 endpoint "
                         "instead of the free one.")
    ap.add_argument("--api-key-file", metavar="FILE",
                    help="GPG-encrypted file containing the API key; decrypted "
                         "with `gpg -d FILE` (the key is never written to "
                         "shell history)")
    ap.add_argument("-o", "--out-dir", metavar="DIR",
                    help="write translated files into DIR")
    ap.add_argument("--delay", type=float, default=0.3,
                    help="seconds between API calls (default 0.3)")
    ap.add_argument("--no-babel", action="store_true",
                    help="do not patch babel language lines in .tex output")
    ap.add_argument("--no-anchors", action="store_true",
                    help="do not update #anchor links or inject header ids "
                         "in .md output")
    ap.add_argument("--compile", action="store_true",
                    help="after translating, compile each output to PDF "
                         "(pandoc for .md, pdflatex for .tex)")
    ap.add_argument("--compile-only", action="store_true",
                    help="compile FILE(s) to PDF without translating")
    ap.add_argument("--all", action="store_true",
                    help="process every .md and .tex under the current dir "
                         "(for --compile-only this includes already-translated "
                         "files like manual.fr.tex)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list inputs/outputs without calling Google Translate")
    ap.add_argument("--adaptive-example", metavar="FILE",
                    help="translate adaptively using Google Cloud Translation "
                         "Adaptive MT: FILE is the source-language document "
                         "and FILE.<lang><ext> (e.g. preconditioning_manual_"
                         "2a57ad.de.tex for --to de) is its reference "
                         "translation. Requires --project and OAuth token. "
                         "For --to de this uses guides/manuals/preconditioning"
                         "_manual_2a57ad.* as the hand-polished German example.")
    ap.add_argument("--project", metavar="PROJECT",
                    help="GCP project ID/number for Adaptive Translation "
                         "(also $GOOGLE_CLOUD_PROJECT, or gcloud config)")
    ap.add_argument("--location", metavar="LOC", default="us-central1",
                    help="GCP location for Adaptive Translation (default us-central1)")
    ap.add_argument("--adaptive-model", metavar="MODEL", default=None,
                    help="Adaptive Translation model to request "
                         "(default llm)")
    ap.add_argument("--adaptive-dataset", metavar="DATASET",
                    help="existing Adaptive MT dataset resource name "
                         "projects/PROJECT/locations/LOC/adaptiveMtDatasets/ID; "
                         "if given, --adaptive-example is ignored for dataset mode")
    ap.add_argument("--access-token", metavar="TOKEN",
                    help="OAuth access token for Adaptive Translation "
                         "(also $GOOGLE_OAUTH_ACCESS_TOKEN or gcloud auth)")
    ap.add_argument("--access-token-file", metavar="FILE",
                    help="GPG-encrypted file containing OAuth access token; "
                         "decrypted with `gpg -d FILE`")
    args = ap.parse_args(argv)

    if args.config:
        try:
            cfg = _load_config(args.config)
            args = _apply_config(args, ap, cfg)
        except ValueError as exc:
            ap.error(str(exc))
        print("using config file: {}".format(args.config))

    files = args.files
    if args.all:
        files = collect_all(include_translated=args.compile_only)
    if not files:
        ap.error("provide FILE(s) or use --all")

    before = len(files)
    if git_repo():
        files = [f for f in files if git_tracked(f)]
        if not files:
            ap.error("no git-tracked .md/.tex files to process")
        if len(files) < before:
            print("note: skipping {} untracked file(s); only files tracked "
                  "by git are processed".format(before - len(files)),
                  file=sys.stderr)
    elif not args.all:
        print("note: not in a git work tree; change detection and the "
              "git-tracking filter are disabled", file=sys.stderr)

    if args.compile_only:
        for src in files:
            tag = None
            if os.path.isfile(src):
                with open(src, encoding="utf-8") as fh:
                    tag = read_tag(fh.read())
            pdf = os.path.splitext(src)[0] + ".pdf"
            if (tag and os.path.isfile(pdf)
                    and (git_unchanged_since(src, tag[1])
                         or git_unmodified(src))):
                print("{} -> SKIP (unchanged since {})".format(
                    src, tag[1][:8]))
                continue
            ok, detail = compile_pdf(src)
            print("{} -> {}".format(src, "OK" if ok else "FAILED"))
            if not ok:
                print("  {}".format(detail))
        return 0

    if not args.to:
        ap.error("-t/--to is required for translation")

    api_key = args.api_key or os.environ.get(API_KEY_ENV)
    if args.api_key_file:
        try:
            res = subprocess.run(["gpg", "-d", args.api_key_file],
                                 capture_output=True, text=True, check=True)
            api_key = res.stdout.strip()
        except FileNotFoundError:
            ap.error("gpg not found on PATH (needed for --api-key-file)")
        except subprocess.CalledProcessError as exc:
            ap.error("gpg -d {} failed: {}".format(
                args.api_key_file, exc.stderr.strip() or exc))
    if api_key:
        print("using paid Google Cloud Translation API v2")

    # ---- Adaptive Translation (Google Cloud Adaptive MT) -----------------
    adaptive_cfg = None
    if args.adaptive_example or args.adaptive_dataset:
        if not args.to:
            ap.error("--adaptive-example/--adaptive-dataset requires -t/--to")
        project = _get_gcp_project(args.project)
        access_token = _get_access_token(args.access_token)
        if args.access_token_file and not access_token:
            try:
                res = subprocess.run(["gpg", "-d", args.access_token_file],
                                     capture_output=True, text=True, check=True)
                access_token = res.stdout.strip()
            except FileNotFoundError:
                ap.error("gpg not found on PATH (needed for --access-token-file)")
            except subprocess.CalledProcessError as exc:
                ap.error("gpg -d {} failed: {}".format(
                    args.access_token_file, exc.stderr.strip() or exc))
        dataset = args.adaptive_dataset
        reference_pairs = None
        if dataset and args.adaptive_example:
            print("note: --adaptive-dataset given, ignoring --adaptive-example for dataset selection",
                  file=sys.stderr)
        if not dataset and args.adaptive_example:
            ext = os.path.splitext(args.adaptive_example)[1].lower()
            if ext not in (".md", ".tex"):
                ap.error("--adaptive-example must be a .md or .tex file")
            if not os.path.isfile(args.adaptive_example):
                ap.error("--adaptive-example file not found: {}".format(args.adaptive_example))
            # Derive target example via same naming as out_path
            # (preconditioning_manual_2a57ad.tex -> .de.tex for --to de)
            example_tgt = out_path(args.adaptive_example, args.to, None)
            if not os.path.isfile(example_tgt):
                ap.error("--adaptive-example target not found: {} (expected {} for --to {})".format(
                    example_tgt, example_tgt, args.to))
            rules = TEX_RULES if ext == ".tex" else MD_RULES
            reference_pairs = _extract_reference_pairs(args.adaptive_example, example_tgt, rules)
            if not reference_pairs:
                ap.error("no reference pairs extracted from {} -> {}".format(
                    args.adaptive_example, example_tgt))
            if len(reference_pairs) < 5:
                print(f"warning: only {len(reference_pairs)} reference pairs extracted (need >=5 for best results)",
                      file=sys.stderr)
            print(f"adaptive translation: extracted {len(reference_pairs)} reference pairs from "
                   f"{args.adaptive_example} -> {example_tgt}")
        # For --dry-run no API call is made, so token/project are not strictly required
        if not args.dry_run:
            if not project:
                ap.error("adaptive translation requires --project (or $GOOGLE_CLOUD_PROJECT / gcloud config)")
            if not access_token:
                ap.error("adaptive translation requires OAuth token (--access-token, $GOOGLE_OAUTH_ACCESS_TOKEN, or gcloud auth login)")
        else:
            if not project:
                print("note: --dry-run without --project, would require --project for real translation",
                      file=sys.stderr)
            if not access_token:
                print("note: --dry-run without access token, would require OAuth token for real translation",
                      file=sys.stderr)
            # Use dummy token for dry-run path (no network)
            if not access_token:
                access_token = "dry-run-token"
            if not project:
                project = "dry-run-project"
        if dataset and "/" not in dataset:
            # Expand short ID
            dataset = f"projects/{project}/locations/{args.location}/adaptiveMtDatasets/{dataset}"
        adaptive_cfg = {
            "project": project,
            "location": args.location,
            "dataset": dataset,
            "model": args.adaptive_model or "llm",
            "reference_pairs": reference_pairs,
            "access_token": access_token,
        }
        if dataset:
            print(f"using Google Adaptive Translation dataset {dataset} in {args.location}")
        else:
            assert reference_pairs is not None  # extracted above
            print(f"using Google Adaptive Translation (model {args.adaptive_model or 'llm'}) with "
                  f"{len(reference_pairs)} reference pairs from {args.adaptive_example} "
                  f"(project {project}, {args.location})")

    for src in files:
        dst = out_path(src, args.to, args.out_dir)
        ext = os.path.splitext(src)[1].lower()
        if ext not in (".md", ".tex"):
            print("skip (not .md/.tex):", src, file=sys.stderr)
            continue
        print("{} -> {}".format(src, dst))
        if args.dry_run:
            continue
        if os.path.isfile(dst):
            with open(dst, encoding="utf-8") as fh:
                tag = read_tag(fh.read())
            if (tag and tag[0] == src
                    and git_unchanged_since(src, tag[1])):
                print("  unchanged since {}, skipping translation".format(
                    tag[1][:8]))
                if args.compile:
                    ok, detail = compile_pdf(dst)
                    print("  compile: {} -> {}".format(
                        "OK" if ok else "FAILED", detail))
                continue
        with open(src, encoding="utf-8") as fh:
            content = fh.read()
        if ext == ".md":
            result = translate_markdown(content, args.source, args.to,
                                        args.delay,
                                        update_anchors=not args.no_anchors,
                                        api_key=api_key,
                                        adaptive_cfg=adaptive_cfg)
        else:
            result = translate_tex(content, args.source, args.to, args.delay,
                                   patch_babel_flag=not args.no_babel,
                                   api_key=api_key,
                                   adaptive_cfg=adaptive_cfg)
        commit = git_commit_of(src)
        if commit:
            result = prepend_tag(ext, result, src, commit)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(result)
        print("  wrote {} bytes".format(len(result.encode("utf-8"))))
        if args.compile:
            ok, detail = compile_pdf(dst)
            print("  compile: {} -> {}".format("OK" if ok else "FAILED", detail))

    return 0


if __name__ == "__main__":
    sys.exit(main())
