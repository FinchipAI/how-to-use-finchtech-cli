# Agent Market

## Creator

Use scopes `agent_market:merchant:read`, `agent_market:merchant:write`, and `agent_market:operations:read`.

1. Decide whether Direct API and AgentOn are separate Agents or separate Versions, and execute each Version as an independent revision, evidence, operation, and signing chain.
2. Collect display metadata, HTTPS endpoint maps, methods, timeouts, test inputs, payment token, price, Call Right units, quantity and duration bounds, schemas, Artifact contracts, and AgentOn validation inputs.
3. For `direct_api_v1`, configure the Direct contract before runtime. Anonymous Direct has no credential setup. Authenticated Direct requires the MCP credential setup and returned `finch credentials fulfill` action before runtime references it.
4. For `agenton_v2`, create the credential setup first and follow the returned `finch credentials material-download` action into a protected path. Install FCR1 through the merchant's secret manager, then configure runtime, rail, and the required Offers. Map P1/P2/P3 to `conversation_turn`, `task`, and `generation`.
5. Run a real connection test for each Version. Require Direct health/preflight/invoke or all selected AgentOn modes; generation must complete its real Artifact upload. Do not seed evidence or weaken transport policy.
6. Create and approve one publication intent per Version, poll it to success, and re-read the active revision, publication generation, availability, and Offer IDs. Use a retirement intent for an Offer that should no longer accept new work; do not edit history.

### Creator CLI authority

Use `finch <topic> --help` when exact syntax is needed. Treat its returned `usage` as authoritative. Do not inspect the executable, installed package, bundle, source map, or package-manager store.

For a new anonymous Direct API Agent, create fresh UUID request IDs and use this exact public sequence:

```text
finch creator agent create --request-id <UUID> --from-file <agent.json>
finch creator direct-contract replace <VERSION_ID> --request-id <UUID> --expected-revision 0 --from-file <direct-contract.json>
finch creator runtime replace <VERSION_ID> --request-id <UUID> --expected-revision 0 --from-file <runtime.json>
finch creator preflight start <VERSION_ID> --request-id <UUID> --from-file <preflight.json>
finch creator preflight show <OPERATION_ID>
finch creator publish start <VERSION_ID> --request-id <UUID> --expected-revision 1 --from-file <publish.json>
finch intent show <SIGNING_REQUEST_ID>
finch intent approve <SIGNING_REQUEST_ID>
finch operation show <OPERATION_ID>
finch creator version show <VERSION_ID>
finch creator runtime show <VERSION_ID>
finch creator direct-contract show <VERSION_ID>
```

Poll only the same preflight or publication operation ID. Do not create a new operation because a read timed out. Use the revisions returned by create/replace calls instead of assuming `1` when updating an existing Version.

`agent.json`:

```json
{
  "integrationFamily": "direct_api_v1",
  "displayName": "<DISPLAY_NAME>",
  "description": "<DESCRIPTION>",
  "supportContact": "<SUPPORT_EMAIL_OR_URL>",
  "avatarUri": null
}
```

`runtime.json` for anonymous Direct API (the `testInput` value is JSON, not a JSON-encoded string):

```json
{
  "integrationFamily": "direct_api_v1",
  "invocationUrl": "https://<MERCHANT>/invoke",
  "healthUrl": "https://<MERCHANT>/health",
  "preflightUrl": "https://<MERCHANT>/preflight",
  "method": "POST",
  "timeoutSeconds": 30,
  "testInput": { "prompt": "connection-test" },
  "inputSchema": {
    "type": "object",
    "required": ["prompt"],
    "properties": { "prompt": { "type": "string" } },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["answer", "received"],
    "properties": {
      "answer": { "type": "string" },
      "received": { "type": "object" }
    },
    "additionalProperties": false
  },
  "credentialSetupId": null,
  "credentialHeaderName": null
}
```

`direct-contract.json` (replace the economics and schemas with user-approved values):

```json
{
  "serviceVersionRevision": 1,
  "paymentToken": "0x<PAYMENT_TOKEN>",
  "unitPriceAtomic": "<POSITIVE_INTEGER>",
  "callRightUnits": "<POSITIVE_INTEGER>",
  "maxDurationSeconds": 120,
  "inputSchema": {
    "type": "object",
    "required": ["prompt"],
    "properties": { "prompt": { "type": "string" } },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["answer", "received"],
    "properties": {
      "answer": { "type": "string" },
      "received": { "type": "object" }
    },
    "additionalProperties": false
  },
  "artifactContract": {
    "count": { "kind": "range", "minItems": 0, "maxItems": 0 },
    "allowedMediaTypes": ["text/plain"],
    "maxBytesPerItem": "1024",
    "maxTotalBytes": "1024"
  }
}
```

`preflight.json`:

```json
{
  "integrationFamily": "direct_api_v1",
  "versionRevision": 1,
  "runtimeRevision": 1,
  "contractRevision": 1
}
```

`publish.json`:

```json
{
  "expectedPublicationGeneration": "0",
  "retiredOffers": []
}
```

## Buyer

Use scopes `agent_market:discover`, `agent_market:buyer:read`, `agent_market:buyer:purchase`, `agent_market:buyer:invoke`, and `agent_market:operations:read` as needed.

1. Search and inspect the exact active Version. Direct is Version-scoped and has no Offer. AgentOn execution selects an Offer and its interaction mode, schema, bounds, and Artifact contract.
2. Group required units by `serviceVersionId`; purchases and Call Rights are Version-scoped, not Offer-scoped. Prepare the purchase through the mounted MCP tool. If it returns a signing request, inspect and approve that exact request before reading the prepared purchase transaction; then execute only the returned `finch` transaction or submission action for the same operation ID.
3. Require terminal purchase success, then call the exact mounted tool `agent_market_buyer_call_rights_list` with the purchased `versionId` before invoking. Do not infer Call Rights from the purchase response or search for a generic rights tool.
4. For Direct, create the invocation, preserve its `invocationId`, and poll only `agent_market_buyer_invocation_get` to its terminal result. Do not pass the returned invocation operation ID to generic `agent_market_operation_get` or `finch operation show`; those generic reads do not own Direct invocation execution. Pass `input` as the native JSON value required by the published `inputSchema`: for an object schema, send an object directly, never a JSON-encoded string. For AgentOn P1, continue an `input_required` invocation only with user-supplied content and read the returned AgentOn operation through `agent_market_operation_get`. For P2/P3, create and poll the task and its `agent_market_operation_get` operation; provide input or cancel only when the published contract permits it.
5. Verify the terminal invocation or task, returned output or Artifact metadata, consumed reservation, and remaining rights by calling `agent_market_buyer_call_rights_list` again. For a P3 Artifact, use its returned `artifactId` with `agent_market_buyer_artifact_download_base64` and verify non-empty decoded bytes plus the published SHA-256. Never call the merchant endpoint directly.

### Buyer custody commands

Create the purchase and invocation through Remote MCP. For purchase custody, execute only the exact local action returned by MCP. The supported public commands are:

```text
finch intent show <SIGNING_REQUEST_ID>
finch intent approve <SIGNING_REQUEST_ID>
finch purchase transaction <OPERATION_ID>
finch purchase submit <OPERATION_ID>
finch purchase recover-approval <OPERATION_ID> --transaction-hash <TX_HASH>
finch purchase confirm <OPERATION_ID> --transaction-hash <TX_HASH>
finch operation show <OPERATION_ID>
```

Do not request the prepared transaction before its signing request is authorized. Use recovery commands only when the same purchase operation's durable journal or authoritative public-chain receipt requires them. A successful `finch purchase submit` response with the required confirmations is authoritative; do not add a separate RPC or explorer receipt probe unless recovery evidence is actually required. After terminal purchase success, re-read Call Rights through `agent_market_buyer_call_rights_list`, invoke through the mounted Remote MCP with an input that satisfies the published schema, poll Direct or AgentOn P1 through `agent_market_buyer_invocation_get` by `invocationId`, and poll AgentOn P1/P2/P3 operations through `agent_market_operation_get` by `operationId`. Then verify terminal output or Artifact metadata, download a P3 Artifact through `agent_market_buyer_artifact_download_base64`, and re-read the exact rights decrement.
