from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend import custom_video as video


ENV = {
    "CUSTOM_VIDEO_API_KEY": "test-only-secret",
    "CUSTOM_VIDEO_MODEL": "seedance-2.0-mini",
    "CUSTOM_VIDEO_BASE_URL": "https://provider.example",
    "CUSTOM_VIDEO_UNIT_COST_CNY": "2.5",
    "CUSTOM_VIDEO_BUDGET_CNY": "20",
    "CUSTOM_VIDEO_DOWNLOAD_HOSTS": "media.example",
}
PHOTO = b"\xff\xd8\xff" + b"normalized-test-jpeg"


def approved_director() -> dict:
    digest = hashlib.sha256(PHOTO).hexdigest()
    director = video.build_director_card({"id": "custom-123", "identity": {"age": 27}}, digest)
    director["doNotSubmit"] = False
    director["approval"] = {"confirmed": True, "specHash": director["specHash"], "referenceHash": digest, "budgetRef": "reserved-job-123", "reviewer": "owner-123", "reviewedAt": "2026-09-09T12:00:00+08:00", "maxCostCny": 2.5}
    return director


def normal_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/models":
        return httpx.Response(200, json={"data": [{"id": "seedance-2.0-mini"}]})
    if request.url.path == "/api/v3/files/uploads":
        return httpx.Response(200, json={"id": "file-123"})
    if request.url.path == "/api/v3/files/file-123":
        return httpx.Response(200, json={"url": "https://media.example/photo.jpg?token=private"})
    if request.url.path == "/api/v3/contents/generations/tasks":
        return httpx.Response(200, json={"id": "task-123", "model": "seedance-2.0-mini"})
    return httpx.Response(404)


class VideoConfigurationTests(unittest.TestCase):
    def test_config_is_disabled_without_explicit_model_budget_and_hosts(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            status = video.config_status()
            self.assertFalse(status["available"])
            self.assertEqual({"durationSeconds": 10, "resolution": "480p", "modelLabel": "Seedance 2.0 Mini", "autoSubmit": True}, {key: status[key] for key in ("durationSeconds", "resolution", "modelLabel", "autoSubmit")})
        with patch.dict(os.environ, {**ENV, "CUSTOM_VIDEO_MODEL": "", "FUMIN_MODEL": "seedance-other"}, clear=True):
            self.assertFalse(video.config_status()["available"])
        for key in ("CUSTOM_VIDEO_UNIT_COST_CNY", "CUSTOM_VIDEO_BUDGET_CNY", "CUSTOM_VIDEO_DOWNLOAD_HOSTS"):
            with self.subTest(key=key), patch.dict(os.environ, {**ENV, key: ""}, clear=True):
                self.assertFalse(video.config_status()["available"])

    def test_budget_over_200_requires_separate_manual_approval(self) -> None:
        with patch.dict(os.environ, {**ENV, "CUSTOM_VIDEO_BUDGET_CNY": "201"}, clear=True), patch.object(video.shutil, "which", return_value="/test/ffprobe"):
            self.assertFalse(video.config_status()["available"])
            os.environ["CUSTOM_VIDEO_BUDGET_APPROVAL"] = "Explicit owner approval, additional cap CNY201"
            self.assertTrue(video.config_status()["available"])

    def test_only_exact_seedance_20_mini_model_enables_generation(self) -> None:
        for model in ("seedance-2.0", "seedance-2.0-fast", "seedance-2.5", "doubao-seedance-2-0-fast-260128", "doubao-seedance-2-0-260128", "seedance-test-exact", "seedance-2.0-mini-unknown", "fake-seedance-2.0-mini"):
            with self.subTest(model=model), patch.dict(os.environ, {**ENV, "CUSTOM_VIDEO_MODEL": model}, clear=True), patch.object(video.shutil, "which", return_value="/test/ffprobe"):
                self.assertFalse(video.config_status()["available"])
        with patch.dict(os.environ, ENV, clear=True), patch.object(video.shutil, "which", return_value="/test/ffprobe"):
            self.assertTrue(video.config_status()["available"])

    def test_nonfinite_prices_unsafe_host_and_missing_probe_fail_closed(self) -> None:
        for key, value in (("CUSTOM_VIDEO_UNIT_COST_CNY", "NaN"), ("CUSTOM_VIDEO_BUDGET_CNY", "Infinity"), ("CUSTOM_VIDEO_DOWNLOAD_HOSTS", "*.example"), ("CUSTOM_VIDEO_BASE_URL", "http://provider.example")):
            with self.subTest(key=key), patch.dict(os.environ, {**ENV, key: value}, clear=True):
                self.assertFalse(video.config_status()["available"])
        with patch.dict(os.environ, ENV, clear=True), patch.object(video.shutil, "which", return_value=None):
            self.assertFalse(video.config_status()["available"])

    def test_public_config_contains_no_model_key_or_url(self) -> None:
        with patch.dict(os.environ, ENV, clear=True), patch.object(video.shutil, "which", return_value="/test/ffprobe"):
            status = video.config_status()
        self.assertEqual({"available": True, "estimatedCostCny": 2.5, "durationSeconds": 10, "resolution": "480p", "modelLabel": "Seedance 2.0 Mini", "autoSubmit": True}, status)
        self.assertNotIn("test-only-secret", json.dumps(status))

    def test_director_does_not_transfer_profile_secrets_to_provider(self) -> None:
        with patch.dict(os.environ, ENV, clear=True):
            director = video.build_director_card({"id": "custom-123", "name": "PRIVATE_NAME", "preferences": "PRIVATE_PREFERENCE", "identity": {"age": 31, "name": "PRIVATE_NAME", "occupation": "PRIVATE_JOB"}}, hashlib.sha256(PHOTO).hexdigest())
        prompt = director["prompt"]
        for value in ("PRIVATE_NAME", "PRIVATE_PREFERENCE", "PRIVATE_JOB"):
            self.assertNotIn(value, prompt)
        self.assertIn("31岁", prompt)
        self.assertIn("10秒真人写实", prompt)
        self.assertIn("9–10秒", prompt)
        self.assertEqual(1, director["stateOut"]["stableTailSeconds"])
        self.assertTrue(director["doNotSubmit"])
        self.assertEqual(director["requestedModel"], director["usedModel"])
        with self.assertRaises(ValueError):
            video.build_director_card({"identity": {"age": 17}}, hashlib.sha256(PHOTO).hexdigest())

    def test_director_reads_existing_character_card_age_location(self) -> None:
        with patch.dict(os.environ, ENV, clear=True):
            director = video.build_director_card({"id": "custom-123", "identity": {"gender": "女性"}, "sourceProfile": {"facts": {"age": 34}}}, hashlib.sha256(PHOTO).hexdigest())
        self.assertIn("34岁", director["prompt"])


class VideoNetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(os.environ, ENV, clear=True)
        self.probe_patch = patch.object(video.shutil, "which", return_value="/test/ffprobe")
        self.env_patch.start()
        self.probe_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.probe_patch.stop)

    async def test_submit_exact_model_reference_and_specs_only_once(self) -> None:
        requests: list[httpx.Request] = []
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return normal_handler(request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task_id = await video.submit_video(PHOTO, approved_director(), client=client)
        self.assertEqual("task-123", task_id)
        self.assertEqual(4, len(requests))
        self.assertEqual("/v1/models", requests[0].url.path)
        self.assertIn(b'filename="identity.jpg"', requests[1].content)
        payload = json.loads(requests[-1].content)
        self.assertEqual("seedance-2.0-mini", payload["model"])
        self.assertEqual({"generate_audio": False, "ratio": "9:16", "duration": 10, "resolution": "480p", "watermark": False}, {k: payload[k] for k in ("generate_audio", "ratio", "duration", "resolution", "watermark")})
        self.assertEqual("reference_image", payload["content"][1]["role"])
        self.assertNotIn("approval", payload)
        self.assertNotIn("reviewer", json.dumps(payload))

    async def test_approval_hash_model_and_cost_changes_block_before_network(self) -> None:
        for field, value in (("doNotSubmit", True), ("prompt", "modified"), ("photoSha256", "0" * 64), ("requestedModel", "seedance-other")):
            director = approved_director()
            director[field] = value
            handler = AsyncMock()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(field=field), self.assertRaises(video.VideoProviderError):
                    await video.submit_video(PHOTO, director, client=client)
            handler.assert_not_called()

    async def test_legacy_five_second_director_cannot_create_new_task(self) -> None:
        director = approved_director()
        director["durationSeconds"] = 5
        director["specHash"] = video._canonical_hash(video._bound_spec(director))
        director["approval"]["specHash"] = director["specHash"]
        handler = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(video.VideoProviderError):
                await video.submit_video(PHOTO, director, client=client)
        handler.assert_not_called()

    async def test_native_ambience_setting_is_preserved_for_ten_seconds(self) -> None:
        os.environ["CUSTOM_VIDEO_GENERATE_AUDIO"] = "true"
        director = approved_director()
        self.assertTrue(director["generateAudio"])
        self.assertIn("仅轻柔海风", director["audioContract"])
        self.assertIn("不模仿或克隆声音", director["audioContract"])
        calls = []
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return normal_handler(request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await video.submit_video(PHOTO, director, client=client)
        payload = json.loads(calls[-1].content)
        self.assertTrue(payload["generate_audio"])
        self.assertEqual(10, payload["duration"])

    async def test_unavailable_model_never_uploads_or_falls_back(self) -> None:
        requests: list[httpx.Request] = []
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"data": [{"id": "seedance-some-other-model"}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(video.VideoProviderError):
                await video.submit_video(PHOTO, approved_director(), client=client)
        self.assertEqual(1, len(requests))

    async def test_wrong_version_or_size_blocks_before_photo_upload(self) -> None:
        for model in ("seedance-2.0", "seedance-2.0-fast", "seedance-2.5"):
            director = approved_director()
            os.environ["CUSTOM_VIDEO_MODEL"] = model
            handler = AsyncMock()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(model=model), self.assertRaises(video.VideoNotConfiguredError):
                    await video.submit_video(PHOTO, director, client=client)
            handler.assert_not_called()
            os.environ["CUSTOM_VIDEO_MODEL"] = ENV["CUSTOM_VIDEO_MODEL"]

    async def test_submit_timeout_is_uncertain_without_retry(self) -> None:
        submissions = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal submissions
            if request.url.path.endswith("generations/tasks"):
                submissions += 1
                raise httpx.ReadTimeout("secret upstream URL", request=request)
            return normal_handler(request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(video.VideoSubmissionUncertainError) as raised:
                await video.submit_video(PHOTO, approved_director(), client=client)
        self.assertEqual(1, submissions)
        self.assertNotIn("secret", str(raised.exception))

    async def test_429_5xx_and_missing_task_id_are_uncertain(self) -> None:
        for status in (429, 500, 503, 200):
            calls = []
            def handler(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                return httpx.Response(status, json={"error": "PRIVATE_PROVIDER_BODY"}) if request.url.path.endswith("generations/tasks") else normal_handler(request)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(status=status), self.assertRaises(video.VideoSubmissionUncertainError) as raised:
                    await video.submit_video(PHOTO, approved_director(), client=client)
            self.assertEqual(4, len(calls))
            self.assertNotIn("PRIVATE_PROVIDER_BODY", str(raised.exception))

    async def test_rejected_submission_and_upload_do_not_retry(self) -> None:
        for target, status in (("/api/v3/files/uploads", 500), ("/api/v3/contents/generations/tasks", 401)):
            calls = []
            def handler(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                return httpx.Response(status) if request.url.path == target else normal_handler(request)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(video.VideoProviderError) as raised:
                    await video.submit_video(PHOTO, approved_director(), client=client)
            self.assertNotIsInstance(raised.exception, video.VideoSubmissionUncertainError)
            self.assertEqual(target, calls[-1].url.path)

    async def test_poll_is_read_only_and_returns_only_sanitized_state(self) -> None:
        requests = []
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"status": "succeeded", "model": "seedance-2.0-mini", "content": {"video_url": "https://media.example/result.mp4?signature=private"}, "private_field": "not-returned"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await video.poll_video("task-123", client=client)
        self.assertEqual("succeeded", result["status"])
        self.assertEqual("GET", requests[0].method)
        self.assertEqual("seedance-2.0-mini", result["usedModel"])
        self.assertNotIn("private_field", result)

    async def test_existing_task_can_be_polled_after_budget_disabled_and_model_changed(self) -> None:
        os.environ["CUSTOM_VIDEO_BUDGET_CNY"] = "0"
        os.environ["CUSTOM_VIDEO_MODEL"] = "seedance-new-model"
        handler = lambda request: httpx.Response(200, json={"status": "processing", "model": "seedance-2.0"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await video.poll_video("task-123", expected_model="seedance-2.0", client=client)
        self.assertEqual("processing", result["status"])
        self.assertEqual("seedance-2.0", result["usedModel"])
        self.assertFalse(video.config_status()["available"])

    async def test_poll_permanent_result_errors_have_validation_class(self) -> None:
        for payload in (
            {"status": "succeeded", "model": "seedance-wrong"},
            {"status": "succeeded", "model": "seedance-2.0-mini"},
            {"status": "succeeded", "video_url": "https://not-approved.example/a.mp4"},
            {"status": "succeeded", "video_url": "http://media.example/a.mp4"},
        ):
            handler = lambda request: httpx.Response(200, json=payload)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(payload=payload), self.assertRaises(video.VideoCandidateValidationError):
                    await video.poll_video("task-123", client=client)
        async with httpx.AsyncClient(transport=httpx.MockTransport(normal_handler)) as client:
            with self.assertRaises(video.VideoCandidateValidationError):
                await video.poll_video("task-123", expected_model="invalid/model", client=client)

    async def test_poll_network_failure_remains_transient_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("temporary network error", request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(video.VideoProviderError) as raised:
                await video.poll_video("task-123", client=client)
        self.assertNotIsInstance(raised.exception, video.VideoCandidateValidationError)

    async def test_download_pins_validated_ip_and_uses_sni_without_credentials(self) -> None:
        requests = []
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"verified-video", headers={"content-type": "video/mp4"})
        with patch.object(video, "_resolve_public_address", AsyncMock(return_value="93.184.216.34")), patch.object(video, "_validate_candidate_bytes") as validate:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await video.download_candidate("https://media.example/result.mp4?signature=private", client=client)
        self.assertEqual(b"verified-video", result)
        request = requests[0]
        self.assertEqual("93.184.216.34", request.url.host)
        self.assertEqual("media.example", request.headers["host"])
        self.assertEqual("media.example", request.extensions["sni_hostname"])
        self.assertNotIn("authorization", request.headers)
        self.assertEqual(b"signature=private", request.url.query)
        validate.assert_called_once_with(b"verified-video", 10)

    async def test_download_passes_saved_five_second_spec_to_validation(self) -> None:
        handler = lambda request: httpx.Response(200, content=b"historical-five-second-video", headers={"content-type": "video/mp4"})
        with patch.object(video, "_resolve_public_address", AsyncMock(return_value="93.184.216.34")), patch.object(video, "_validate_candidate_bytes") as validate:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await video.download_candidate("https://media.example/result.mp4", expected_duration_seconds=5, client=client)
        self.assertEqual(b"historical-five-second-video", result)
        validate.assert_called_once_with(b"historical-five-second-video", 5)

    async def test_download_invalid_saved_duration_never_fetches(self) -> None:
        for duration in (0, 8, 15, True, "10", {"duration": 10}):
            handler = AsyncMock()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(duration=duration), self.assertRaises(video.VideoCandidateValidationError):
                    await video.download_candidate("https://media.example/result.mp4", expected_duration_seconds=duration, client=client)
            handler.assert_not_called()

    async def test_download_rejects_unsafe_urls_without_fetch(self) -> None:
        values = ("http://media.example/a", "https://evil.example/a", "https://media.example.evil.com/a", "https://user:pass@media.example/a", "https://media.example:8443/a", "https://127.0.0.1/a", "https://media.example/a#fragment")
        for url in values:
            handler = AsyncMock()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.subTest(url=url), self.assertRaises(video.VideoCandidateValidationError):
                    await video.download_candidate(url, client=client)
            handler.assert_not_called()

    async def test_dns_private_mixed_or_missing_addresses_are_rejected(self) -> None:
        loop = video.asyncio.get_running_loop()
        for addresses in (("127.0.0.1",), ("169.254.169.254",), ("::1",), ("93.184.216.34", "10.0.0.1"), ()):
            resolved = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)) for address in addresses]
            with patch.object(loop, "getaddrinfo", AsyncMock(return_value=resolved)):
                with self.subTest(addresses=addresses), self.assertRaises(video.VideoCandidateValidationError):
                    await video._resolve_public_address("media.example")

    async def test_download_rejects_redirect_bad_mime_and_oversized_content(self) -> None:
        for response in (httpx.Response(302, headers={"location": "https://media.example/next"}), httpx.Response(200, headers={"content-type": "text/html"}), httpx.Response(200, headers={"content-type": "video/mp4", "content-length": str(video.MAX_VIDEO_BYTES + 1)})):
            requests = []
            def handler(request: httpx.Request) -> httpx.Response:
                requests.append(request)
                return response
            with patch.object(video, "_resolve_public_address", AsyncMock(return_value="93.184.216.34")):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    with self.assertRaises(video.VideoProviderError):
                        await video.download_candidate("https://media.example/result.mp4", client=client)
            self.assertEqual(1, len(requests))

    async def test_download_rejects_unexpected_compression_and_stream_overrun(self) -> None:
        for headers, content in (({"content-type": "video/mp4", "content-encoding": "gzip"}, b""), ({"content-type": "video/mp4"}, b"x" * 33)):
            handler = lambda request: httpx.Response(200, headers=headers, content=content)
            with patch.object(video, "MAX_VIDEO_BYTES", 32), patch.object(video, "_resolve_public_address", AsyncMock(return_value="93.184.216.34")):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    with self.assertRaises(video.VideoProviderError):
                        await video.download_candidate("https://media.example/result.mp4", client=client)


class VideoTechnicalValidationTests(unittest.TestCase):
    @unittest.skipUnless(video.shutil.which("ffmpeg") and video.shutil.which("ffprobe"), "requires local ffmpeg and ffprobe")
    def test_actual_encoded_five_and_ten_second_files_match_saved_specs(self) -> None:
        # Disposable local solid-color clips exercise actual codec metadata;
        # they are not paid generation, likeness candidates, or retained media.
        for duration, dimensions in ((5, "480x848"), (10, "480x848"), (10, "496x864")):
            with self.subTest(duration=duration, dimensions=dimensions):
                generated = subprocess.run([
                    video.shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={dimensions}:r=10",
                    "-t", str(duration), "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-movflags", "+frag_keyframe+empty_moov", "-f", "mp4", "pipe:1",
                ], check=True, capture_output=True, timeout=30)
                video._validate_candidate_bytes(generated.stdout, duration)
                with self.assertRaises(video.VideoCandidateValidationError):
                    video._validate_candidate_bytes(generated.stdout, 5 if duration == 10 else 10)

    def test_wrong_signature_or_unavailable_tool_are_not_candidates(self) -> None:
        with self.assertRaises(video.VideoCandidateValidationError):
            video._validate_candidate_bytes(b"not an mp4")
        with patch.object(video.shutil, "which", return_value=None), self.assertRaises(video.VideoCandidateValidationError):
            video._validate_candidate_bytes(b"\x00\x00\x00\x18ftypisom")

    def test_ffprobe_specs_are_enforced_and_temporary_file_removed(self) -> None:
        metadata = {"format": {"duration": "10.0"}, "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 480, "height": 848}]}
        paths = []
        def fake_probe(command, **kwargs):
            paths.append(command[-1])
            self.assertTrue(os.path.isfile(command[-1]))
            return subprocess.CompletedProcess(command, 0, json.dumps(metadata), "")
        with patch.object(video.shutil, "which", return_value="/test/ffprobe"), patch.object(video.subprocess, "run", side_effect=fake_probe):
            video._validate_candidate_bytes(b"\x00\x00\x00\x18ftypisom")
            metadata["format"]["duration"] = "12"
            with self.assertRaises(video.VideoCandidateValidationError):
                video._validate_candidate_bytes(b"\x00\x00\x00\x18ftypisom")
        self.assertTrue(all(not os.path.exists(path) for path in paths))

    def test_saved_five_second_video_only_passes_its_own_spec(self) -> None:
        data = b"\x00\x00\x00\x18ftypisom"
        metadata = {"format": {"duration": "5.0"}, "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 480, "height": 848}]}
        probe = subprocess.CompletedProcess([], 0, json.dumps(metadata), "")
        with patch.object(video.shutil, "which", return_value="/test/ffprobe"), patch.object(video.subprocess, "run", return_value=probe):
            video._validate_candidate_bytes(data, 5)
            with self.assertRaises(video.VideoCandidateValidationError):
                video._validate_candidate_bytes(data)

    def test_ten_second_video_cannot_pass_as_saved_five_second_video(self) -> None:
        data = b"\x00\x00\x00\x18ftypisom"
        metadata = {"format": {"duration": "10.0"}, "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 480, "height": 848}]}
        probe = subprocess.CompletedProcess([], 0, json.dumps(metadata), "")
        with patch.object(video.shutil, "which", return_value="/test/ffprobe"), patch.object(video.subprocess, "run", return_value=probe):
            with self.assertRaises(video.VideoCandidateValidationError):
                video._validate_candidate_bytes(data, 5)

    def test_only_known_mini_padding_extends_width_past_480(self) -> None:
        data = b"\x00\x00\x00\x18ftypisom"
        for width, height, allowed in ((496, 864, True), (480, 848, True), (480, 864, True), (488, 848, False), (496, 848, False), (512, 896, False), (864, 496, False), (480, 560, False)):
            metadata = {"format": {"duration": "10.0"}, "streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": width, "height": height}]}
            probe = subprocess.CompletedProcess([], 0, json.dumps(metadata), "")
            with self.subTest(width=width, height=height), patch.object(video.shutil, "which", return_value="/test/ffprobe"), patch.object(video.subprocess, "run", return_value=probe):
                if allowed:
                    video._validate_candidate_bytes(data)
                else:
                    with self.assertRaises(video.VideoCandidateValidationError):
                        video._validate_candidate_bytes(data)


if __name__ == "__main__":
    unittest.main()
