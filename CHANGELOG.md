# Changelog

All notable changes to Auto Retopo Bake will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.2.0] - 2026-10-16

### Changed

- Changed the default `Target Quads` value from `20000` to `30000`.
- Changed the internal AutoRemesher `--sharp-edge` value from `90.0` to `150.0`.

### Added

- Added persistent `Output Directory` storage in the add-on preferences.
- The Output Directory is automatically saved when changed.
- The saved Output Directory is restored after restarting Blender and when opening another `.blend` file.
- Added migration support for an Output Directory value already stored in an existing `.blend` file.

### Validation

- Verified the default Target Quads value is `30000` in Blender 5.2.0 LTS.
- Verified the AutoRemesher command receives `--sharp-edge 150.0`.
- Verified Output Directory persistence across multiple Blender restarts.
- Verified changing the Output Directory updates the saved preference without requiring a manual Preferences save.
- CLI version remains unchanged.

## [1.1.0] - 2026-10-08

### Changed

- Removed the duplicate GLB file-browser icon from the add-on panel.
- Updated Selected Objects mode so the original selected mesh is used directly as the High Poly bake source.
- Selected Objects mode no longer leaves additional `*_HP` objects in the scene.
- Temporary working duplicates used for Merge by Distance and AutoRemesher export are removed after processing.

### Added

- Added progress display for the 9 processing stages.
- Added current-object progress for Selected Objects batch processing.
- Added total elapsed-time display in `MM:SS` format.
- Added completion summaries for successful and partially failed batch runs.

### Validation

- Verified GLB File mode on Blender 5.2.0 LTS.
- Verified Selected Objects batch processing with multiple mesh objects.
- Verified non-mesh objects are ignored in batch mode.
- Verified original selected objects remain unchanged.
- Verified Diffuse and Normal baking after the Selected Objects workflow change.
- Verified English and Japanese Blender UI environments.

## [1.0.1] - 2026-10-02

### Fixed

- Removed direct dependencies on localized/default Blender node names such as `Principled BSDF`.
- Shader nodes are now identified using `bl_idname`, socket identifiers, and persistent purpose tags.
- Added automatic creation of required Principled BSDF, Material Output, and Normal Map nodes when missing.
- Improved compatibility with localized Blender interfaces and manually renamed shader nodes.

### Validation

- Verified English and Japanese Blender UI environments.
- Verified GLB File mode and Selected Objects batch mode.
- Verified materials with manually renamed shader nodes.
- Verified saved `.blend` files retain Diffuse and Normal texture connections after reload.

## [1.0.0] - 2026-10-02

### Added

- Initial Blender add-on release.
- GLB File mode.
- Selected Objects batch mode.
- AutoRemesher integration.
- Merge by Distance preprocessing.
- Smart UV generation.
- Diffuse / Base Color baking.
- Tangent Space Normal Map baking.
- Automatic and manual projection settings.
- Configurable target quad count.
- Configurable bake resolution.
- Automatic Low Poly material setup.
- Per-object error handling in batch mode.
- Windows and Linux support.
