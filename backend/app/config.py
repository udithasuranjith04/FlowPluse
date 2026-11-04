from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.capabilities import capabilities


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROADPULSE_", env_file=".env", extra="ignore")
    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = "sqlite:///./runtime/roadpulse.db"
    camera_mode: str = "replay"
    camera_url: str = ""
    replay_path: str = ""
    camera_id: str = Field(default="configured", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    camera_name: str = "Authorized camera"
    camera_region: str = "Not specified"
    camera_provider: str = ""
    camera_source_page: str = ""
    camera_terms_url: str = ""
    camera_permission_notes: str = ""
    camera_permission_checked: str = ""
    camera_analysis_authorized: bool = False
    camera_redisplay_authorized: bool = False
    camera_allow_private: bool = False
    camera_owned: bool = False
    camera_allowed_hosts: str = ""
    local_camera_index: int = Field(default=0, ge=0, le=15)
    local_camera_authorized: bool = False
    target_fps: float = Field(default=2, ge=0.5, le=15)
    snapshot_interval_seconds: float = Field(default=15, ge=1, le=86400)
    # Explicit, reversible migration switch. The generated fixture always remains vehicle-based.
    detection_target: Literal["vehicle", "person"] = "person"
    model_name: str = "yolo11n.pt"
    model_path: str = "runtime/models/yolo11n.pt"
    device: str = "cpu"
    save_evidence: bool = False
    evidence_ttl_hours: float = Field(default=24, ge=0.01, le=168)
    evidence_dir: Path = Path("runtime/evidence")
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    autostart: bool = False
    digitraffic_enabled: bool = False
    digitraffic_user: str = Field(
        default="RoadPulse-AI/local-research", min_length=3, max_length=100
    )

    @field_validator("digitraffic_user")
    @classmethod
    def header_valid(cls, value: str) -> str:
        if not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Digitraffic application header must contain printable ASCII")
        return value

    @field_validator("camera_mode")
    @classmethod
    def mode_valid(cls, value: str) -> str:
        if value not in {"live", "replay", "snapshot"}:
            raise ValueError("Mode must be live, replay, or snapshot")
        return value

    @field_validator("host")
    @classmethod
    def local_host(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("RoadPulse must bind to localhost")
        return value

    @field_validator("camera_id")
    @classmethod
    def real_camera_id(cls, value: str) -> str:
        if value == "demo":
            raise ValueError("demo is reserved for the generated source")
        return value

    @field_validator("device")
    @classmethod
    def device_valid(cls, value: str) -> str:
        if value not in {"cpu", "mps"}:
            raise ValueError("Use cpu or experimental mps with CPU fallback")
        return value

    def source_issues(self) -> list[str]:
        """Local checks only: safe to expose, no URLs, paths, credentials or DNS calls."""
        if not (self.camera_url or self.replay_path) and self.camera_mode == "replay":
            return []
        issues = []
        if self.camera_mode == "replay":
            if not self.replay_path or not Path(self.replay_path).expanduser().is_file():
                issues.append(
                    "Replay file missing. Set an existing ROADPULSE_REPLAY_PATH "
                    "or clear it for synthetic demo."
                )
        elif not self.camera_url:
            issues.append(
                "Camera URL missing. Set ROADPULSE_CAMERA_URL or choose replay for synthetic demo."
            )
        if not Path(self.model_path).is_file():
            issues.append("YOLO weights missing. Run make model and check ROADPULSE_MODEL_PATH.")
        if not (self.camera_analysis_authorized and self.camera_redisplay_authorized):
            issues.append("Analysis and redisplay permission must both be recorded in .env.")
        if not self.camera_permission_notes.strip():
            issues.append("Record permission evidence in ROADPULSE_CAMERA_PERMISSION_NOTES.")
        try:
            checked = date.fromisoformat(self.camera_permission_checked)
            if checked > date.today():
                raise ValueError
        except ValueError:
            issues.append("Permission check date must be YYYY-MM-DD and not in the future.")
        if not all(x.strip() for x in (self.camera_name, self.camera_provider, self.camera_region)):
            issues.append("Set camera name, provider and region metadata.")
        if self.camera_mode != "replay":
            if not self.camera_allowed_hosts.strip():
                issues.append("Set the exact source hostname in ROADPULSE_CAMERA_ALLOWED_HOSTS.")
            if not self.camera_owned and (
                not safe_link(self.camera_source_page) or not safe_link(self.camera_terms_url)
            ):
                issues.append("Record official source-page and applicable terms HTTP(S) links.")
        return issues

    @property
    def db_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only local SQLite is supported")
        return Path(self.database_url.removeprefix("sqlite:///"))

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    def cameras(self) -> list[dict]:
        cameras: list[dict] = [
            {
                "id": "demo",
                "name": "Synthetic boulevard",
                "region": "Local simulation",
                "mode": "REPLAY",
                "source_type": "generated",
                "provider": "RoadPulse AI",
                "source_page": "",
                "terms_url": "",
                "url_redacted": None,
                "analysis_authorized": True,
                "redisplay_authorized": True,
                "permission_notes": "Generated geometry; no real camera. Fixture detector.",
                "permission_checked": "2026-10-31",
                "license_status": "Project-generated / AGPL-3.0",
                "enabled": True,
            }
        ]
        if self.camera_url or self.replay_path or self.camera_mode != "replay":
            issues = self.source_issues()
            cameras.append(
                {
                    "id": self.camera_id,
                    "name": self.camera_name,
                    "region": self.camera_region,
                    "mode": self.camera_mode.upper(),
                    "source_type": "file" if self.camera_mode == "replay" else self.camera_mode,
                    "provider": self.camera_provider,
                    "source_page": safe_link(self.camera_source_page),
                    "terms_url": safe_link(self.camera_terms_url),
                    "url_redacted": "[configured on server]",
                    "analysis_authorized": self.camera_analysis_authorized,
                    "redisplay_authorized": self.camera_redisplay_authorized,
                    "permission_notes": self.camera_permission_notes,
                    "permission_checked": self.camera_permission_checked,
                    "license_status": "Operator-controlled; recorded ownership permission"
                    if self.camera_owned
                    else "Operator supplied; verify provider terms",
                    "enabled": not issues,
                    "configuration_issues": issues,
                }
            )
        cameras.append(
            {
                "id": f"local-camera-{self.local_camera_index}",
                "name": f"Local live camera · device {self.local_camera_index}",
                "region": "This computer",
                "mode": "LIVE",
                "source_type": "local_camera",
                "provider": "Operator-controlled camera",
                "source_page": "",
                "terms_url": "",
                "analysis_authorized": self.local_camera_authorized,
                "redisplay_authorized": self.local_camera_authorized,
                "permission_notes": "Operator opt-in required; macOS camera permission required.",
                "permission_checked": "",
                "license_status": "Operator-controlled; no third-party footage grant",
                "enabled": self.local_camera_authorized and Path(self.model_path).is_file(),
                "configuration_issues": []
                if self.local_camera_authorized
                else [
                    "Use Local Live Camera and confirm ownership/permission "
                    "for local processing and display."
                ],
            }
        )
        for camera in cameras:
            camera["capabilities"] = capabilities(
                camera["source_type"],
                camera["analysis_authorized"] and camera["redisplay_authorized"],
            )
        return cameras


def safe_link(value: str) -> str:
    """Attribution links cannot contain credentials, query tokens or fragments."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return ""
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
