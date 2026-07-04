# Example: research notes

How a research notebook might use Forest. The authority-holder is the researcher (or lab citation standard).

A source claim enters wild wood:

```yaml
forest: wild
bucket: import
signature: source:paper-doi-or-url
authority: hearsay
body: Exact quoted or summarized source passage, depending on your citation rules.
```

A researcher interpretation enters home wood:

```yaml
forest: home
bucket: note
signature: researcher
authority: ground
origin: cites -> source_entry
body: We will treat this result as relevant to experiment B, not experiment A.
```

The source owns the claim (`hearsay`). The researcher owns the local interpretation (`ground` for this project only — not universal truth).
