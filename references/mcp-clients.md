# Native MCP setup

## Runtime and wallet custody

Before a new connection, recovery after losing an execution environment, or reuse of a browser wallet, establish where the CLI will run and which account the Human intends to use. Explain the relevant choice in the Human's language, then follow the corresponding route. Read available host and storage information first; reuse choices the Human has already confirmed.

### A durable place to run the CLI

CLI-MCP needs a host that can execute Finch CLI and securely preserve its wallet and unfinished-operation records across conversations, process exits and restarts. The computer need not run continuously. A remote host is suitable when its protected state remains available or can be securely restored before the next action.

A plain web or mobile chat, a Remote MCP connector, and remembered conversation text do not by themselves provide that host. A disposable sandbox whose local files disappear after each run is unsuitable for creating or funding a wallet. An ephemeral process can use durable, protected storage, but establish that storage and recovery path before wallet setup. If the current chat can reach a suitable persistent Agent host, run the CLI there; a phone may be the interface to that host.

When no suitable host is available, explain the missing execution or storage capability and offer a persistent host or the browser workflow below. Preserve the original wallet identity when recovering an environment; a replacement wallet can mean a different Finch Account. Keep private keys, CLI state and recovery journals in protected storage, and let the native MCP client retain its own OAuth credentials.

### The Agent's wallet and budget

The recommended CLI-MCP account uses a dedicated wallet controlled by the Agent, separate from the Human's everyday wallet. Explain this before asking for the wallet choice. When a new wallet is appropriate, follow the explicit wallet-creation decision in [Shared authority and setup](../SKILL.md#shared-authority-and-setup); an existing Agent wallet can be reused.

The Human may allocate the Agent's spending budget by funding that dedicated wallet as needed. Separating the wallets limits the assets exposed to that Agent's wallet control. The Agent must continue protecting an empty wallet: its key also controls the Finch Account and its owned resources. A top-up supplies a budget; the Agent follows the Human's instructions and the market's approval rules for each business action.

During normal setup, the Agent requests the full advertised MCP business permissions so the Agent can operate its own account. Restricted permissions are an advanced choice when the Human asks for a narrower role; follow the existing [connection permission policy](../SKILL.md#login-and-mcp-connection). OAuth permissions, possession of the wallet, and the Human's approval of a specific action remain distinct.

### An existing MetaMask or other browser wallet

A wallet being connected on Finch's website does not connect that wallet to Finch CLI or authorize the Agent's MCP client. Browser extensions keep their signing keys in the browser wallet; CLI-MCP uses the wallet held by the CLI. Browser login and MCP authorization pages do not transfer that key.

For an Agent working in the Human's existing website account, prefer the browser-automation route below. Reusing the exact same exportable EOA in CLI-MCP is an additional path explicitly chosen by the Human: the Human exports that account's private key through the wallet's official interface into a protected local file on the CLI host, then the Agent uses the official `finch wallet use --file <PATH>` import. Obtain the Human's explicit choice before moving the key. Keep the key out of chat, screenshots and command arguments, and follow [Wallet bootstrap and CLI health](../SKILL.md#wallet-bootstrap-and-cli-health) for existing state and account switching.

Explain why importing the Human's everyday wallet is discouraged: exporting and moving its key creates another custody location and gives the Agent control of that wallet's existing assets. Recommend the dedicated Agent wallet and a budget allocated by the Human instead. An account visible in an extension is not necessarily an exportable EOA; hardware, smart-contract and other non-exportable accounts need their supported workflow. Never treat an unsupported import as permission to replace the intended account.

### Choose who is acting in which account

| Intended use | Route |
| --- | --- |
| Agent uses its dedicated Finch account | CLI on the durable host plus the current Agent client's native Remote MCP connection. |
| Agent acts in the Human's existing Finch account | The Agent's supported browser automation in the Human's logged-in browser; retain the browser wallet's normal signing and confirmation flow. |
| Human temporarily uses the Agent's Finch account on the website | The CLI's browser-login handoff, following [Local Browser login](../SKILL.md#local-browser-login). |

For browser automation, verify the intended website account and the requested action before continuing. A browser automation integration does not itself set up CLI custody or MCP authorization.

For handoff, follow the local-host requirement in [Local Browser login](../SKILL.md#local-browser-login): the Agent runs the CLI on the Human's machine with a graphical browser it can open. The Agent checks its intended account and wallet, then opens the one-use confirmation page through the documented CLI command. The Human confirms the displayed account and uses the resulting website session; wallet keys remain on the Agent host. Wallet-signing actions still follow the original CLI custody flow. After temporary use, the Human signs out of the website to end that Web session; this does not disconnect the Agent's CLI-MCP connection. Report a cloud-host, headless-host or browser-opening limitation instead of copying the secret completion URL elsewhere.

## Connect the current client

Use the section for the application the Human is connecting after the runtime and wallet route above is established. These are operational examples, not an allowlist. Check the installed client's help when its commands differ. Keep existing model/provider and unrelated MCP settings when editing configuration.

First verify `finch status`; create a wallet only with the user's explicit approval and log in with `finch login --chain-id <SUPPORTED_AUTH_CHAIN_ID>` if needed. Existing explicit approval in the conversation counts. Then follow the authorization fallbacks in SKILL.md in order. A command requiring interactive answers must stay in an interactive terminal; `finch mcp connect` captures a login command's output but does not answer its prompts.

Before using an add/login command below, apply the [connection permission policy](../SKILL.md#login-and-mcp-connection) through the installed client's native OAuth scope options. These examples select the server and transport; use client help/settings to supply the selected permissions for both registration and authorization rather than inventing flags. Keep the resulting authorization URL unchanged when passing it to Finch CLI.

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
```

If `finch mcp connect -- claude mcp login finch` requires a terminal, use fallback 2: run `claude mcp login finch` in an interactive terminal, keep it running, and send its original authorization URL to `finch mcp authorize --stdin`. Its loopback listener accepts the callback. Finch is a remote HTTP server; no local Finch server executable is needed. Use a new Claude Code session to load its tools.

## Gemini CLI

```sh
gemini mcp add --transport http finch https://www.finchtech.ai/mcp
```

The native OAuth entry is `/mcp auth finch` inside an interactive Gemini CLI session. Use this entry when the installed client has no standalone OAuth login command. Keep that session running and use its displayed authorization URL with fallback 2. If the agent cannot operate the interactive session or obtain the URL, report that boundary and use fallback 3; configuring another application would not connect Gemini.

## Goose

Merge a named extension into Goose's native `~/.config/goose/config.yaml`:

```yaml
extensions:
  finch:
    enabled: true
    type: streamable_http
    name: finch
    uri: https://www.finchtech.ai/mcp
```

Alternatively use `goose configure` → Add Extension → Remote Extension (Streamable HTTP). Authorize the saved `finch` extension in a new native Goose session. An ad-hoc `--with-streamable-http-extension` connection can receive a different name and therefore a separate OAuth credential; it does not verify the saved extension. `goose mcp` runs bundled MCP servers, not a remote OAuth login command. Keep the native connection running and use its displayed authorization URL with fallback 2; otherwise use fallback 3. Do not replace native OAuth with a Finch bearer header.

## Verify the result

Verify the selected permission set as described in the [connection permission policy](../SKILL.md#login-and-mcp-connection). Call the current application's mounted `identity_actor_get` tool and compare `accountId`, wallet address, and environment with `finch status`. A fresh native session may be needed to load newly added tools; reuse its saved configuration and authorization. If only configuration or OAuth is complete, say so and identify what remains unverified. Report an actual client/protocol error instead of inventing an adapter or switching applications.

## Connection troubleshooting

### The client's connection page says required parameters are missing

Check the actual URL received by that page, including the parsed query values. Parameter names being present does not prove their contents survived generation or copying. If the client packages configuration in encoded data, decode it locally in memory according to that client's format and validate its JSON and required fields. Keep the URL and decoded session material private. A damaged value needs a correctly generated request from the client's native flow. Let that flow retain its matching PKCE/state and use the resulting authorization URL unchanged with Finch CLI.

### CLI approval succeeded but the Finch authorization page did not change

Finch's `/oauth/authorize` GET page is a static instruction page. CLI approval does not update it, and it has no completion or return-to-client button. Check the CLI's complete secret-safe result and the native login that started the request, then follow [Verify the result](#verify-the-result).

### A remote or headless host could not finish the HTTPS callback

For an HTTPS callback, Finch CLI opens the verified callback in the graphical browser on the machine running that CLI. `BROWSER_OPEN_FAILED` reports a browser-launch failure; a successful launch only confirms that the browser-opening command exited successfully. An HTTP 200 containing a generic login page also does not verify that the MCP client exchanged the code or connected. Check which machine/browser handled the callback and whether the original native login is still running. If the environment cannot provide the supported browser handoff, report that boundary before another approval. Use the documented native CLI/browser path, preserving the intended Account, wallet, PKCE and state; keep completion URLs and codes inside that path. If the original login has exited or its request expired, start a fresh complete native login. Repeated approvals or HTTP requests to the callback are not a substitute for this handoff.
