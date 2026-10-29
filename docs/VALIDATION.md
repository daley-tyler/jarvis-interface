# Validation record

Checked locally on 29 October 2026. All **43 unittest tests passed**, including the original 32 regression tests and 11 privacy checks. The tests use synthetic values and temporary files. They exercise command matching, bridge acknowledgements, expiry, malformed packets, process locking, pinch hysteresis, tracking loss, transcript suppression, disabled capture, and reviewed-file copying.

The original builder kit's NumPy renderer smoke test passed at 960×540 for four panel reveal states. Python compilation and launcher shell syntax also passed. A hosted Actions workflow is included, but no hosted run has occurred for JARVIS.

## Scene and privacy checks

I rebuilt the reviewed local scenes with TouchDesigner's native command-line utilities, then extracted them again. Operator definitions and source survived the round trip. Saved speech fields, tracked geometry and numerical samples were cleared. This included serialized audio sample buffers, rather than only replacing the external audio files. Personal portrait assets were replaced with independently drawn geometric panels; the recording-derived ambience was replaced with silence. The local cleaned backup was checked against the original folder by file hashes.

These are structural checks. I did not launch the editor or activate a camera or microphone during privacy cleanup. Saving a future live session may serialize new operator state, so a new scene export needs another review. The full scene, upstream components and assets are excluded from this source-only repository.

## Earlier hardware evidence

Before the privacy restriction, the copied prototype opened in TouchDesigner 2025.33230. Its HUD network reported no errors or warnings, its hand adapter returned a valid sample, and a typed command received a matching scene acknowledgement. The camera and final output reported 1280×720 at 30 FPS after requesting 60 FPS. This was a smoke check, not a sustained performance benchmark or a complete physical gesture demonstration.

The cached `tiny.en` model loaded locally with int8 CPU inference and two threads. A synthetic silence array returned no text. No successful live microphone recording or spoken command demonstration was completed. An attempted synthetic file-decoding probe encountered a PyAV compatibility issue; the application uses in-memory arrays instead. The temporary probe file and camera screenshot were deleted during privacy cleanup. A camera-free cinematic screenshot remains outside Git for local review; no demonstration video was recorded.

The existing environment reported Python 3.12.2, faster-whisper 1.2.1, sounddevice 0.5.6, NumPy 2.5.4, and CTranslate2 4.8.3. A fresh dependency installation has not been validated.

## Remaining limitations

The push-to-talk window, capture stop behavior, recognition accuracy, playback feedback, and full gesture workflows still need an owner-approved hardware session. No new hardware permission or live test is part of this cleanup. Scene and asset redistribution rights remain open, and this source checkout alone cannot reproduce the visual application. No license has been assigned pending the provenance review.
