## Credits & License

This project uses **MARK 56 — JARVIS** by [FatihMakes](https://creativecommons.org/licenses/by-nc/4.0/legalcode).

Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode).

*Note: This code has been modified from the original.*

## Lumen Local engine (Qwen 3.5 4B)

Gemini Live remains the default. To switch the conversation to a fully local
speech/model/voice path, open **ENGINE & PROVIDERS**, choose
**LUMEN LOCAL · QWEN 3.5 4B**, then press **SAVE & APPLY**.

The profile uses:

- **Speech recognition:** local faster-whisper (Whisper `base`, CPU).
- **Language model:** Ollama at `127.0.0.1:11434`, model `qwen3.5:4b`.
- **Speech output:** local Piper, voice `en_US-lessac-medium`.
- **Tools:** the same Lumen action, plugin and confirmation-gate flow.

### One-time Windows setup

Install Ollama, then run:

```powershell
ollama pull qwen3.5:4b
```

In Lumen's active virtual environment, install the optional local audio packages:

```powershell
python -m pip install faster-whisper piper-tts
```

The first run downloads the Whisper model and Piper voice. The local profile
checks that Ollama is reachable and that the exact Qwen model is installed
before starting. A missing dependency is reported with a repair instruction;
Lumen Local does not silently fall back to Gemini.

### Switching while Lumen is running

After the microphone is awake, say or type:

- **“Switch to local”** or **“go offline”** — use local Whisper → Qwen 3.5 4B → Piper.
- **“Switch to Gemini”** or **“go online”** — return to the existing Gemini Live conversation.

Switching rebuilds the conversation session. It does not overwrite the saved
Gemini key or the custom **MY OWN SETUP** pipeline. Model-assisted side calls
also stay on local Qwen in Lumen Local mode. Gemini-grounded side searches are
not available in that mode; the normal Lumen web-search action remains separate.

The existing wake-word / manual wake controls are unchanged.
