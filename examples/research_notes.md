# Example: research notes

How a research notebook might use Forest 0.4. The authority-holder is the researcher (or lab citation standard).

A source claim enters wild wood:

```yaml
jurisdiction: wild
bucket: import
source: paper-doi-or-url
signature: source:paper-doi-or-url
body: Exact quoted or summarized source passage, depending on your citation rules.
```

A researcher interpretation enters home wood:

```yaml
jurisdiction: home
bucket: note
signature: researcher
origin: cites -> source_entry
body: We will treat this result as relevant to experiment B, not experiment A.
```

The source owns the claim (wild `import`). Jurisdiction is *why* it is here, not a data type. The researcher's note becomes project ground only through an optional **root** — an `adoption_record` with `adopts` → that note (in place). Not universal truth; project truth when you need it.

`recall` returns bounded previews (jurisdiction first). Full passage body is `read` after ticketed `open` → `around` → `step`. An earned wild `read` cites into the next conversation pair.
