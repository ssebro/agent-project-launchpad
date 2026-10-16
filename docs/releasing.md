# Releasing

1. Run the full synthetic test suite, linter, and build on a clean checkout.
2. Confirm the native launch/resume flags against installed tool help. Record any
   compatibility changes. Never use customer transcripts as fixtures.
3. Build both wheel and sdist, install the wheel in a clean virtual environment,
   and check `--help`, `--version`, `list --json`, and `shell-init`.
4. Review the Git diff and archive contents for personal paths, session IDs,
   runtime handoffs, tokens, and generated data. Runtime state must stay outside
   the checkout and distribution archives.
5. Update the version in `pyproject.toml` and `src/agent_launchpad/__init__.py`,
   date the changelog entry, and commit the release. Ensure GitHub CI is green.
6. Create a `vX.Y.Z` annotated tag and push it. Create a GitHub release using that
   changelog entry, attaching the verified wheel and sdist.
7. PyPI publication is a separate future setup. Do not imply that the package can
   be installed by name from PyPI until publication is verified.

No release workflow receives a package-registry token. CI has read-only repository
permissions. Publishing a release is a deliberate maintainer action.
