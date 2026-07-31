# Example: codebase memory

How a code agent might use Forest 0.4. The authority-holder is the maintainer or accepted spec.

An old architectural decision enters wild wood:

```yaml
bucket: import
jurisdiction: wild
signature: source:docs/adr-004.md
body: The monolith owns user authentication.
```

A later changelog entry:

```yaml
bucket: import
jurisdiction: wild
signature: source:CHANGELOG.md
body: Auth moved to the identity service in v3.
```

A model may write an attributed **synthesis** in home, edged back to those wild
imports (`cites`). The raw ADR/changelog rows stay wild — they do not change
jurisdiction.

`recall_similar` surfaces bounded previews (jurisdiction first). Synthesis is not
project ground until the maintainer **roots** the entry in place — and only if it
must stay true. Full body disclosure is `read` after ticketed `open` → `around` →
`step`. Wild reads cite into the next pair.
