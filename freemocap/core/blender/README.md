# Blender preparation contract

The normal workflow is **push the add-on changes, update/sync FreeMoCap's Python
dependency, run FreeMoCap**. Export does not depend on a GitHub Action, release,
package catalog, manually built ZIP, or manual Blender add-on installation.

## One builder, three callers

The add-on's Python distribution contains `_host_tools`, a standard-library package
builder plus its license and legacy loader template. Core loads the builder as a
file without importing the Blender add-on (which would require bpy). The repository
`tools/build_addon.py` command delegates to the same implementation for standalone
ZIPs. `_host_tools` is excluded from the generated Blender packages and their
runtime-source fingerprint. It is host tooling, not code that runs inside Blender.

- **Source mode:** core reads the source and builder from its installed Python
  dependency. It identifies the selected Blender's Python/platform and prepares
  the matching ZIP automatically.
- **Electron:** `freemocap.spec` bundles that dependency's source, host tools and
  assets as loose backend resources, alongside its expected identity. The frozen
  backend uses the same preparation function. Users need neither Git nor a
  separate Python environment, compiler, pip, or checkout.
- **Standalone Blender:** the tag/manual GitHub Action uses the same builder to
  produce downloadable ZIPs for users who install the Extension directly. This
  workflow is independent of FreeMoCap export.

First use downloads pinned, precompiled PyArrow/TOMLI wheels from PyPI if they are
not already cached. Downloads are hash-verified. Nothing is compiled or installed
into core's Python or Blender's global Python environment. Blender's Extension
installer installs declared wheels; legacy packages contain a private dependency
bundle. The core cache stores wheels, built ZIPs and profiles outside the app's
installation directory. Subsequent use works offline with cached dependencies.

The ZIP cache key includes source identity, host-builder contents and target
runtime. Checksums detect damaged cached ZIPs. A source or builder change selects
a new package. An application-supplied provenance record avoids running Git on
users' machines. An older dependency lacking the host builder produces a clear
update-required error. Current automatic runtime coverage is Windows x64 with
Blender 3.0, 3.6, 4.2, 4.5 and 5.2; other combinations fail explicitly.

## Installation and process boundary

`prepare_blender` reuses a verified matching normal-profile installation. Otherwise
it builds/reuses a ZIP and asks Blender to install it in a FreeMoCap-managed
profile. A fresh process verifies the installed identity and dependency readiness
before the profile is published for reuse. Export repeats readiness checks.
Export and the subsequently opened GUI use the same profile. Normal preferences
and independently managed Extensions are left intact.

Managed profiles are keyed by executable, Blender version and ZIP checksum.
Repairs create a new profile instead of replacing possibly loaded DLLs. OS-owned
file locks serialize builders/installers and release on process exit. Old profiles
are retained; automatic garbage collection is not implemented.

Blender subprocesses do not inherit core's Python paths or frozen library paths.
The Windows DLL search directory is cleared only while spawning Blender and then
restored. Linux child processes receive the original library path. This applies
to both background export and the Blender GUI.

## Optional developer overrides

`FREEMOCAP_BLENDER_PACKAGE_CATALOG` can explicitly select a catalog of prebuilt
local packages. It is not consulted during normal dependency-based preparation.
A development source hash can explicitly accept a different installed build;
source, dependency and API checks still apply. `FREEMOCAP_BLENDER_STORAGE` can
isolate caches/profiles for testing. These overrides are not normal setup steps.

## Validation

The logic suites cover integrity checks, profile selection, package caching,
process environments and frozen identity. The add-on suite verifies that host tools
never enter Blender ZIPs and that both package formats preserve runtime identity.

`test_blender_automatic_integration.py` uses a built Python wheel in a disposable
installed-distribution layout. Starting with empty Blender preferences and cached
binary wheels, it exports both prepared reference recordings through both Parquet
routes. Network requests are forbidden and no package catalog or development
fingerprint override is supplied. It verifies one generated ZIP/profile is reused
and normal preferences stay untouched.

`test_blender_frozen_integration.py` builds and relocates a real PyInstaller probe
with that same source/builder bundled as data. It builds the Blender ZIP at runtime
and exports both reference recordings offline. Enable with
`FREEMOCAP_RUN_FROZEN_TESTS=1`. Both real suites use `FREEMOCAP_BLENDER_EXE`,
`FREEMOCAP_TEST_ADDON_WHEEL`, `FREEMOCAP_TEST_WHEEL_CACHE`, and
`FREEMOCAP_PREPARED_DATA_ROOT`. This validates the frozen backend boundary, not a
full signed Electron installer or a fresh detection/post-hoc GUI run.
