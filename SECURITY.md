# Security

## Reporting a vulnerability

If you believe you have found a security issue in the Forest constitution or reference wrapper, please report it privately:

- Open a [GitHub Security Advisory](https://github.com/schmerbert/The_Forest/security/advisories/new) (preferred), or
- Email **forrestwestphal@gmail.com** with a description and reproduction steps

Do not open a public issue for undisclosed vulnerabilities.

## Scope

In scope:

- Append-only guarantees bypassed by schema or wrapper bugs
- Sealed entries leaking through retrieval paths
- Custody laundering (inference/hearsay promoted to ground without ceremony)
- Silent rewrite or drift detection failures in the reference wrapper

Out of scope for this repository:

- Application-layer ceremony design in downstream projects
- SQLite engine vulnerabilities (report upstream)
- Deployments that call `ForestStore.adopt()` directly without a promotion gate

## Response

We aim to acknowledge reports within 72 hours and provide a fix or mitigation timeline for confirmed issues affecting the constitutional layer.

## Past disclosures

- **v0.1 promotion boundary (fixed in 0.2.0).** Entry status was stored in
  mutable columns; direct writes could forge ground, unseal sealed text, and
  launder inference into canon without ceremony. v0.2 derives status from the
  append-only record trail. Details and migration guide in the
  [CHANGELOG](CHANGELOG.md).

## Threat model

The SQL triggers defend against buggy or confused application code. They do
not defend against an adversary with write access to the database file —
whoever can run `UPDATE` can also run `DROP TRIGGER`. Deployments needing
protection against a hostile writer must put the file behind an
authenticating service boundary. Speaker authentication for adoption quotes
is the host application's responsibility; the store records the claimed
signature verbatim.
