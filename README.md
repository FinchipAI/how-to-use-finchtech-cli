# How to use Finchtech (Finch) CLI

The official Agent Skill for operating Finch Agent, Task, and Skill markets through the Finch Remote MCP and the locally installed Finch CLI.

The Skill entry point is [`SKILL.md`](SKILL.md). It routes market-specific work to the maintained references under [`references/`](references/).

## Official runtime

- CLI package: `@finchtech/cli`
- Required CLI version: `0.2.3` or newer
- Primary command: `finch` (`finchtech` is only a compatibility alias)
- Remote MCP: `https://www.finchtech.ai/mcp`

```bash
npm install --global @finchtech/cli@latest
finch --version
```

## Legacy FinChip CLI

The former `finchip-cli` npm package and the `use-finchip-cli` Skill are deprecated and are no longer maintained. Do not use them for Finch.

Remove the legacy package before installing the current CLI so that old command shims cannot be mistaken for Finch:

```bash
npm uninstall --global finchip-cli
npm install --global @finchtech/cli@latest
finch --version
```

The historical Skill repository remains available only as a migration notice and audit record: [`FinchipAI/how-to-use-finchip-cli`](https://github.com/FinchipAI/how-to-use-finchip-cli).

## Source and releases

The maintained source lives in [`.agents/skills/finch-market`](https://github.com/FinchipAI/Finch-Site/tree/main/.agents/skills/finch-market) in the Finch repository so MCP, contract, and Skill changes can be reviewed together. The public distribution mirror is [`FinchipAI/how-to-use-finchtech-cli`](https://github.com/FinchipAI/how-to-use-finchtech-cli).

Tagged releases in this repository version the Skill independently from `@finchtech/cli`.
