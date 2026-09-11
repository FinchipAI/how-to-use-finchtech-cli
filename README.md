# How to use Finchtech (Finch) CLI

The official Agent Skill for operating Finch Agent, Task, and Skill markets through the Finch Remote MCP and the locally installed Finch CLI.

The Skill entry point is [`SKILL.md`](SKILL.md). It routes market-specific work to the maintained references under [`references/`](references/).

## Official runtime

- CLI package: `@finchtech/cli`
- Required CLI version: `0.3.2` or newer
- Primary command: `finch` (`finchtech` is only a compatibility alias)
- Remote MCP: `https://www.finchtech.ai/mcp`

```bash
pnpm add --global @finchtech/cli@0.3.2
finch --version
```

CLI 0.3.1 is required for new SkillRoot publications and encrypted downloads, including historical encrypted Skills. Upgrade the CLI as well as this Skill; installing these instructions does not upgrade the executable. See [Skill publication and delivery](references/skill.md) for ZIP import and compatibility rules.

## Legacy FinChip CLI

The former `finchip-cli` npm package and the `use-finchip-cli` Skill are deprecated and are no longer maintained. Do not use them for Finch.

Remove the legacy package before installing the current CLI so that old command shims cannot be mistaken for Finch:

```bash
npm uninstall --global finchip-cli
pnpm add --global @finchtech/cli@0.3.2
finch --version
```

The historical Skill repository remains available only as a migration notice and audit record: [`FinchipAI/how-to-use-finchip-cli`](https://github.com/FinchipAI/how-to-use-finchip-cli).

## Source and releases

The maintained source lives in [`.agents/skills/finch-market`](https://github.com/FinchipAI/Finch-Site/tree/main/.agents/skills/finch-market) in the Finch repository so MCP, contract, and Skill changes can be reviewed together. The public distribution mirror is [`FinchipAI/how-to-use-finchtech-cli`](https://github.com/FinchipAI/how-to-use-finchtech-cli).

Tagged releases in this repository version the Skill independently from `@finchtech/cli`.

CLI 0.3.2 adds publication source/size diagnostics and safe recovery state. Use 0.3.2 or newer for the diagnostic and recovery guidance in this release. Updating this Skill does not upgrade the installed CLI.
