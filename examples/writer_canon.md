# Example: writer canon

Author says:

> Her brother's name is Elias.

Stored as:

```yaml
bucket: session_pair
signature: conversation
authority: record
body: |
  USER: Her brother's name is Elias.
```

Extracted ground:

```yaml
bucket: canon
signature: author
authority: ground
origin: spoken_in -> session_pair
body: Her brother's name is Elias.
```

Assistant proposes:

```yaml
bucket: inference
signature: model
authority: inference
origin: derived_from -> canon_entry
body: Maybe Elias betrayed her.
```

That proposal can retrieve. It cannot become canon until adoption.
