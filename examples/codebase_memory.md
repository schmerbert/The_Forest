# Example: codebase memory

How a code agent might use Forest. The authority-holder is the maintainer or accepted spec.

An old architectural decision enters wild wood:

```yaml
bucket: import
forest: wild
signature: source:docs/adr-004.md
body: The monolith owns user authentication.
```

A later changelog entry:

```yaml
bucket: import
forest: wild
signature: source:CHANGELOG.md
body: Auth moved to the identity service in v3.
```

A model may synthesize:

```yaml
bucket: synthesis
signature: model
origin:
  - cites -> adr_entry
  - cites -> changelog_entry
body: The ADR is probably superseded by v3 identity-service changes.
```

Synthesis can retrieve. It is not project ground until the maintainer adopts it.
