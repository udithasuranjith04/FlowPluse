"""List system devices without opening a capture session (optional FFmpeg)."""

import json

from app.local_camera import list_devices

if __name__ == "__main__":
    print(json.dumps(list_devices(), indent=2))
