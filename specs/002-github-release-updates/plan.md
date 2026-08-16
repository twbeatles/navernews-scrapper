# Implementation Plan: GitHub Release Updates

- Add an independently testable signed-manifest module and an isolated installer module.
- Add a main-window update mixin using worker threads and Qt signals for UI handoff.
- Reuse the frozen executable as a short-lived helper after the main process exits.
- Keep update staging under the existing runtime data directory; never update database or config files.
- Bundle the Ed25519 verification dependency and document the release signing command.
