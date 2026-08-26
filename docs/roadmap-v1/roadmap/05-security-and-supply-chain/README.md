# Stage 05 — Security and Supply Chain

## Repository ownership

### forge-template

- **FT-05.01 — Define dependency update automation**
- **FT-05.02 — Harden GitHub Actions permissions**
- **FT-05.03 — Define GitHub Action pinning policy**
- **FT-05.04 — Add secret-handling safeguards**
- **FT-05.05 — Plan SBOM and release provenance capability**

### create-forge

- Epic: [CF-EPIC-05 / #36](https://github.com/Sandsy09/create-forge/issues/36)
- ~~**CF-05.01 — Harden create-forge CI and release permissions**~~ — completed before roadmap filing.
- [x] [**CF-05.02 — Define template-engine dependency update policy**](https://github.com/Sandsy09/create-forge/issues/45)
  ([ADR 0012](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0012-engine-dependency-update-policy.md),
  [canonical engine update policy](https://github.com/Sandsy09/create-forge/blob/main/docs/engine-updates.md))

## Stage record

CF-05.02 closes the create-forge side of the stage: ADR 0012 defines how a
compatibility-line dependency update is adopted (inside a declared range,
proven by the `network` CI job), how a breaking line is crossed (a
deliberate, human-authored PR following the integration contract's release
sequence), and restricts automated dependency tooling —
`.github/dependabot.yml`'s `uv` entry — from proposing a crossing on its own.
The policy governs `copier` today, the only dependency CLAUDE.md invariant 4
already singles out, and self-arms for the `forge-template` engine once
CF-04.01's resolution rules produce a real dependency to declare. The
distribution channel stays deferred to
[PyPI publishing / #9](https://github.com/Sandsy09/create-forge/issues/9), as
ADR 0011 originally scoped it.

The create-forge epic ([CF-EPIC-05 / #36](https://github.com/Sandsy09/create-forge/issues/36))
is complete. `forge-template`'s Stage 05 counterpart (`FT-EPIC-05`) has not
been filed there yet; that repository's own call.

## Stage completion rule

- [x] Repo-local issues are complete or explicitly deferred.
- [x] Cross-repository blockers are resolved.
- [x] Public contracts changed by this stage are documented/versioned.
- [x] No implementation concern is duplicated across repositories.
