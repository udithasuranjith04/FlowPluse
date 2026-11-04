# Implementation decisions

- **Local-first, replay-first:** no lawful live source was provided. Ship explicit generated replay plus a real optional live detector adapter. No invented URLs, permissions or quality claims.
- **AGPL integration:** choose YOLO11n as a documented, optional CPU detector and license the project accordingly. Weights are explicitly downloaded and ignored by Git; no hidden first-start download.
- **Separate fixture detector:** geometric road drawings are not realistic pretrained-model inputs. A color detector runs on generated pixels to exercise the real downstream pipeline, with explicit labeling. This does not fulfill real-model validation on a permitted real clip; that remains a release gate.
- **Standard SQLite driver:** avoids an unnecessary ORM layer for two simple tables. Queries are parameterized, writes transaction-bound and access serialized.
- **Modest tracking baseline:** own class-aware, velocity-assisted spatial association, with clear limitations and tests. Evaluate a stronger tracker only using permitted representative clips.
- **Environment-only sources:** protects signed source URLs and prevents arbitrary remote URLs/paths entering through the browser API. Source metadata is shown read-only; editable UI settings focus on zones and thresholds. Restart after changing environment metadata.
- **Redacted schematics:** opt-in evidence is rebuilt from track geometry on a blank background. No raw frame crosses the storage boundary. This prioritizes privacy over visual evidence richness.
- **Candidate state in memory:** only active/resolved observations are durable. Human reviews are stored independently from worker lifecycle changes.
- **No hosted deployment:** a server with native video decoding and model weights is outside the free local guarantee. The frontend requires its local backend; static hosting alone would not be a complete product.

- **Frontend dependency patch:** ESLint 10 supports the installed TypeScript ESLint integration. A pinned `minimatch` 11.0.1 override addresses [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) in the development toolchain. Re-evaluate the override when upstream tooling adopts the patched major version; verify lint, tests and the production build before changing it.

- **Single OpenCV package:** use `opencv-python` consistently across replay and the optional Ultralytics extra. Installing both GUI and headless distributions would overlap the same `cv2` namespace. Linux CI supplies the native OpenGL/glib runtime libraries. Upstream [Ultralytics dependencies](https://github.com/ultralytics/ultralytics/blob/main/pyproject.toml) also exclude OpenCV 4.13.0.90; the project carries that exclusion.

- **Python 3.12 baseline:** the specification's Python 3.11+ recommendation permits selecting 3.12 as the minimum. Installed NumPy stubs use Python 3.12 syntax. Package metadata, setup, Ruff, mypy, version-manager selection and CI now agree on the 3.12 baseline; `make lint` selects the backend configuration explicitly. No manual mypy override is required.
