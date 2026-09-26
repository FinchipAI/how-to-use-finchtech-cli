# Native MCP setup

Use the section for the application the user is connecting. These are operational examples, not an allowlist. Check the installed client's help when its commands differ. Keep existing model/provider and unrelated MCP settings when editing configuration.

First verify `finch status`; create a wallet only with the user's explicit approval and log in with `finch login --chain-id <SUPPORTED_AUTH_CHAIN_ID>` if needed. Existing explicit approval in the conversation counts. Then follow the authorization fallbacks in SKILL.md in order. A command requiring interactive answers must stay in an interactive terminal; `finch mcp connect` captures a login command's output but does not answer its prompts.

## Codex

Adding an OAuth server can start authorization immediately. For a new entry, wrap that operation:

```sh
finch mcp connect -- codex mcp add finch --url https://www.finchtech.ai/mcp
```

For an existing entry needing authorization:

```sh
finch mcp connect -- codex mcp login finch --no-browser
```

Use a new Codex session to load newly configured MCP tools. `codex mcp list` showing OAuth does not verify a tool call.

## OpenCode

Merge this entry into the native OpenCode configuration:

```json
{"mcp":{"finch":{"type":"remote","url":"https://www.finchtech.ai/mcp","enabled":true}}}
```

```sh
finch mcp connect -- opencode mcp auth finch
```

Start a new OpenCode session if the current session has not loaded the server.

## OpenClaw

Register the authenticated Streamable HTTP server, then authorize it:

```sh
openclaw mcp add finch --url https://www.finchtech.ai/mcp --transport streamable-http --auth oauth --no-probe
finch mcp connect -- openclaw mcp login finch
```

`--no-probe` lets registration precede authorization. Verify through the connected agent afterward. Use native MCP commands rather than looking for a browser-extension login.

## Hermes

```sh
hermes mcp add finch --url https://www.finchtech.ai/mcp --auth oauth
```

This command is interactive: complete its configuration and tool-enablement prompts. For an existing entry, the native authorization command is `hermes mcp login finch --flow browser`; `device` is a different OAuth protocol. Try wrapping the native login with `finch mcp connect`. If it requires terminal input, keep the native command running in an interactive terminal and use the original URL with `finch mcp authorize --stdin` (fallback 2). Start a new Hermes session after saving the tools.

## Claude Code

```sh
claude mcp add --transport http --scope user finch https://www.finchtech.ai/mcp
finch mcp connect -- claude mcp login finch --no-browser
```

Finch is a remote HTTP server; no local Finch server executable is needed. Use a new Claude Code session to load its tools.

## Gemini CLI

```sh
gemini mcp add --transport http finch https://www.finchtech.ai/mcp
```

The native OAuth entry is `/mcp auth finch` inside an interactive Gemini CLI session. There is no equivalent standalone `gemini mcp login` command in the inspected version. Keep that session running and use its displayed authorization URL with fallback 2. If the agent cannot operate the interactive session or obtain the URL, report that boundary and use fallback 3; configuring another application would not connect Gemini.

## Goose

Use `goose configure` → Add Extension → Remote Extension (Streamable HTTP), with `https://www.finchtech.ai/mcp`. Authorize through the native extension connection. `goose mcp` runs bundled MCP servers; it is not a remote OAuth login command. If the native connection exposes an authorization URL, keep it running and use fallback 2. Otherwise use fallback 3. Do not replace native OAuth with a Finch bearer header.

## Verify the result

Call the current application's mounted `identity_actor_get` tool and compare `accountId`, wallet address, and environment with `finch status`. A fresh native session may be needed to load newly added tools; reuse its saved configuration and authorization. If only configuration or OAuth is complete, say so and identify what remains unverified. Report an actual client/protocol error instead of inventing an adapter or switching applications.

Command examples inspected on 2026-09-26: Codex 0.157.1, OpenCode 1.18.32, OpenClaw 2026.9.6, Hermes v2026.9.24, Claude Code 2.1.283, Gemini CLI 0.61.0, Goose 1.52.0. This records command surfaces, not a claim that every listed client has passed end-to-end verification.
