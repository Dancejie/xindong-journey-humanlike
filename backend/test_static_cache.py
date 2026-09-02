from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.app import app


class StaticDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_index_is_revalidated(self) -> None:
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-cache", response.headers.get("cache-control"))

    def test_media_is_cached_and_supports_range(self) -> None:
        response = self.client.get(
            "/media/video/E01-arrival-reveal.mp4",
            headers={"Range": "bytes=0-99"},
        )
        self.assertEqual(206, response.status_code)
        self.assertEqual(100, len(response.content))
        self.assertEqual(
            "public, max-age=604800, stale-while-revalidate=2592000",
            response.headers.get("cache-control"),
        )


if __name__ == "__main__":
    unittest.main()
