# Cross-Repository Contributor Workflow

This is the canonical workflow for changes that span `create-forge` and
[`forge-template`](https://github.com/Sandsy09/forge-template). It explains
how to validate both working trees together before publishing a template tag
and how to sequence releases without exposing incompatible combinations.

The repositories are expected to be sibling directories:

```text
<workspace>/
├── create-forge/
└── forge-template/
```

Substitute the real path to `forge-template` if the checkout is elsewhere.
Keep each repository on its own branch and pull request; their ownership and
release histories remain separate.

## Current and target integration

The released v0.1.x CLI owns a bundled prompt registry and calls Copier through
`src/create_forge/runner.py`. The current `--template-url` option is the
sanctioned development escape hatch for selecting a sibling template checkout.
It is also capable of running arbitrary third-party templates, so it always
uses the existing code-execution warning and trust boundary.

The accepted target in [ADR 0010](adr/0010-public-engine-integration-contract.md)
replaces direct Copier integration with the versioned public `forge-template`
engine. Cross-repository development will retain an explicit, warned local or
VCS override, but its exact interface belongs to CF-04.01. Do not treat the
v0.1.x option name as the future contract or bypass the compatibility rules in
the [integration contract](integration-contract.md).

## Prepare both working trees

Start both changes from current `main` and use separate branches:

```bash
cd ../forge-template
git switch main
git pull --ff-only
git switch -c <type>/<template-change>
uv sync --all-groups

cd ../create-forge
git switch main
git pull --ff-only
git switch -c <type>/<cli-change>
uv sync --all-groups
```

Template schema, rendering, generated files, and update compatibility belong
in `forge-template`. CLI flags, prompts, registry presentation metadata,
diagnostics, and orchestration belong in `create-forge`. Do not copy template
validation into the CLI, and do not import Copier anywhere under
`src/create_forge` except `runner.py`.

## Validate the sibling checkout

Run each repository's fast gate first:

```bash
cd ../forge-template
uv run poe check

cd ../create-forge
uv run poe check
```

When `copier.yml` and `templates.toml` change together, point the drift suite
at the working tree rather than its latest release:

```bash
uv run pytest tests/test_drift.py --forge-template-root=../forge-template
```

This test-only option reads `../forge-template/copier.yml` directly, including
uncommitted changes. Without the option, the network-marked drift suite keeps
its normal behavior and clones the latest PEP 440 tag, matching what released
v0.1.x users receive. Keep the option and path in the single equals-form
argument shown above so pytest does not discover the sibling test suite while
processing its initial paths.

Then exercise the real CLI-to-Copier path. Choose an empty disposable target;
the command below uses a sibling directory so neither repository becomes
dirty:

```bash
uv run create-forge new "Cross Repo Smoke" --yes --template-url ../forge-template --ref HEAD --path ../create-forge-cross-repo-smoke --data github_org=test-org --data "author_name=Test User" --data author_email=test@example.invalid
cd ../create-forge-cross-repo-smoke
uv run poe check
```

Return to the repository and remove only the disposable scaffold after its
path and checks have been verified.

`--ref HEAD` is essential. Under the supported Copier 9.x line, a local Git
source with that ref includes committed and dirty working-tree changes.
Omitting it makes Copier resolve the latest PEP 440 tag, which tests the
released template instead of the pending branch.

`--template-url` always prints that template code will execute. `--yes` skips
both ordinary prompts and the confirmation question, but it does not suppress
the warning. Omit `--yes` when manually exercising the confirmation path, and
never use a source you do not trust.

## Choose the remaining template checks

Run the additional `forge-template` checks according to the change:

| Change | Required validation |
| --- | --- |
| Repository tooling, schema checks, or documentation only | `uv run poe check` |
| `template/` or `copier.yml` | `uv run poe combos` after the fast gate |
| Behavior or paths already present in released projects | `uv run poe update` after combos |
| Generated CI workflows | `./scripts/verify-ci.sh <org>` when the cost and GitHub Actions usage are justified |

The local drift suite catches the silent failure mode where the CLI supplies a
registry key Copier no longer recognises. The real scaffold verifies source,
ref, answers, tasks, and generated-project checks. Both are required for a
paired schema/registry change because a successful scaffold alone can look
correct after Copier silently discards an unknown answer.

## Merge and release v0.1.x changes

Merging `forge-template` does not release it: v0.1.x consumers resolve its
latest PEP 440 tag. Use this sequence for compatible paired changes:

1. Open both pull requests and validate their working trees together with the
   local drift and scaffold commands above.
2. Prove the pending template remains compatible with every supported released
   v0.1.x CLI. Today that includes `create-forge` v0.1.0.
3. Merge the `forge-template` pull request first, then publish its compatible
   template tag.
4. Rerun `uv run pytest -m network` on the `create-forge` branch so its registry
   is checked against the tag users will resolve.
5. Merge and, when needed, release the compatible `create-forge` change.

Do not publish registry metadata before the corresponding template behavior is
available from the latest compatible tag. Conversely, every new template tag
must continue to work with supported v0.1.x CLI releases because those clients
also resolve the latest tag.

There is no safe one-step v0.1.x release order for a removal, rename, narrowed
choice domain, or other change that invalidates an existing CLI's inputs. Stage
such work through a backward-compatible transition or defer it to the public
engine cutover, where bounded package ranges and ProjectSpec protocol checks
keep older clients on their supported line. The future engine-first release
sequence remains defined by the [integration contract](integration-contract.md).

## Finish the change

Wait for each repository's required aggregate check, squash-merge with a
Conventional Commit subject, delete both feature branches, and fast-forward
both local `main` branches. A cross-repository issue is complete only after
both pull requests and their required checks are finished.
