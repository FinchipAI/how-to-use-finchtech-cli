# Skill Market

Source shape and content protection are independent choices. A Creator may publish one file or one directory using `plaintext`, `finchip_v2`, or `lit` when the selected deployment supports that mode. Never substitute a GitHub or arbitrary IPFS URL for a new local package.

## Creator

Use `skill_market:discover` and `skill_market:creator:write`.

1. Collect a unique slug, name, protocol category, source path, file-or-directory source kind, content mode, license, price, maximum supply, usage limit, optional platform display category, and required public presentation. Do not guess economics or publish a repository root.
2. Prepare publication through MCP, call `identity_actor_get`, compare it with `finchtech status`, and hard stop if Account, wallet, or environment differs. Show the exact custody summary for approval, then run the returned `finchtech skill publish-submit` action. Packaging, filtering, deterministic ZIP creation, optional encryption, upload, key custody, and chain submission stay local.
3. Prepare a public cover upload through MCP and run `finchtech skill asset-upload`; then prepare presentation and run `finchtech skill presentation-submit`. Presentation may include bounded summary, description, tags, parameters, dependencies, capabilities, compatibility, repository and documentation links, support, release notes, and related public metadata.
4. Use Manage reads before changing anything. Manage supports platform display category, unit price, maximum supply, public presentation, and a new file-or-directory version. Use the corresponding MCP preparation and returned `finchtech` action (`price-submit`, `supply-submit`, `presentation-submit`, or `version-submit`), repeating the MCP/CLI identity comparison before each custody action. Re-read chain and presentation state after each change.
5. Preserve the protected local recovery journal until all multi-transaction publication or version stages settle. Resume only with `finchtech skill recover publication <FINGERPRINT>` using the non-secret 64-hex fingerprint printed by the CLI. Do not expose journal contents, rerun a broadcast stage, delete local state, or create a replacement Skill after an unknown outcome.

`plaintext` means the package is publicly downloadable without a holding or wallet proof. A zero-priced protected Skill is still protected and still requires acquisition before key release. `finchip_v2` and `lit` are distinct existing envelope modes; do not translate or invent cryptographic data between them.

## Buyer

Use `skill_market:discover` and `skill_market:buyer:write` as needed.

1. Search or list, then inspect the exact Skill ID and version, owner, price, supply, content mode, package hash, presentation, and delivery terms.
2. Download `plaintext` content through the public delivery plan without purchasing. For protected content, prepare purchase through MCP, call `identity_actor_get`, require exact equality with `finchtech status`, show the transaction summary for approval, and run the exact `finchtech skill purchase-submit` action. The command validates `signingAuthority`, broadcasts once, checkpoints the transaction hash before waiting for a receipt, and confirms atomically.
3. Read delivery through MCP and run `finchtech skill download` to a new protected output file. Normal packages use IPFS. The legacy plaintext Skill 21 delivery may contain bounded canonical `data:text/markdown;base64` content; pass the authoritative plan unchanged to the CLI so it decodes locally and verifies the immutable package hash. Never decode, rewrite, or extend this exception to another Skill, protected content, or another URI/media type.
4. When moving an owned holding to a newer compatible version, prepare conversion through MCP, repeat the identity comparison, and run `finchtech skill convert-submit`; verify the old/new balances and download the selected version explicitly.

If purchase or conversion times out after broadcast, recover only with `finchtech skill recover intent <FINGERPRINT>`. Recovery verifies the recorded transaction's sender, recipient, calldata, and value before waiting and confirming; it never broadcasts again. A buyer-intent journal containing a transaction hash can only be recovered, never abandoned or deleted by hand. Do not print or inspect journal secrets; logout and wallet-switch errors expose only the kind, fingerprint, and public recovery command.

Skill catalog and holdings are chain-authoritative, while projected search may converge after a confirmed transaction. Never treat an older search projection as permission to override the current chain-authoritative detail.
