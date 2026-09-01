# Skill Market

Source shape and content protection are independent choices. A Creator may publish one file or one directory using `plaintext`, `finchip_v2`, or `lit` when the selected deployment supports that mode. Never substitute a GitHub or arbitrary IPFS URL for a new local package.

## Chain identity

Every concrete Skill is identified by `(chainId, skillId[, version])`. PROD discovery may return Ethereum `1`, Optimism `10`, BNB Smart Chain `56`, Base `8453`, and Arbitrum `42161` records in one result set. Preserve the returned `chainId` through detail, delivery, purchase, conversion, publication/version preparation, Manage, confirmation, recovery, and every CLI local action. Never infer it from the CLI login profile, a contract address, or a previous result, and never retry a missing-chain request against Base: Ethereum/Optimism and BNB/Arbitrum intentionally reuse contract addresses.

The Remote MCP plan is the market-chain authority. Finch CLI selects the source-controlled deployment, chain definition, envelope tag, and default RPC for that exact plan chain. Use a process-local `FINCHTECH_RPC_URL_<chainId>` override only when the user or environment operator intentionally supplies another HTTPS RPC for the same chain; do not reuse one chain's RPC for another.

## Creator

Use `skill_market:discover` and `skill_market:creator:write`.

1. Collect a unique slug, name, protocol category, source path, file-or-directory source kind, content mode, license, price, maximum supply, usage limit, optional platform display category, and required public presentation. Do not guess economics or publish a repository root.
2. Prepare publication through MCP, call `identity_actor_get`, compare it with `finch status`, and hard stop if Account, wallet, or environment differs. Show the exact custody summary for approval, then run the returned `finch skill publish-submit` action. Packaging, filtering, deterministic ZIP creation, optional encryption, upload, key custody, and chain submission stay local.
3. Prepare a public cover upload through MCP and run `finch skill asset-upload`; then prepare presentation and run `finch skill presentation-submit`. Presentation may include bounded summary, description, tags, parameters, dependencies, capabilities, compatibility, repository and documentation links, support, release notes, and related public metadata.
4. Use Manage reads before changing anything. Manage supports platform display category, unit price, maximum supply, public presentation, public HTML documents, and a new file-or-directory version. Use the corresponding MCP preparation and returned `finch` action (`price-submit`, `supply-submit`, `presentation-submit`, or `version-submit`), repeating the MCP/CLI identity comparison before each custody action. Re-read chain, presentation, and document state after each change.
5. Preserve the protected local recovery journal until all multi-transaction publication or version stages settle. Resume only with `finch skill recover publication <FINGERPRINT>` using the non-secret 64-hex fingerprint printed by the CLI. Do not expose journal contents, rerun a broadcast stage, delete local state, or create a replacement Skill after an unknown outcome.

`plaintext` means the package is publicly downloadable without a holding or wallet proof. A zero-priced protected Skill is still protected and still requires acquisition before key release. `finchip_v2` and `lit` are distinct existing envelope modes; do not translate or invent cryptographic data between them.

### Public HTML documents

Manage Information, Instruction, Benchmark, and Showcase HTML through Remote MCP; no separate CLI upload command exists or is needed. Before changing documents, call `skill_market_manage_get` for the exact `(chainId, skillId)`. Preserve its complete `presentation` value and inspect the required `documents` summary, whose four kinds are each either an admitted-content summary or `null`. A temporary `SKILL_MANIFEST_UNAVAILABLE` means the public IPFS gateways have not completed the read; retry the same Manage request instead of treating every kind as absent.

Call `skill_market_presentation_prepare` with the same `chainId`, `skillId`, and complete current `presentation`, plus `documentUpdates` only when changing documents. The update is explicit by kind:

- Omit a kind to preserve it.
- Set a kind to `null` to delete that whole kind.
- Set a kind to `{ "html": "...", "assets": [...] }` to replace that whole kind, including its complete asset list. `assets` is required and may be empty; omitted assets are removed rather than preserved.

Each asset is `{ "filename": "style.css", "mediaType": "text/css", "contentBase64": "..." }`. Use a flat filename, canonical base64, and a media type matching both the extension and bytes. Do not embed remote URLs, active scripts, nested paths, or content that the public static-document policy rejects. HTML cannot be empty or whitespace-only.

The request must satisfy both the 3,000,000 decoded-byte content limit and the 4,000,000 serialized-arguments limit. Large HTML or assets that exceed the Remote MCP transport limit must be managed in the Finch browser; do not split one whole-kind replacement into partial calls or move the business rule into a local script.

Document preparation stores a content-addressed derived manifest and waits for the same public IPFS gateway path used by CLI 0.2.1. During gateway warm-up, `SKILL_MANIFEST_UNAVAILABLE` is recoverable: retry the exact same prepare payload after a short wait. Do not alter `presentation`, assets, or document intent between those retries. Other validation errors require fixing the request rather than retrying it unchanged.

After prepare succeeds, repeat the MCP/CLI identity check and run the returned plan unchanged with `finch skill presentation-submit --from-file <PLAN.json>`. The CLI locally retrieves the derived manifest, preserves all unmodified documents and versions, applies the prepared presentation, re-encodes `setSkillURI`, signs, and broadcasts. Re-read `skill_market_manage_get` and the public content routes after confirmation; a deleted document route must return `404`.

## Buyer

Use `skill_market:discover` and `skill_market:buyer:write` as needed.

1. Search or list, then inspect the exact Skill ID and version, owner, price, supply, content mode, package hash, presentation, and delivery terms.
2. Download `plaintext` content through the public delivery plan without purchasing. For protected content, prepare purchase through MCP, call `identity_actor_get`, require exact equality with `finch status`, show the transaction summary for approval, and run the exact `finch skill purchase-submit` action. The command validates `signingAuthority`, broadcasts once, checkpoints the transaction hash before waiting for a receipt, and confirms atomically.
3. Read delivery through MCP and run `finch skill download` to a new protected output file. Delivery packages use IPFS; pass the authoritative plan unchanged so the CLI verifies the immutable package hash before creating the file.
4. When moving an owned holding to a newer compatible version, prepare conversion through MCP, repeat the identity comparison, and run `finch skill convert-submit`; verify the old/new balances and download the selected version explicitly.

If purchase or conversion times out after broadcast, recover only with `finch skill recover intent <FINGERPRINT>`. Recovery verifies the recorded transaction's sender, recipient, calldata, and value before waiting and confirming; it never broadcasts again. A buyer-intent journal containing a transaction hash can only be recovered, never abandoned or deleted by hand. Do not print or inspect journal secrets; logout and wallet-switch errors expose only the kind, fingerprint, and public recovery command.

Skill catalog and holdings are chain-authoritative, while projected search may converge after a confirmed transaction. Never treat an older search projection as permission to override the current chain-authoritative detail.
