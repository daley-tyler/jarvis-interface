# Architecture notes

The application has two independent update loops. TouchDesigner owns rendering and gesture interaction. The voice process owns audio capture, speech recognition, and speech playback. I kept that boundary because recognition can take longer than a frame and should not stall the interface.

The maintained scene source is under `touchdesigner/`. These files were extracted from the installed DATs in the saved scene rather than chosen from the older installer experiments. `prepare_local_scene.py` updates only the voice bridge and main gesture callback. It preserves the remaining node network and runtime assets.

## Interaction priority

The globe controller gets the first opportunity to capture a pinch on its own controls. The workspace controller follows, then the central hologram controller, then the legacy card logic. Existing captures are retained until release or tracking loss. The identity guard restricts the legacy card behavior. The main hand reader rejects non-finite coordinates, inactive hands, and negative pinch distances. Separate close and release thresholds reduce repeated transitions when a measured pinch distance jitters near the boundary.

The renderer caches sprites after their first load. It still composites arrays on the CPU and uploads the output to a Script TOP. No sustained scene performance benchmark or comparative latency claim is available. The live camera reported 30 FPS while the scene requested 60; requesting a higher rate does not make the physical camera run faster.

## File protocol

Both processes use `JARVIS_VOICE_V20` beside the saved `.toe`. `voice_command.json` contains a sequence number, allowlisted action, canonical argument, and timestamp. The service uses atomic replacement and a single-process file lock. Sequence numbers advance even after a command file is removed, preventing a running bridge from getting stuck behind a reset counter.

The bridge polls on available timeline frames, at most ten times per second. It deliberately ignores a packet already present at initial attachment, rejects commands older than 15 seconds, and never evaluates arbitrary code or free-form text. A command has one action, and later actions interrupt the automatic country tour. Gesture capture also interrupts the tour.

`voice_ack.json` reports acceptance or failure for the matching sequence. Without a matching acknowledgement, the voice process says that the command is queued and unconfirmed. This single-slot transport is intended for one voice process and a local interactive scene, not multiple senders or a durable queue. A late command can still execute after the two-second acknowledgement wait, up to its expiry time.

`voice_status.json` carries listening, transcribing, speaking, and fixed error codes. Status older than 30 seconds stops holding ambient audio down after a process crash. The voice process clears its status during normal exit. Rendering must be running for polling and acknowledgement to occur.

## Activation choice

Microphone access requires the owner’s explicit `--enable-microphone` opt-in. With that opt-in, the maintained control is an explicit push-to-talk window with bounded capture. It uses standard-library Tkinter and does not require terminal focus or accessibility permission for a global hotkey. Enter mode remains available.

I have not enabled continuous listening. Reliable hands-free operation would need a dedicated wake detector or voice-activity gate, a maximum utterance duration, suppression during JARVIS speech, and measurements with background audio. Repeatedly running Whisper on room noise would add CPU work and false-trigger opportunities. A deliberate gesture or physical push-to-talk trigger could use the same voice worker later, after the existing capture path is validated on hardware.

Raw speech stays inside the voice process. The status writer discards its legacy text, response, and error-message arguments. The command writer validates both action and argument against a fixed set before persisting anything. The scene status DAT no longer copies heard text or replies, which prevents those fields being saved inside a `.toe`. The optional Ollama compatibility hook is inert.
