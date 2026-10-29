# Running with an existing local scene

This guide is for an owner who already has a separately reviewed JARVIS scene and assets. The public source checkout does not contain them, and there is no public scene download or automatic reconstruction step. Use the device-free README quick start if you only have this repository.

The previously checked application was TouchDesigner 2025.33230 on macOS. The voice environment used Python 3.12.2, faster-whisper 1.2.1, sounddevice 0.5.6, NumPy 2.5.4 and CTranslate2 4.8.3. A fresh install of the declared dependency ranges has not been verified. Tkinter is needed only for the optional control window. The current launcher, process lock and speech playback target macOS; this is not a validated Windows voice application.

## Required private files

The scene requires `toxes/MediaPipe.tox` and its matching tracking helpers, the identity runtime sprites, workspace assets, globe assets, feedback graphics and the cinematic background. The generic replacements and silence are sufficient in place of the removed personal portraits and audio. The globe and workspace modules still need the other sprites; they do not generate missing graphics automatically.

The checked helper path is `/project1/hand_tracking/helpers`. The hand adapter expects normalized `h1:`, `h0:` or `h2:` pinch midpoint coordinates, distance and an activity signal. Different plugin releases can change the network and channel layout. The exact installed MediaPipe release has not been matched to a public version, so installing the latest upstream release is not a verified replacement.

`tools/prepare_local_scene.py` can copy an existing reviewed release and install the maintained voice bridge and gesture callback. It requires an owner-supplied JSON manifest whose `reviewed` field is `true` and whose `files` object maps every copied project-relative filename to its SHA-256 digest. The manifest is an audit result, not a switch to bypass a review. It refuses changed files, unreviewed files and iCloud placeholders.

```sh
python tools/prepare_local_scene.py /path/to/reviewed-release /path/to/new-local-copy \
  --review-manifest /path/to/completed-review.json
```

Keep the new folder intact. The helper preserves a before-updates scene, updates the two maintained DATs, and refuses an existing destination. It is not a camera-disable tool. The NumPy renderers resolve their configured asset directories as filesystem paths, so relative values also require a suitable working directory. The reviewed private copy has the required files, but a fresh relocated editor launch has not been validated.

## Scene and voice communication

Opening a scene can activate its independent browser capture path even when the output uses a cinematic background. Do not open it for a device-free test. This preparation stage did not launch the editor or approve further hardware use.

In a separately approved scene session, the expected output is `/project1/gesture_hud/FINAL_OUTPUT`. The timeline must run for its frame callbacks to poll commands. Place `JARVIS_VOICE_V20` beside the `.toe` file and use the copied scene's voice folder for commands. The service writes there; the bridge reads `project.folder/JARVIS_VOICE_V20`. Using the source checkout's voice folder while running a different scene folder will not connect them.

```sh
cd /path/to/new-local-copy/JARVIS_VOICE_V20
python voice_service.py --text "Jarvis show Japan" --no-speak
```

Typed commands need no microphone, camera, model or voice dependency install. They still need a compatible, running scene for an actual visual action. Without its acknowledgement they remain explicitly unconfirmed. The automated suite checks this protocol with temporary files and a synthetic scene boundary without opening TouchDesigner.

## Optional microphone and camera use

These steps require a separate owner-approved hardware session. They were not performed during final preparation.

```sh
cd /path/to/new-local-copy/JARVIS_VOICE_V20
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python voice_service.py --activation panel --local-model-only --enable-microphone
```

The last command requires the `tiny.en` Whisper model to be cached already. Omitting `--local-model-only` permits downloading missing weights from Hugging Face. Capture begins only after clicking Speak, and Stop or the configured time limit ends it. Enter mode is available with `--activation enter`; the launcher forwards the same options and does not opt into capture automatically.

The camera is required for physical hand tracking, not for command matching, unit tests or typed input. Microphone capture is required for spoken recognition, not for typed commands or gesture logic. No personal recording or photograph is required to render the cleaned private interface. A later editor save may retain new operator samples, so treat each proposed scene export as a new privacy review.
