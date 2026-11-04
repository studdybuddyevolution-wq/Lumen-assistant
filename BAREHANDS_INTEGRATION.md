# Barehands integration for Lumen

Lumen can optionally control [Barehands](https://github.com/jaredrhod/barehands), the webcam-based hand-tracked board. Barehands remains a separate upstream checkout; this repository contains only Lumen's small local bridge.

## No paid APIs

The bridge does not call Gemini, OpenAI, Anthropic, or any other model/API. It sends requests only to \`127.0.0.1\` on the configured Barehands port. It uses Python's standard library and adds no Python package dependencies.

Barehands itself runs locally and uses the browser webcam. On the first page load it downloads its hand-tracking and 3D-rendering libraries/assets from public CDNs (MediaPipe and three.js), so an internet connection is needed initially. No paid API key is required by Barehands.

Important distinction: Lumen's existing Gemini Live conversation engine is separate and can still consume the quota/billing of the Gemini account already configured for Lumen. This integration does not change or call that engine.

## Install on Windows

From the Lumen repository root (\`C:\Mark-LVI-main\`):

\`\`\`powershell
git clone https://github.com/jaredrhod/barehands.git integrations\barehands
\`\`\`

The Barehands checkout is ignored by Lumen's \`.gitignore\` so its upstream files, runtime state, notes and media are not accidentally committed to the Lumen repository. Barehands is licensed separately under AGPL-3.0-or-later; retain its own LICENSE and notices, and review its terms before redistributing it or a modified combined build.

No \`barehands.json\` is required for a first run. Barehands supplies defaults. To customize its board name, port, notes folders, or media folder, copy \`integrations\barehands\barehands.json.example\` to \`integrations\barehands\barehands.json\` and edit that local copy.

If Barehands is installed somewhere else, set \`LUMEN_BAREHANDS_DIR\` to its absolute folder path before launching Lumen.

## Use it

Restart Lumen after adding the checkout so its action loader discovers \`barehands_control\`. In Lumen, ask it to use the tool:

- \`status\`: check whether the local Barehands server is running.
- \`start\`: start the local server (Windows uses upstream \`run.bat\`).
- \`open\`: open \`http://127.0.0.1:8794/stage.html\` in the default browser. Chrome is recommended; grant webcam permission.
- \`present\`: spotlight a text card.
- \`add_card\`: add a text card.
- \`add_image\`: stage a file already inside Barehands' configured media folder.
- \`board_state\`: read the last board snapshot.
- \`clear\` / \`reset\`: clear or reset the board scene.

Example request:

\`\`\`text
Start Barehands, open its board, then present a card titled "Lumen is online"
with the body "This board is being controlled locally by Lumen."
\`\`\`

For \`add_image\`, provide a relative path such as \`misc/logo.png\`. The bridge rejects absolute paths, parent-directory traversal, hidden paths, unsupported extensions, and files outside the configured media folder. It does not expose arbitrary notes folders or general filesystem access.

## Disable

Set \`LUMEN_BAREHANDS_DISABLED=1\` to disable the bridge action. Remove the variable or set it to \`0\` to re-enable it. If the checkout is absent, Lumen still starts normally; the action simply reports that Barehands is not installed.

## Upstream project

- Source: https://github.com/jaredrhod/barehands
- License: AGPL-3.0-or-later (see the upstream LICENSE file)
- Barehands documentation: https://github.com/jaredrhod/barehands#readme
