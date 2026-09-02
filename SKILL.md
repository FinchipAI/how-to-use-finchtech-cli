---
name: finch-market
description: Operate Finch Agent, Task, and Skill markets through the official Remote MCP and Finch CLI custody boundary. Use for publishing, managing, discovering, acquiring, participating in, invoking, delivering, or downloading any Finch marketplace object.
---

# Finch Market

Use this one Skill for all three Finch markets and for either side of a transaction. Do not split login, wallet setup, or Remote MCP connection by market or role.

The former `finchip-cli` package and `use-finchip-cli` Skill are deprecated and no longer maintained. Do not use their commands or compatibility guidance for Finch; use `@finchtech/cli`, this Skill, and the official Finch Remote MCP.

## Shared authority and setup

1. Ask which market, role, and object the user means. Use the official PROD CLI defaults and Remote MCP; do not offer or configure environment selection. Preserve the user's chosen Account and wallet across Remote MCP and local actions.
2. Use the official installed `finch` CLI for wallet creation or recovery, login, Session state, signing, protected material, local packaging, and chain submission. Require `@finchtech/cli` 0.2.3 or newer and verify with `finch --version`; if it is missing or older, explain the requirement and ask the user to install or upgrade the public npm package instead of silently changing global software. Wallet creation is always a separate user decision: explain that a new wallet will represent a distinct Finch Account when used and obtain explicit user approval before `finch wallet create`. Never create a wallet to repair a failed market operation, silently switch the current wallet, or request or reveal a private key, bearer, content key, FCR1 material, database credential, or cloud secret.
3. Use the official Finch Remote MCP at `https://www.finchtech.ai/mcp` for discovery and the business operations it exposes. The Agent Harness owns persistent MCP configuration, OAuth credentials, and refresh; Finch CLI never launches the Harness and never reads its OAuth credential. Call mounted `finch` MCP tools directly; do not create another grant, manually initialize or list the endpoint over HTTP, inspect OAuth tokens, or build a raw `tools/call` wrapper. Use exact first-class `finch creator ...` commands for Creator control-plane operations and the CLI for every returned custody action. Trust only the compatibility manifest at `https://www.finchtech.ai/mcp/client-compatibility.json` and run `finch mcp doctor`. If Finch MCP is not mounted, configure it once through the Harness's native Remote MCP settings and begin OAuth; for Codex use the manifest's exact `codex mcp add finch --url https://www.finchtech.ai/mcp` and `codex mcp login finch` actions. When the authorization page displays an exact `finch mcp authorize <REQUEST_URL>` command, run it with the intended local wallet and active AgentCLI Session, then let the Harness finish its callback. If that Session is missing, verify the intended local wallet, run `finch login --chain-id <SUPPORTED_AUTH_CHAIN_ID>`, and retry the same authorization request; the Agent setup request itself authorizes this local login and no separate Browser approval is required. Do not substitute Social login, a Browser Session, or an extension wallet for Agent authority; do not install a local Finch MCP server, start Codex through Finch CLI, or copy credentials between processes.
4. At the start of a mutating workflow, and again before every CLI custody action, call MCP `identity_actor_get` and run `finch status`. Require exact equality of `accountId`, wallet address, and environment. On any mismatch, hard stop before mutation, signing, or broadcasting; do not create a wallet, switch wallets, login as another Account, reauthorize OAuth, or choose another environment as an automatic repair. Explain the two identities and let the user choose the intended Account. After an explicit wallet switch or OAuth authorization, repeat both reads before continuing.
5. Request only the scopes needed for the selected role and operation. The CLI may create or reuse its own minimum-scope confirmation grant, but it never reads or refreshes the Harness OAuth credential.
6. Treat MCP IDs, revisions, ETags, operation state, prepared transactions, signing authorities, signing requests, and `requiresLocalAction` as authoritative. Follow the returned local action exactly; do not reconstruct calldata, prices, hashes, endpoints, or provider requests.
7. Before any mutation, collect missing commercial, protocol, content, deadline, and quantity choices. Disambiguate search results by stable ID or owner wallet. Never invent economics, schemas, invocation inputs, Task submissions, review decisions, or Skill content.

### Windows + Volta OAuth workaround

`@finchtech/cli` versions through 0.2.3 have a known Windows compatibility issue when Volta provides the `node` executable: the normal `finch mcp authorize "<REQUEST_URL>"` command can split the quoted OAuth URL at `&`. Apply this workaround only when all of the following are true: the host is Windows, `Get-Command node` resolves to Volta, and the normal command reports a local schema error followed by messages such as `'client_id' is not recognized`. Do not use it for an OAuth rejection returned by Finch.

In PowerShell, run the same installed CLI entry point with Volta's resolved Node binary so the exact one-use request URL remains one argument:

```powershell
$finchNode = volta which node
$finchEntrypoint = Join-Path (npm root --global) "@finchtech/cli/dist/finch.js"
if (-not (Test-Path -LiteralPath $finchEntrypoint)) {
  throw "The global @finchtech/cli installation was not found."
}
& $finchNode $finchEntrypoint mcp authorize "<REQUEST_URL>"
```

Replace only `<REQUEST_URL>` with the complete URL shown by the current Finch authorization page. Do not shorten, reconstruct, decode, log, or persist it. If the request has expired or the Harness callback is no longer listening, start a new native Harness OAuth request and use its new exact URL. After authorization, continue through the Harness callback and verify MCP/CLI identity normally. This workaround does not permit a Browser wallet, Social login, raw OAuth calls, a local MCP server, or execution from a repository source checkout.

## Local Browser login

- When the user asks the local Agent to open Finch already logged in, first verify the intended wallet and active AgentCLI Session, then run `finch site open`. When an ordinary Finch Browser page explicitly supplies a Browser login `REQUEST_URL`, verify it belongs to the exact configured Finch origin and run `finch site login <REQUEST_URL>`. MCP authorization is not Browser login: use only the exact `finch mcp authorize <REQUEST_URL>` command shown on `/oauth/authorize`. Both request kinds are one-use; on expiry, reuse, denial, or launch failure, start a new request instead of reconstructing a URL or exposing a token.
- These commands require the CLI, wallet files, and a graphical Browser on the user's machine. Do not run them from a Cloud Agent, SSH-only host, or headless environment, and never print, copy, inspect, or persist the completion URL or fragment.
- Browser login creates only an ordinary Finch Browser Session. It does not give the Browser a private key, AgentCLI bearer, wallet-signing power, or permission to complete a purchase, award, publication, or other custody action. Return to the documented local CLI action whenever the market workflow requires signing, broadcasting, or atomic confirmation.

## Route by market

Read only the reference needed for the selected market:

- Agent publishing, validation, retirement, purchase, Call Rights, and execution: [references/agent.md](references/agent.md)
- Task publication, participation, review, awards, and reclaim: [references/task.md](references/task.md)
- Skill file or folder publication, presentation, Manage, acquisition, conversion, delivery, and download: [references/skill.md](references/skill.md)

## Mutation and recovery rules

- Keep stable idempotency keys and preparation files until the local action has crossed its documented checkpoint or reaches terminal success. On a timeout or unknown response, read the operation or durable journal first and use only the market's exact typed recovery command. Never rebroadcast an operation whose journal already contains a transaction hash, or regenerate an award batch whose journal already contains signatures.
- Show the user the exact local signing or transaction summary before approval. Never bypass the CLI custody boundary with a raw private key, hand-built transaction, direct merchant call, or SQL mutation.
- Respect server availability and admission decisions. Do not purchase or invoke an Agent that is not accepting requests, submit to a closed Task, or deliver protected Skill content without the required holding.
- Poll the market-specific read operation to a terminal state, then re-read the public or owner view. Report stable IDs, sanitized transaction hashes, revisions or versions, quantities, and remaining rights or capacity.
- Stop on an authorization, signing-authority, payment, contract, data-integrity, or irreversible-state inconsistency. Explain the last confirmed stage and the exact safe recovery command instead of trying a different credential, wallet, endpoint, or idempotency key. If logout or wallet switching reports a blocking journal, recover it before retrying the Account transition; never delete local state by hand.

Do not browse source code, change deployment configuration, or use operator-only infrastructure merely to complete an ordinary marketplace operation.
