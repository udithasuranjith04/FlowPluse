"""Mock records follow the verified official Caltrans schema, not a live media test."""

import pytest

from app.providers import CaltransProvider


def test_caltrans_mock_schema_keeps_permissions_false_and_viewer_separate():
    provider = CaltransProvider()
    assert provider.catalog_url(1).endswith("/d1/cctv/cctvStatusD01.json")
    result = provider.parse(
        {
            "data": [
                {
                    "cctv": {
                        "index": "1",
                        "inService": "true",
                        "location": {
                            "district": "1",
                            "locationName": "Mock road",
                            "county": "Mock county",
                        },
                        "imageData": {
                            "streamingVideoURL": "https://camera.example/view.htm",
                            "static": {
                                "currentImageURL": "https://camera.example/image.jpg",
                                "currentImageUpdateFrequency": "15",
                            },
                        },
                    }
                }
            ]
        }
    )[0]
    assert not result.analysis_authorized and not result.redisplay_authorized
    assert result.snapshot_interval_seconds == 900
    assert result.video_url == "" and result.viewer_url.endswith("view.htm")
    assert "https://camera.example" not in repr(result)


def test_caltrans_rejects_invalid_schema_and_district():
    provider = CaltransProvider()
    with pytest.raises(ValueError):
        provider.catalog_url(13)
    with pytest.raises(ValueError):
        provider.parse({"unexpected": []})
