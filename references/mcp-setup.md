# CLI login and native MCP setup

Use this reference when an agent needs its own Finch CLI Session and an authenticated native connection to `https://www.finchtech.ai/mcp`. These are two separate credentials for the same intended Account. The CLI owns wallet custody; the harness owns MCP OAuth and refresh.

The examples below describe client operation, not a Finch client allowlist. For another MCP client, use its native Streamable HTTP and OAuth setup and follow the same sequence. Check installed client help when syntax differs. A missing guide entry says nothing about whether a client can connect.

## Complete the shared sequence

1. **Prepare the intended CLI identity before starting OAuth.** Check `finch --version` (0.3.9+) and `finch status`. With installation authorization, use `pnpm add --global @finchtech/cli@0.3.9` or the user's package manager. On a clean installation, create a wallet only when the user explicitly chose a new identity (`finch wallet create`), or import their protected local file as described in the main Skill. Existing authorization in the task is sufficient. Never create a replacement wallet during recovery.
2. **Log in with that wallet.** Read `finch login --help` and use a supported authentication chain, for example `finch login --chain-id 56`. This signs an off-chain login challenge; it does not require funding or a chain transaction. Check `finch status` for the resulting Account, wallet and environment. `finch mcp doctor` can diagnose this stage but cannot verify harness OAuth.
3. **Configure Finch in the current harness's native MCP settings.** Preserve its other settings. Request the scopes needed for the task; `account:read` is enough for identity verification. Where available, set this in the native client's scope option. Inspect the scope the native authorization request actually presents: a client may select its own defaults. Never rewrite the authorization URL to change scope or treat a broader request as permission to perform business operations.
4. **Start native OAuth and keep that process running.** Use a persistent terminal session, a PTY, or a background terminal that survives individual shell calls. Do not block the only shell action until its timeout kills the login process. Use a second terminal action to complete authorization while the first waits. Clients that reject non-interactive OAuth need a real PTY; `tmux` is one way for a shell-capable agent to operate such a session without human input.
5. **Read this attempt's authorization page.** Take the current `https://www.finchtech.ai/oauth/authorize?...` URL emitted or opened by the native process. Read that public page through browser tools or an ordinary page fetch, extract the exact `finch mcp authorize <REQUEST_TOKEN>` command, and execute it unchanged in the same CLI identity context. Do not use an old browser tab or a request from a previous attempt. Do not decode the request token, write it into scripts or reports, implement OAuth yourself, or edit the harness's credential storage.
6. **Let the callback finish.** The CLI opens the completion URL in the default browser. That browser must reach the callback listener belonging to the still-running harness process. For a loopback callback, browser and listener need the same network context; on a remote machine, use its working browser or the client's documented remote callback arrangement. Wait for native login to report success before ending its terminal. CLI `authorized: true` alone does not establish that the harness received and saved credentials.
7. **Load the authenticated tools and verify identity.** Reload the native MCP connection or start a new run of the same harness with the same user, HOME/profile and configuration. Wait for tool discovery. Use native tool search when the client defers tools; an empty MCP resource list is not an empty tool list. Actually call mounted `identity_actor_get` and compare its Account, wallet and environment with `finch status`. Report CLI login, native OAuth and native identity call separately. After a restart, call it again to verify that native credentials persist.

If the current conversation cannot refresh its tool catalog, a shell-capable agent can start a fresh run of its own harness and give it only the identity-check task. Use the same profile and let that process load and call its native tools. Carry forward its real tool result; do not replace it with a direct HTTP call, a custom MCP adapter or a fabricated success message.

This OAuth callback is separate from Finch Browser Session handoff. `finch site open` and `finch site login` are not part of this flow. Their local-user-browser restrictions do not prohibit CLI/MCP login on a remote machine with a working callback path.

## OpenClaw

Example syntax checked against OpenClaw 2026.9.6:

```sh
openclaw mcp set finch '{"url":"https://www.finchtech.ai/mcp","transport":"streamable-http","auth":"oauth","oauth":{"scope":"account:read"}}'
openclaw mcp login finch
```

Keep `login` running while doing steps 5–6. Use the same OpenClaw state directory/profile for setup and agent execution. After authentication, reload MCP or start a fresh agent turn; native tools commonly have names such as `finch__identity_actor_get`. The saved-server registry and a live tool call establish different stages. See [OpenClaw native MCP OAuth](https://docs.openclaw.ai/cli/mcp/transports).

## Hermes

For Hermes 0.21.5, merge this non-secret configuration into `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  finch:
    url: https://www.finchtech.ai/mcp
    auth: oauth
    oauth:
      scope: account:read
```

Run `hermes mcp login finch` in a persistent PTY. Complete the shared flow in another terminal action. Configuration editing avoids the interactive prompts in `hermes mcp add`; it does not supply credentials. Reload MCP or start a new Hermes conversation after native login succeeds, then call `mcp__finch__identity_actor_get` when mounted. See [Hermes OAuth HTTP servers](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp#oauth-authenticated-http-servers).

If authorization succeeds but native login times out, check the callback and client error before retrying. A callback-listener hang was observed with 0.21.5 on Linux; this observation is not a protocol incompatibility or a requirement for other versions. Increasing a timeout cannot repair a hung listener. Record the installed version and last confirmed stage rather than patching the harness or inserting tokens to claim success.

## OpenCode

For OpenCode 1.18.32, merge the following into the applicable `opencode.json` (preserving provider and other settings):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "finch": {
      "type": "remote",
      "url": "https://www.finchtech.ai/mcp",
      "enabled": true,
      "oauth": { "scope": "account:read" }
    }
  }
}
```

Run `opencode mcp auth finch` in a persistent terminal, then complete steps 5–6 concurrently. Check `opencode mcp list`; use a fresh `opencode run` or reload the interactive session to call the mounted identity tool. Keep the same working directory when using project configuration. Newer configuration schemas may differ; consult installed help and the [OpenCode MCP guide](https://opencode.ai/docs/mcp-servers/).

## Codex

```sh
codex mcp add finch --url https://www.finchtech.ai/mcp
codex mcp login finch --scopes account:read
```

After OAuth completes, use the existing `[mcp_servers.finch]` table in `~/.codex/config.toml`. For a task that depends on Finch at startup, set `required = true`; optionally allow `startup_timeout_sec = 30` on a slower connection. These are Codex readiness controls, not Finch protocol requirements. Preserve other configuration.

Start a fresh Codex run after changing configuration. Wait for MCP initialization, discover deferred tools if needed, and call the native identity tool. Do not infer missing tools from `list_mcp_resources`. This recipe was checked against Codex CLI 0.156.1; see [Codex MCP configuration](https://developers.openai.com/codex/mcp/).

## Gemini CLI

```sh
gemini mcp add --transport http --scope user finch https://www.finchtech.ai/mcp
```

In Gemini CLI 0.61.0, native authentication is the **interactive slash command** `/mcp auth finch`, not a `gemini mcp auth` shell subcommand. A shell-capable agent can open `gemini` in a persistent PTY, wait for the input prompt and send that slash command, then complete the Finch command from another terminal action. Keep the interactive process alive until it reports authentication and tool reload.

For identity-only setup, merge `oauth: {"enabled": true, "scopes": ["account:read"]}` into `mcpServers.finch` in the applicable `settings.json` before starting authentication. Preserve the `httpUrl` and other settings. Use `/mcp list` and `/mcp reload` or a fresh Gemini run to load the identity tool. A headless prompt describing `/mcp auth` is not evidence that the native slash command executed. See [Gemini CLI MCP OAuth](https://geminicli.com/docs/tools/mcp-server/#managing-oauth-authentication).

## Recover from an incomplete attempt

- Confirm which stage failed: CLI Session, native OAuth initiation, Finch command, callback, native credential save, tool discovery or actual identity call.
- If the native process exited, the URL expired or the command was already consumed, terminate only that abandoned attempt and start one fresh native login. Use its new URL. Do not keep multiple competing login attempts for the same server.
- Preserve the intended identity, recovery journals and native credential ownership. Never copy CLI bearers into MCP settings, implement PKCE/token exchange, import internal OAuth classes, or populate token files as a workaround.
- If the native client still fails after a fresh attempt with a working callback path, report the concrete error and client version. A client defect is not fixed by declaring success after `doctor` or `authorize`.
