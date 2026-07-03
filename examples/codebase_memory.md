# Example: codebase memory

A code agent finds an old architectural decision record:

```yaml
bucket: import
forest: wild
signature: source:docs/adr-004.md
authority: hearsay
body: The monolith owns user authentication.
```

Later changelog says:

```yaml
bucket: import
forest: wild
signature: source:CHANGELOG.md
authority: hearsay
body: Auth moved to the identity service in v3.
```

A model may synthesize:

```yaml
bucket: synthesis
signature: model
authority: inference
origin:
  - cites -> adr_entry
  - cites -> changelog_entry
body: The ADR is probably superseded by v3 identity-service changes.
```

It still is not project ground until the maintainer/spec adopts it.
