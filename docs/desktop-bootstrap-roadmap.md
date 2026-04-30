# Desktop Bootstrap Roadmap

This file tracks the bootstrap launcher plan so the next phases are not lost after install/verify/repair lands.

## Current Phase

Implemented first:

- one-file bootstrap launcher build
- embedded managed payload built from the clean desktop release
- install / verify / repair for managed files
- launch of the extracted legacy desktop runtime from disk

Managed payload scope today:

- hidden internal runtime executable extracted next to the public launcher
- `app-runtime/` extracted next to the public launcher
- user data and logs stay outside managed payload and are preserved

## Existing Version/Release Scaffold

There is already version/update groundwork in:

- [backend/versioning.py](F:/AI/stream-sub-translator/backend/versioning.py)
- [backend/api/routes_version.py](F:/AI/stream-sub-translator/backend/api/routes_version.py)
- `updates` config section in [backend/config.py](F:/AI/stream-sub-translator/backend/config.py)

That scaffold should be reused for later live release sync instead of starting another parallel version system.

## Next Phase: Runtime Update

Preferred approach:

- use GitHub Releases, not direct `main` branch sync
- publish a signed or at least hashed runtime manifest asset
- publish runtime payload archives per release
- launcher compares local manifest vs release manifest
- launcher downloads only changed managed files or a staged patch bundle
- launcher verifies SHA256 before swap

Why not update from `main`:

- `main` can be ahead of release and temporarily inconsistent
- Git checkout / pull is not a stable end-user updater
- rollback is harder

## Final Phase: Launcher Self-Update

The public launcher exe should update separately from runtime files.

Preferred flow:

- launcher checks release metadata
- downloads `Stream Subtitle Translator.new.exe`
- launches a tiny helper or delayed replacement flow
- current launcher exits
- helper replaces old launcher exe
- helper launches the new launcher

Do not try to replace the running launcher exe in-place.

## Notes

- keep default local-first behavior
- keep remote mode explicit opt-in
- do not move user data into managed payload
- do not run Python directly from embedded onefile resources
