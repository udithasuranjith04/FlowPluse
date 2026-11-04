# Privacy and retention

The application does not perform face recognition, plate OCR, person re-identification or individual profiling. Detected vehicle IDs are anonymous, short-lived identifiers scoped to a camera session. They cannot be used to link people or vehicles across cameras.

Raw frames, annotated JPEGs, track histories and time-series measurements are held in bounded process memory. The application does not save source videos or original frame images. SQLite stores event metadata, review labels, configuration and zone coordinates. Metadata is local, persists across restarts and currently has no automatic TTL; operators can delete their stopped application's `runtime/` directory to reset local history. Do not distribute a personal database.

`ROADPULSE_SAVE_EVIDENCE=false` is the default. When explicitly enabled, the evidence boundary accepts only track geometry, never the original frame. It renders a small **redacted schematic** of boxes on a blank background. This intentionally retains no camera pixels, faces, plates or background features. These schematics are not photographic proof. Encoding or writing failure prevents storage. File cleanup runs on startup and every 60 seconds even when inference is paused, and on evidence retrieval. Expired links return 404. The default TTL is 24 hours and can be shortened in settings.

Permission to display a stream is required even when storage is off. Original source pixels may be visible to the local operator in the transient video panel. Do not expose the local application as a public service. No event is automatically sent to a third party or emergency service.

The software uses system fonts and ships no analytics, external images, advertising or API telemetry. Runtime upstream contact is limited to the source that you explicitly configure; the optional model downloader is an explicit setup command. Source URLs stay in the backend environment and are never serialized into public API responses.

The real detector adapter sets Ultralytics offline mode, disables runtime dependency auto-installation and usage sync, directs its settings to ignored local `runtime/` storage, and explicitly disables prediction image/text/crop saving. The separate `make model` setup command is the deliberate network-enabled weights download. These adapter settings are implemented; real-package execution remains pending as recorded in the verification log.

If the filesystem prevents deleting expired evidence, retrieval still rejects it after expiry and Diagnostics shows a cleanup error. Cleanup retries on subsequent cycles; fix the local directory permissions to remove the expired file from disk.
