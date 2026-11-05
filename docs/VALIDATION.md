# Validation record

Checked locally on 29 October 2026. All **49 unittest tests passed**, retaining the 43 previously passing cases, including the original 32 regression cases. Six final preparation checks exercise synthetic capture bounds, stop/overflow cleanup, push-to-talk wiring and the complete typed service-to-bridge acknowledgement path. The tests use synthetic values and temporary files. They exercise command matching, bridge acknowledgements, expiry, malformed packets, process locking, pinch hysteresis, tracking loss, transcript suppression, disabled capture, and reviewed-file copying.

The original builder kit's NumPy renderer smoke test passed at 960×540 for four panel reveal states. Python compilation and launcher shell syntax also passed. The [published GitHub Actions run](https://github.com/daley-tyler/jarvis-interface/actions/runs/40949517209) passed all 49 tests and Python compilation on the source release. Hosted checks use synthetic inputs and do not validate the excluded scene or physical devices.

## Scene and privacy checks

I rebuilt the reviewed local scenes with TouchDesigner's native command-line utilities, then extracted them again. Operator definitions and source survived the round trip. Saved speech fields, tracked geometry and numerical samples were cleared. This included serialized audio sample buffers, rather than only replacing the external audio files. Personal portrait assets were replaced with independently drawn geometric panels; the recording-derived ambience was replaced with silence. The local cleaned backup was checked against the original folder by file hashes.

These are structural checks. I did not launch the editor or activate a camera or microphone during privacy cleanup. Saving a future live session may serialize new operator state, so a new scene export needs another review. The full scene, upstream components and assets are excluded from this source-only repository.

## Earlier hardware evidence

Before the privacy restriction, the copied prototype opened in TouchDesigner 2025.33230. Its HUD network reported no errors or warnings, its hand adapter returned a valid sample, and a typed command received a matching scene acknowledgement. The camera and final output reported 1280×720 at 30 FPS after requesting 60 FPS. This was a smoke check, not a sustained performance benchmark or a complete physical gesture demonstration.

The cached `tiny.en` model loaded locally with int8 CPU inference and two threads. A synthetic silence array returned no text. No successful live microphone recording or spoken command demonstration was completed. An attempted synthetic file-decoding probe encountered a PyAV compatibility issue; the application uses in-memory arrays instead. The temporary probe file and camera screenshot were deleted during privacy cleanup. A camera-free cinematic screenshot remains outside Git for local review; no demonstration video was recorded.

The existing environment reported Python 3.12.2, faster-whisper 1.2.1, sounddevice 0.5.6, NumPy 2.5.4, and CTranslate2 4.8.3. A fresh dependency installation has not been validated.

## Remaining limitations

The real Tk push-to-talk window, physical microphone stop behavior, recognition accuracy, playback feedback, and full gesture workflows still need an owner-approved hardware session. Fake Tk/worker boundaries and a synthetic InputStream verify code paths without establishing real GUI responsiveness or device behavior. No new hardware permission or live test is part of this cleanup. Scene and asset redistribution rights remain open, and this source checkout alone cannot reproduce the visual application. No license has been assigned pending the provenance review.

## Final packaging checks

The cleaned development scene was reviewed statically: 1,558 operator definition files, nine literal project-relative file references and 55 explicitly enumerated renderer assets. Those enumerated files exist locally. This does not prove every dynamic expression or a relocated editor session will work. The external MediaPipe binary, embedded OpenPose component and remaining art have incomplete version/provenance evidence, so none was copied into the publication candidate.

The public release contains source, tests and Markdown only. The exact tree and every Git object, including historical objects, were checked for media, runtime state, private paths and credential patterns. Standalone typed commands were checked without a model or devices. No new HUD screenshot was captured and no hardware process was launched. See [distribution](DISTRIBUTION.md) for the decision and [local scene setup](LOCAL_SCENE.md) for the missing private requirements.
