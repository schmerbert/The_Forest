# Example: writer canon

How a fiction-writing tool might use Forest. The authority-holder is the author.

Author says:

> Her brother's name is Elias.

Stored as:

```yaml
bucket: session_pair
signature: conversation
body: |
  USER: Her brother's name is Elias.
```

Extracted ground — written by the adoption ceremony, one transaction:

```yaml
# the ground text
bucket: canon
signature: author
origin: derived_from -> session_pair
body: Her brother's name is Elias.

# the authority act that makes it ground
bucket: adoption_record
signature: author            # who spoke the adopting words
edge: adopts -> canon entry
body: "Yes — that's canon: her brother is Elias."
```

The canon entry is ground *because* the adoption record points at it. There is no status column to set.

Assistant proposes:

```yaml
bucket: inference
signature: model
origin: derived_from -> canon_entry
body: Maybe Elias betrayed her.
```

That proposal can retrieve. It cannot become canon until the author adopts it through a recorded ceremony.
