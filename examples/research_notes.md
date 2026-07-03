# Example: research notes

A source claim enters wild wood:

```yaml
forest: wild
bucket: import
signature: source:paper-doi-or-url
authority: hearsay
body: Exact quoted or summarized source passage, depending on your citation rules.
```

A researcher note enters home wood:

```yaml
forest: home
bucket: note
signature: researcher
authority: ground
origin: cites -> source_entry
body: We will treat this result as relevant to experiment B, not experiment A.
```

The distinction matters: the source owns the claim; the researcher owns the local interpretation.
