# Privacy behavior

I keep recognition in the separate Python voice process. Microphone capture requires `--enable-microphone` and a deliberate Speak or Enter action. Clips are bounded and held in memory. Audio is released after transcription, including on errors; no audio file is created. Tests do not access devices.

The file bridge stores only fixed action names and arguments, sequence numbers, timestamps, phase flags, and diagnostic codes. Raw speech, free-form replies and exception messages are discarded by the state writer. Unmatched speech is not logged or sent to a language model. The old Ollama hook returns no response even if enabled by legacy settings.

The maintained HUD code renders arrays in memory and does not export camera frames. MediaPipe runs through the existing local browser runtime and loopback transport. Dependency installation and missing model downloads contact package or model hosts; `--local-model-only` disables model downloading. I found no hosted recognition API in the maintained Python code. I have not completed a network audit of the upstream browser runtime.

The reviewed local project uses generic graphics and silence in place of personal media. Native TouchDesigner files can serialize tracking samples, audio buffers and DAT values when saved. A cleaned scene is not a permanent privacy guarantee for later editor sessions. Review each future scene export and keep recordings, runtime state, local scenes, archives and editor profiles outside Git.

The preparation tool requires an approved SHA-256 file manifest and refuses changed or unreviewed input. This repository contains source and synthetic tests only. It excludes the private scene, editor state, media and project backups. The cleanup makes no claim about cloud retention, filesystem snapshots or copies outside the inspected project locations.
