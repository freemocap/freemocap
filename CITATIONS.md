# References and intellectual provenance

Each independent repository owns a root `references.bib`, created when it first
needs citations. Core's bibliography belongs here, not in the outer workspace.
Other repositories adopt this policy when relevant work reaches them; do not
pre-create empty bibliographies. This follows SkellySpeak's repository convention
[@skellyspeakGraph2026].

Register sources that materially inform scientific claims, algorithms, architecture,
implementation choices or tutorials: papers, books, standards, websites, source
repositories and documentation all count. Prefer primary sources. Retain useful
background sources with an honest claim/review record rather than deleting unused
entries. This is an intellectual paper trail, not a requirement to cite trivial
syntax or invent evidence for original design decisions.

## Bibliography format

Use UTF-8 BibTeX compatible with Better BibTeX export, stable ASCII citation keys,
braced field values, and protected proper names/corporate authors. Better BibTeX
is a Zotero tool, not a separate bibliography language. Pin existing keys when
using Zotero; preserve custom fields during export [@betterBibtexExport].
Our validator deliberately supports this braced subset, including nested braces
and escapes. Normalize quoted values/macros/concatenation before committing;
unsupported syntax fails rather than being silently ignored. No Zotero installation
or dependency change is required to maintain the file.

Every entry needs `title`, `author` or `editor`, `url`, `urldate` (YYYY-MM-DD),
`review`, and `claim`. Use the appropriate entry type and supply verified publication
metadata: year, venue/publisher, volume/pages, DOI, version or commit as applicable.
For undated websites omit the publication year; access date is not publication date.
Use `@misc` for websites/repositories for conventional BibTeX compatibility.

Custom provenance fields:

* `review`: `metadata`, `abstract`, `excerpt`, `full-text`, or `source-code`.
  This records material inspected, not scientific endorsement or independent validation.
* `claim`: the specific supported proposition or why the source is retained.
* `note`: scope, limitations, inaccessible primary text, version/commit and local
  modifications when these affect interpretation. Required for limited review
  (`metadata`, `abstract`, `excerpt`).

Do not fabricate missing metadata. Record secondary-only access and uncertainty.
Use a stable official URL and DOI when available; pin repository references to a
revision where practical. Merge duplicate sources rather than minting new keys.

## In-text use and checks

Use `[@skellyspeakGraph2026]` beside the supported statement in Markdown/MDX and
source comments; groups use `[@gstreamerPads; @gstreamerScheduling]`.
These are provenance markers; adding this
policy does not install a rendered bibliography plugin. Human-friendly links may
accompany markers. Citation examples use real registered keys, so they are checked.
For YAML/JSON, use a comment with a marker where supported, or reference a cited
design note; structured `sources` fields are not presently scanned.

Run from the repository root with any Python 3.11+ interpreter:

```text
python -B tools/check_references.py
python -B -m unittest discover -s tools -p "test_references.py" -v
```

The checker validates syntax, duplicate keys/fields/URLs/DOIs, required metadata,
review labels and dates, and unresolved bracketed citation keys in repository
Markdown/MDX, Python, Rust, JS/TS, YAML, JSON and TeX source. It skips generated,
environment and dependency directories. Tests use in-memory fixtures. CI runs
without application dependencies or network access. These checks cannot establish
claim support, discover uncited ideas, or certify that links remain accessible;
review every changed claim and its evidence during handoff. Existing uncatalogued
literature is migrated as its owning material is reviewed, not claimed complete.
