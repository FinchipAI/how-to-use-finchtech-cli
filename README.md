# How to use Finchtech (Finch) CLI

The official Agent Skill for operating Finch Agent, Task, and Skill markets through the Finch Remote MCP and the locally installed Finch CLI.

The Skill entry point is [`SKILL.md`](SKILL.md). It routes market-specific work to the maintained references under [`references/`](references/).

## Official runtime

- CLI package: `@finchtech/cli`
- Required CLI version: `0.3.3` or newer
- Primary command: `finch` (`finchtech` is only a compatibility alias)
- Remote MCP: `https://www.finchtech.ai/mcp`

```bash
pnpm add --global @finchtech/cli@0.3.3
finch --version
```

CLI 0.3.1 is required for new SkillRoot publications and encrypted downloads, including historical encrypted Skills. Upgrade the CLI as well as this Skill; installing these instructions does not upgrade the executable. See [Skill publication and delivery](references/skill.md) for ZIP import and compatibility rules.

## Legacy FinChip CLI

The former `finchip-cli` npm package and the `use-finchip-cli` Skill are deprecated and are no longer maintained. Do not use them for Finch.

Remove the legacy package before installing the current CLI so that old command shims cannot be mistaken for Finch:

```bash
npm uninstall --global finchip-cli
pnpm add --global @finchtech/cli@0.3.3
finch --version
```

The historical Skill repository remains available only as a migration notice and audit record: [`FinchipAI/how-to-use-finchip-cli`](https://github.com/FinchipAI/how-to-use-finchip-cli).

## Source and releases

The public Skill repository is [`FinchipAI/how-to-use-finchtech-cli`](https://github.com/FinchipAI/how-to-use-finchtech-cli). Read the instructions and references here, and find versioned downloads under [Releases](https://github.com/FinchipAI/how-to-use-finchtech-cli/releases). The canonical source is maintained internally alongside Finch's MCP and contract code; using this Skill requires no access to the private repository.

Tagged releases in this repository version the Skill independently from `@finchtech/cli`.

CLI 0.3.3 includes final multipart upload limits (warning above 4,000,000 bytes, rejection above 4,500,000), journal v6 recovery guards, and detailed ZIP/intent errors. The 10 MiB source ZIP import limit is a separate check. Follow [publication diagnostics and recovery](references/skill.md#publication-diagnostics-and-recovery-cli-033) before retrying a failed publication.

`finch mcp doctor` checks the CLI Session and MCP discovery, not the Harness's OAuth credentials. Its `harnessOAuth.status` is `not_checked`; compare the connected MCP identity with `finch status` and use native Harness reauthorization when needed. This release does not claim to fix production intent availability, manifest availability or OAuth persistence. Updating this Skill does not upgrade the installed CLI.
