# Licensing and attribution

Repository code and original generated fixtures: **AGPL-3.0-or-later**, see [LICENSE](../LICENSE). The generated replay is made of original geometry; it contains no third-party footage, actual people or identifiable vehicles. No model weights are committed.

Optional real inference uses **Ultralytics YOLO11n**, with COCO vehicle classes. Ultralytics offers an AGPL-3.0 option and a separate enterprise license. This project adopts an open-source AGPL-compatible distribution; do not describe the model integration as MIT or free of source-availability obligations. Review the [official license](https://www.ultralytics.com/license) and [YOLO11 documentation](https://docs.ultralytics.com/models/yolo11/) before redistribution or deployment. A third-party weight file must have its own provenance and terms checked; only load trusted local files.

Major runtime packages retain their own licenses: React, Vite, FastAPI, Recharts, Lucide and Pydantic use MIT licenses; NumPy uses BSD terms; OpenCV uses Apache-2.0 in current 4.x releases; Shapely uses BSD terms and its GEOS dependency carries LGPL terms; SQLite is public domain. Bundled native libraries and development dependencies have their own notices; inspect the installed distribution's notices before redistribution. This list is an attribution guide, not a complete legal audit or legal advice.

No stock photos, web fonts or camera clips are bundled. RoadPulse's tracker is its own spatial matcher, not a copied ByteTrack implementation. Camera availability does not grant rights; permission for analysis and browser display is an independent requirement.

## Fintraffic data

Official Fintraffic/Digitraffic open data is separately licensed under CC BY 4.0, not the repository's AGPL. Preserve provider attribution, the source/license links, applicable notices, and a statement that RoadPulse added YOLO overlays. See [provider terms](https://www.digitraffic.fi/en/terms-of-service/) and [the integration guide](DIGITRAFFIC.md). These data rights do not grant authorization for unrelated camera operators. No real camera image history or model weights are committed to the repository.
