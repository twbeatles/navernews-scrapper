# Tasks: GitHub Release Updates

- [x] T001 Add signed manifest verification in `core/update_manifest.py`
- [x] T002 Add verified staging and rollback installer in `core/update_installer.py`
- [x] T003 [US1] Add update discovery UI in `ui/main_window_update.py`
- [x] T004 [US2] Wire UI and helper startup handling in `ui/main_window.py`, `ui/main_window_support/ui_shell_support/setup.py`, and `news_scraper_pro.py`
- [x] T005 [US3] Add release manifest generator and instructions in `scripts/build_update_manifest.py` and `updates/README.md`
- [x] T006 Add signature-verification tests in `tests/test_update_manifest.py`
- [x] T007 [US2] Route update installation through the existing graceful shutdown lifecycle in `ui/main_window_update.py`
- [x] T008 [US2] Persist and display helper apply/rollback/failure results in `core/update_installer.py` and `ui/main_window_update.py`
- [x] T009 [US2] Clean stale staged/helper artifacts and make update threads shutdown-aware in `core/update_installer.py` and `ui/main_window_update.py`
- [x] T010 [P] Add installer, result, cleanup, malformed-manifest, and close-race tests in `tests/test_update_installer.py` and `tests/test_update_manifest.py`
- [x] T011 [US3] Synchronize release workflow and user recovery documentation in `README.md`, `claude.md`, and `updates/README.md`
- [x] T012 [US3] Register `NEWS_SCRAPER_UPDATE_PRIVATE_KEY_B64` as the repository GitHub Actions secret
- [x] T013 [US3] Automate signed GitHub Release publication in `.github/workflows/release.yml`
