# 36. Keep credentials out of template sources and CLI diagnostics

## Status

Accepted

## Context

Issue #139 found that the third-party warning printed the raw template
source before Copier ran. HTTP user-info could therefore reach a shared
terminal or CI log. Unknown Copier error messages were also passed through,
and existing projects can retain credential-bearing sources in their answers
files. Fixing only the warning would leave those paths exposed.

## Decision

Use one pure source-validation and safe-display boundary, shared by the CLI
and runner. Reject HTTP(S) user-info, SSH URL passwords, URL queries and
fragments, malformed authorities, and control characters. Apply equivalent
checks to Copier's git-prefixed and shorthand URLs without rewriting accepted
execution sources. Preserve ordinary SSH usernames, SCP-style sources, and
local paths, where punctuation has filesystem rather than URL semantics.

Validate explicit sources before prompts and all scaffold sources before
destination handling. Read update metadata with PyYAML's safe loader and
validate its recorded source before Copier runs; declare PyYAML directly as
a runtime dependency. Never repair or rewrite existing project metadata
automatically. Reject malformed metadata without quoting it.

Render source warnings as literal text and remove URL authentication, query,
and fragment components defensively. Keep recognised Copier error guidance,
but replace unrecognised messages with fixed instructions. Retain original
exception causes internally under the existing runner contract, without
rendering or logging those chains in normal CLI failures.

## Consequences

Unsafe sources fail with exit 1, including in unattended and dry-run commands.
Users authenticate through Git credential helpers or SSH agents and select
versions with --ref. Legacy projects with unsafe recorded sources need a
manual credential-free replacement before update. Unknown Copier failures
offer less detail in exchange for preventing credential disclosure.

This does not change template trust, create an authentication mechanism,
sandbox template tasks, or alter forge-template. Sentinel regressions cover
raw and encoded forms, CLI output, direct runner calls, update metadata,
literal Rich rendering, and destination preservation.
