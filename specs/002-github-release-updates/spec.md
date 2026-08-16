# Feature Specification: GitHub Release Updates

**Feature Branch**: `002-github-release-updates`
**Created**: 2026-08-16
**Status**: Implemented

## User Scenarios & Testing

### User Story 1 - Secure update discovery (Priority: P1)

A released-app user can check for an update and only sees versions authenticated
by the publisher and newer than the installed version.

**Acceptance Scenarios**:

1. Given a valid signed newer release manifest, the user is offered the update.
2. Given a changed, expired, unsigned, or non-HTTPS manifest, no executable is downloaded.
3. Given the installed version is current, the manual check reports that status.

### User Story 2 - Safe in-place installation (Priority: P1)

A released-app user can install a verified update without losing their local
news database, settings, backups, or cloud-sync state.

**Acceptance Scenarios**:

1. The update executable is fully downloaded and verified before replacement.
2. A separate process waits for the app to close, replaces only the executable,
   and retains a rollback copy.
3. If the replacement cannot start successfully, the previous executable is restored.

### User Story 3 - Publisher release workflow (Priority: P2)

A maintainer can produce a signed manifest for a GitHub Release without placing
the signing secret in source control or the distributed application.

## Requirements

- The app MUST retrieve update metadata only from the configured HTTPS channel.
- The app MUST verify an Ed25519 signature before trusting the version, URL,
  hash, size, or expiry contained in metadata.
- The app MUST verify the downloaded executable's size and SHA-256 hash before
  installation and once more immediately before replacement.
- The app MUST provide a GitHub release page fallback when update handling fails.
- The app MUST retain user runtime data outside the executable replacement path.
- The signing private key MUST not be committed or bundled.

## Success Criteria

- A valid newer release can be discovered and installed using no manual file replacement.
- Tampering with any signed manifest field prevents installation in 100% of tests.
- A failed post-replacement start check restores the previous executable before the helper exits.

## Assumptions

- Windows one-file builds are the initial supported update artifact.
- GitHub Releases host the executable and the default branch hosts `updates/latest.json`.
