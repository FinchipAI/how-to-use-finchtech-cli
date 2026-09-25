# CLI login and native MCP setup

Finch CLI and the agent harness hold separate credentials for the same intended Account. The CLI owns the local wallet and AgentCLI Session. The harness owns Remote MCP OAuth, credential storage, refresh and tool discovery.

These examples explain client operation; they are not a Finch client allowlist. Other MCP clients follow the same protocol through their native Streamable HTTP and OAuth facilities. Check the client's own documentation when command syntax or configuration differs.

## Shared flow

1. **Establish the intended CLI identity.** Check `finch --version` (0.3.9+) and `finch status`. Install or upgrade when the user has authorized software setup. On a clean installation, create a wallet only if the user explicitly chose a new identity, or import their protected local file as described in the main Skill. Authorization already given in the task counts; never create a replacement wallet as recovery.
2. **Complete pure CLI login.** Use `finch login --help` to choose a supported authentication chain, then run `finch login --chain-id <CHAIN_ID>`. This is an off-chain signature and requires no funding. Read the resulting Account, wallet and environment with `finch status`.
3. **Configure native Remote MCP.** Add `https://www.finchtech.ai/mcp` in the current harness. Preserve its other settings and use its native scope controls; `account:read` is sufficient for identity verification. Inspect the actual requested scopes, since client defaults can differ from configured preferences. Do not rewrite OAuth URLs to change scope or treat an OAuth grant as permission for business actions.
4. **Complete the native authorization attempt.** Keep the native login process running while reading its current Finch authorization page and running the exact `finch mcp authorize <REQUEST_TOKEN>` command shown there. Use the intended CLI identity. Preserve opaque request values unchanged; never decode or reconstruct them. The CLI opens the completion URL in the default browser, which must be able to reach that client's callback listener. Wait for the client to report authentication success. CLI `authorized: true` alone is not proof that the harness saved credentials.
5. **Verify through the harness.** Reload its native MCP connection or start a fresh run with the same user/profile and configuration. Wait for tool discovery, then actually call mounted `identity_actor_get` and compare Account, wallet and environment with `finch status`. An empty MCP resource list does not establish that tools are missing. Check identity again after a restart when verifying credential persistence.

An agent with terminal control can operate a persistent native login session and complete the Finch command concurrently. If its current conversation cannot refresh tools, it can use a new run of its own harness to make the native identity call. A CLI-only check, HTTP probe or custom MCP wrapper does not verify the native connection.

This flow is separate from Finch Browser Session handoff. Do not use `finch site open` or `finch site login` for MCP setup. The current MCP completion path requires a working browser-to-callback route even though pure CLI login itself does not.

## Native client entry points

### OpenClaw

```sh
openclaw mcp set finch '{"url":"https://www.finchtech.ai/mcp","transport":"streamable-http","auth":"oauth","oauth":{"scope":"account:read"}}'
openclaw mcp login finch
```

Use the same OpenClaw state directory/profile for setup and agent execution. Reload MCP or start a fresh agent turn after authentication. See [OpenClaw MCP OAuth](https://docs.openclaw.ai/cli/mcp/transports).

### Hermes

Merge the following into the applicable Hermes configuration, preserving other settings:

```yaml
mcp_servers:
  finch:
    url: https://www.finchtech.ai/mcp
    auth: oauth
    oauth:
      scope: account:read
```

Run `hermes mcp login finch` in an interactive terminal session and complete the shared flow. Reload MCP or start a fresh conversation afterward. See [Hermes OAuth HTTP servers](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp#oauth-authenticated-http-servers).

### OpenCode

Merge this entry into the applicable OpenCode configuration:

```json
{
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

Run `opencode mcp auth finch`, then use `opencode mcp list` and a reloaded or fresh session to verify the connection. Keep the same working directory when using project configuration. See [OpenCode MCP setup](https://opencode.ai/docs/mcp-servers/).

### Codex

Merge this table into the applicable Codex configuration before starting authentication:

```toml
[mcp_servers.finch]
url = "https://www.finchtech.ai/mcp"
scopes = ["account:read"]
```

Run `codex mcp login finch --scopes account:read`, then start a fresh Codex run and wait for native MCP initialization. The alternative `codex mcp add finch --url https://www.finchtech.ai/mcp` route may immediately start OAuth; configuring first allows scope selection before login. See [Codex MCP setup and readiness controls](https://developers.openai.com/codex/mcp/).

### Gemini CLI

```sh
gemini mcp add --transport http --scope user finch https://www.finchtech.ai/mcp
```

In the interactive Gemini CLI session, run `/mcp auth finch`; this is a slash command, not a `gemini mcp auth` shell subcommand. For identity-only setup, its native OAuth configuration accepts `scopes: ["account:read"]`. Preserve the configured HTTP transport and other settings. Use `/mcp list` and `/mcp reload`, or a fresh run, to verify tool discovery. See [Gemini CLI MCP OAuth](https://geminicli.com/docs/tools/mcp-server/#managing-oauth-authentication).

## Incomplete setup

Report the last confirmed stage: CLI Session, native OAuth start, Finch authorization, callback, native credential save, tool discovery or actual identity call. `finch mcp doctor` covers CLI Session and discovery only.

If the native attempt has ended or expired, begin a fresh attempt and use its current request. Preserve the intended wallet, recovery state and credential ownership. Do not patch the client, replace its OAuth flow, populate credential files or write a custom transport to make setup appear successful. If the documented native flow still fails, report the concrete error and client version so the underlying implementation can be investigated.
