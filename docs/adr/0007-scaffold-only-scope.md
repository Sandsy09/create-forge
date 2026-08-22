# 7. Scaffold-only scope

## Status

Accepted

## Context

Tools like `pnpm create-payload-app`, which this project is explicitly
modelled on, sometimes go further than scaffolding files locally — creating
the remote repository and pushing the first commit for the user. Nothing in
principle stops `create-forge` from doing the same: `runner.scaffold()`
already leaves a project git-initialised and ready to commit
([ADR 0005](0005-execute-template-tasks.md)); creating the remote and pushing
would be a natural-feeling next step.

## Decision

`create-forge` scaffolds local projects only. It does not create GitHub
repositories, and it does not push anywhere.

This was rejected specifically, not just left undone: it would pull `gh` (or
an equivalent GitHub client) into the dependency tree, and repository creation
needs the `workflow` OAuth scope to push `.github/workflows/**` — an opaque
failure for a user who has not thought about OAuth scopes and just wants a
scaffolded project (`gh auth refresh -h github.com -s workflow` is not a
message a first-time user can act on unprompted).

## Consequences

- The tool's surface stays small: `new`, `list`, `update`, `doctor`, `config`.
  None of them touch a remote beyond cloning `forge-template` itself.
- A user who wants a remote repository runs `gh repo create` (or the GitHub
  UI) themselves, after scaffolding — a normal, well-documented step outside
  this tool's concern.
- If repository creation is ever revisited, the `workflow` OAuth scope gotcha
  already recorded in `CLAUDE.md` is the first thing that would need solving,
  and it would need its own ADR rather than folding into this one, since it
  reverses this decision rather than extending it.
