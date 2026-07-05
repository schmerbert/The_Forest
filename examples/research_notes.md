# Example: research notes

How a research notebook might use Forest. The authority-holder is the researcher (or lab citation standard).

A source claim enters wild wood:

```yaml
forest: wild
bucket: import
signature: source:paper-doi-or-url
body: Exact quoted or summarized source passage, depending on your citation rules.
```

A researcher interpretation enters home wood:

```yaml
forest: home
bucket: note
signature: researcher
origin: cites -> source_entry
body: We will treat this result as relevant to experiment B, not experiment A.
```

The source owns the claim (wild-wood `import`). The researcher's note becomes project ground only through an adoption ceremony — an `adoption_record` with an `adopts` edge to a canon entry (ground for this project only, not universal truth).
