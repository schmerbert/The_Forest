# Example: writer canon

How a fiction-writing harness might use Forest 0.4. The authority-holder is the author. Root is optional — only when a fact must stay true.

Author says:

> Her brother's name is Elias.

Stored as:

```yaml
jurisdiction: home
bucket: pair
signature: conversation
scroll_ptr: {path: session.scroll, offset: …}
body: |
  USER: Her brother's name is Elias.
```

Prefer `commit_turn(store, scroll, …)` so the pair and scroll stay linked.

Optional root — **in place**: the same entry body becomes ground. Adopting words are the authority *act*, not a second canon. Compare-and-root with `expected_body_hash` so you adopt the exact displayed text.

```yaml
# the authority act (adoption_record)
signature: author
edge: adopts -> that entry
body: "Yes — root this entry exactly as displayed."
expected_body_hash: <sha256 of the entry body>
```

That entry is ground *because* the adoption record points at it. There is no status column to set. Adopting words consent to the **exact displayed body** — they must not silently replace it.

Assistant proposes:

```yaml
jurisdiction: home
bucket: inference
signature: model
origin: derived_from -> pair
body: Maybe Elias betrayed her.
```

If rooted, ground is still that inference sentence — not a paraphrase spoken only in the ceremony.

`recall_similar("Elias")` returns **previews** that lead with `jurisdiction`. Similarity never promotes. Only `root_to_ground` does — and only when you need it. Full body is `read` after ticketed `open` → `around` → `step`.
