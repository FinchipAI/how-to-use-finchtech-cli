# Skill Market

Source shape and content protection are independent choices. A Creator may publish one file or one directory using `plaintext`, `finchip_v2`, or `lit` when the selected deployment supports that mode. Never substitute a GitHub or arbitrary IPFS URL for a new local package.

## CLI 0.3.7 publication and delivery

Require CLI 0.3.7 or newer before these workflows. This version supports staged uploads, the 30 MiB package ceiling, and manifests with authorized external media. Older clients can reject those manifests or packages above their bundled limit. Updating this Skill alone does not update the CLI.

For a single local `.zip`, request a `file` source plan and pass the ZIP path to the returned `finch skill publish-submit` or `finch skill version-submit` action. The CLI expands it before filtering and primary-Markdown hashing. ZIP files inside a directory remain ordinary assets. Include `SKILL.md`, `README.md`, or one unambiguous root Markdown document with valid UTF-8. Imports accept stored/DEFLATE ZIPs up to 30 MiB compressed and expanded and at most 1024 entries; unsafe paths, symlinks, encrypted ZIPs, ZIP64, conflicts, and corrupt content are rejected. The final package must also fit 30 MiB including metadata and encryption overhead, so a source at the import ceiling may still be too large after packaging. Correct the source rather than bypassing validation.

New Skill identities use a SkillRoot commitment; historical identities retain ZIP-hash updates. Pass the user's optional summary unchanged during preparation; omission means an empty summary. Let the CLI calculate commitments and preserve its uploaded bytes and journal when resuming a publication.

Protected Finch-managed and Lit downloads use Oracle V2 grants sealed to a temporary local device key. Let `finch skill download` perform the request, verification, and local decryption; never request or expose a bare content key. The CLI verifies the SkillRoot and every file, or the historical plaintext ZIP hash, before writing an ordinary ZIP. It retains historical package support. Authorized recipients can still copy decrypted content.

## Search continuation and fresh publication signatures

Pass the returned `nextCursor` unchanged to `finch skill search --cursor`, retaining the same filters. Treat cursors as opaque strings, never integers. Restart from page one after a stale or filter-mismatched cursor; CLI 0.3.1 and Remote MCP advertise the required search capability automatically.

Finch-managed publication key requests carry a signed timestamp and are consumed once. If a request expires or was used, sign a fresh request through the updated CLI; never replay the old signature. Keep any existing transaction or publication journal and follow its typed recovery path. Lit publication is unchanged.

## Chain identity

Every concrete Skill is identified by `(chainId, skillId[, version])`. PROD discovery may return Ethereum `1`, Optimism `10`, BNB Smart Chain `56`, Base `8453`, and Arbitrum `42161` records in one result set. Preserve the returned `chainId` through detail, delivery, purchase, conversion, publication/version preparation, Manage, confirmation, recovery, and every CLI local action. Never infer it from the CLI login profile, a contract address, or a previous result, and never retry a missing-chain request against Base: Ethereum/Optimism and BNB/Arbitrum intentionally reuse contract addresses.

The Remote MCP plan is the market-chain authority. Finch CLI selects the source-controlled chain definition, contract authority, envelope tag, and public RPC for that exact plan chain. Do not set `FINCH_ENVIRONMENT`, `FINCHTECH_RPC_URL_<chainId>`, or `FINCH_RPC_URL_<chainId>`; installed CLI ignores them. The only optional endpoint override is the protected profile installed by the TEST Skill.

## Creator

Use `skill_market:discover` and `skill_market:creator:write`.

1. Collect a unique slug, name, protocol category, source path, file-or-directory source kind, optional summary (up to 500 characters), content mode, license, price, maximum supply, usage limit, optional platform display category, and required public presentation. Do not guess economics or publish a repository root.
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

An inline asset is `{ "filename": "style.css", "mediaType": "text/css", "contentBase64": "..." }`. An already uploaded detail asset may instead use `{ "filename": "image.png", "mediaType": "image/png", "storedURI": "<returned detail-storage locator>" }`; use exactly one representation. Preserve a real locator returned by a supported upload path; a local path, cover CID, or invented locator is not a detail upload. Use a flat filename and a media type matching the extension and actual bytes; the server reads and revalidates stored assets. HTML cannot be empty or whitespace-only.

The request must satisfy both the 3,000,000 inline decoded-byte content limit and the 4,000,000 serialized-arguments limit. Stored asset bytes do not spend the inline budget, but HTML plus all assets still must fit the 4 MiB per-document ceiling. If no supported upload path or existing locator is available, report that missing input instead of fabricating an upload command or routing blindly to the browser. Keep each whole-kind replacement complete.

External media requires an operator grant for both the publishing wallet and each exact HTTPS host. The grant covers `img`, `video`, `audio`, `source`, and CSS backgrounds; scripts, iframes, remote stylesheets/fonts, credentials in URLs, non-default ports and unapproved hosts remain refused. Create the Skill first, then add granted documents through presentation preparation; initial creation cannot name external hosts. Published documents retain their recorded hosts. Withdrawal blocks subsequent publication, including unchanged carried-forward documents, but does not disable media on an already published page. Request operator assistance for a grant; an ordinary market operation does not authorize editing Ops policy. The browser publish wizard still refuses external media and uses its existing multipart upload transport.

Document preparation stores a content-addressed derived manifest and waits for the same public IPFS gateway path used by CLI 0.2.1. During gateway warm-up, `SKILL_MANIFEST_UNAVAILABLE` is recoverable: retry the exact same prepare payload after a short wait. Do not alter `presentation`, assets, or document intent between those retries. Other validation errors require fixing the request rather than retrying it unchanged.

After prepare succeeds, repeat the MCP/CLI identity check and run the returned plan unchanged with `finch skill presentation-submit --from-file <PLAN.json>`. The CLI locally retrieves the derived manifest, preserves all unmodified documents and versions, applies the prepared presentation, re-encodes `setSkillURI`, signs, and broadcasts. Re-read `skill_market_manage_get` and the public content routes after confirmation; a deleted document route must return `404`.

## Buyer

Use `skill_market:discover` and `skill_market:buyer:write` as needed.

1. Search or list, then inspect the exact Skill ID and version, owner, price, supply, content mode, package hash, presentation, and delivery terms.
2. Download `plaintext` content through the public delivery plan without purchasing. For protected content, prepare purchase through MCP, call `identity_actor_get`, require exact equality with `finch status`, show the transaction summary for approval, and run the exact `finch skill purchase-submit` action. The command validates `signingAuthority`, broadcasts once, checkpoints the transaction hash before waiting for a receipt, and confirms atomically.
3. Read delivery through MCP and run `finch skill download` to a new protected output file. Delivery packages use IPFS; pass the authoritative plan unchanged so the CLI verifies the SkillRoot and every file, or the historical plaintext ZIP hash, before creating the file.
4. When moving an owned holding to a newer compatible version, prepare conversion through MCP, repeat the identity comparison, and run `finch skill convert-submit`; verify the old/new balances and download the selected version explicitly.

If purchase or conversion times out after broadcast, recover only with `finch skill recover intent <FINGERPRINT>`. Recovery verifies the recorded transaction's sender, recipient, calldata, and value before waiting and confirming; it never broadcasts again. A buyer-intent journal containing a transaction hash can only be recovered, never abandoned or deleted by hand. Do not print or inspect journal secrets; logout and wallet-switch errors expose only the kind, fingerprint, and public recovery command.

Skill catalog and holdings are chain-authoritative, while projected search may converge after a confirmed transaction. Never treat an older search projection as permission to override the current chain-authoritative detail.

## Publication diagnostics and recovery (CLI 0.3.7+)

Parse the JSON string in `error.state` for source diagnostics (`SKILL_SOURCE_SYMLINK_UNSUPPORTED`, `SKILL_SOURCE_UNREADABLE`) and final upload size (`SKILL_UPLOAD_SIZE_INVALID`, `actualBytes`, `maxBytes`). Paths are relative to the selected source. The CLI sends final multipart requests up to 4,000,000 bytes inline and automatically stages larger ones; the old near-limit warning and 4,500,000-byte local refusal no longer apply. Final packages are bounded at 30 MiB (31,457,280 bytes), covers at 5 MiB and manifests at 3 MiB. Upload and download share the package ceiling. Browser publishing still uses multipart and is not a 30 MiB upload path. Source ZIP import has its own compressed/expanded check; metadata, repacking and encryption may increase final size.

Staged upload failures can include `uploadTransport`, `uploadBytes`, `uploadObjectKind`, and `ticketReleased`. A failed release may retain a ticket: finish or release it through the supported client, or follow the returned expiry guidance. Sequential requests are limited to four outstanding tickets per wallet; tickets older than 24 hours are swept when that wallet next requests one. This is not a scheduled bucket-wide cleanup. Never print a signed upload URL or token.

For `SKILL_SOURCE_ZIP_INVALID`, inspect `zipReason`: `archive_too_large`, `expanded_content_too_large`, `utf8_flag_missing`, `filename_encoding_invalid`, or `invalid_archive`. Size errors include `actualBytes`, `maxBytes`, and `sizeBasis` (`archive` or `declared_expanded`); a safe relative entry path may be present. Non-ASCII ZIP filenames require valid UTF-8 bytes and bit 11 in the headers. Rebuild an invalid archive; these input failures use exit code 2 and `fix_request` before upload.

Skill operation and transport errors report HTTP status and available safe correlation IDs; intent diagnostics identify `/api/skills/intents`. `responseIssue` distinguishes transport/body/JSON/schema failures; `schemaIssues` is bounded and contains no response values. Diagnostics do not repair server-side failures or Harness OAuth. Use returned remote IDs for support; the publication fingerprint identifies a local journal, not a server trace. A download `output_destination` refusal concerns the requested output directory/file, not the wallet store; use a new file at the documented protected destination.

Publication failures report `phase`, `fingerprint`, `transactionHashes`, `submissionStatus`, `unconfirmedActions`, `resubmitSafe`, and `recoveryCommand`. Follow the returned `retryable` and `nextAction` together: a confirmed transaction with a pending projection is not proof that every required transaction finished. Re-read the Skill and use a supplied recovery command after comparing CLI/MCP identity. `not_attempted` describes this invocation, not previous attempts; `hash_known` is not a successful receipt by itself. Fingerprint-only recovery can reuse stored bytes. Never print journals or credentials.

Journal v6 records pending stages before submission. Unknown creation, version, or delivery-key outcomes still block blind resubmission; read the specific chain state named in the error and contact support when instructed. CLI 0.3.7 permits the URI stage of a legacy or marked journal to converge on the same URI through its typed recovery path. Known hashes are verified without rebroadcast. Keep journals and wallet/authorization state intact.

`presentation-submit` reports stages and observed hashes without creating a publication journal. When `resubmitSafe` is true, setting the same URI cannot apply twice; it does not guarantee that a reverted transaction or invalid plan will succeed. Re-read chain state first, and obey authorization/input/precondition errors before retrying. A version-moved or unreadable-manifest conflict requires a newly prepared plan. Never apply this same-plan guidance to creating a Skill or version.

## WebP covers and detail images (CLI 0.3.5+)

Use CLI 0.3.5 or newer when a valid WebP cover or packaged detail image was rejected as an unsupported image. This version detects image signatures from raw bytes, including WebP headers whose binary file-size field is not valid UTF-8. Upgrade the executable and retry the failed local validation with the same source; preserve any existing publication journal and follow its recovery instructions if a transaction was already submitted. Existing image types and size limits still apply.
