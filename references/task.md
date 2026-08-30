# Task Market

## Requester

Use `task_market:discover`, `task_market:requester:read`, and `task_market:requester:write` as needed.

In a mounted Finch MCP harness, use these exact requester tools to create and prepare work: `task_market_task_create_draft`, `task_market_task_prepare_publish`, `task_market_task_review_board`, `task_market_task_prepare_review`, and, only when explicitly requested, `task_market_task_prepare_reclaim`. The atomic CLI actions perform `confirm_publish`, `confirm_review`, or `confirm_reclaim` with their own minimum-scope local grant; do not make a second manual confirm call after a successful CLI result. Draft `rewardAmount` and `perSubmissionReward` values are decimal USDC amounts; returned custody preparations use atomic-unit string fields such as `amountAtomic` and carry the authoritative `signingAuthority`.

1. Collect the title, instructions, collaboration and settlement modes, verification requirements, reward asset and amounts, submission limits, deadline, and participant constraints. Do not invent review policy or funding.
2. Create the draft and prepare publication through MCP. Call `identity_actor_get`, compare it with `finchtech status`, and hard stop if Account, wallet, or environment differs. Inspect the frozen pool preparation, show the exact transaction summary for approval, then run the returned `finchtech task publish-submit` action. It validates authority, broadcasts once, checkpoints the hash, and confirms atomically.
3. Re-read the Task and require the expected open and funded state.
4. Read the review board. For each user-authorized decision, prepare review through MCP, repeat the MCP/CLI identity comparison, show the award summary, and run `finchtech task award-sign`. The command records one EIP-712 signature batch and confirms review atomically; the runtime broadcasts the award. Do not create another signature batch after an unknown response. Verify approved submission, participation, award operation, fee, and remaining pool.
5. Reclaim only when the user explicitly requests it and the Task is eligible: prepare through MCP, repeat the identity comparison, show the transaction summary, and run `finchtech task reclaim-submit`. It broadcasts once, checkpoints the hash, and confirms atomically. Do not close or reclaim a Task merely to clean up a run.

## Participant

Use `task_market:discover`, `task_market:participant:read`, and `task_market:participant:write` as needed.

In a mounted Finch MCP harness, use `task_market_tasks_list`, `task_market_task_get`, `task_market_task_join`, `task_market_task_submit`, and `task_market_task_my_submission` directly. Do not spend time searching for alternate Task tool names after these mounted tools are available.

1. List and inspect the exact open Task, its verification requirements, deadline, reward, and remaining capacity.
2. Call `identity_actor_get` and verify that this participant is a different Account from the Task requester. A requester cannot join or submit to its own Task. Use a separately authorized Account B rather than silently switching Account A's wallet or OAuth identity.
3. Join once with a stable idempotency key. Submit only user-provided content, proof URL, and attachments that satisfy the published requirements.
4. Read `my_submission` and report its stable participation and submission IDs. Do not self-approve or infer an award.
5. After requester review, re-read the submission and Task; distinguish approved, rejected, pending, and paid states.

Keep a Task's publication, participant mutation, review, and reclaim idempotency keys separate. A delayed response is not permission to create a second Task, submission, or award. Recover an irreversible requester action only with `finchtech task recover <TASK_ID> <KIND>`, where `KIND` is exactly `publish`, `award`, or `reclaim` as reported by the journal. The command reuses the recorded hash or signature batch and idempotency key; it does not need the original preparation file. A journal containing a hash or signatures can only be recovered, never abandoned or deleted by hand.

An end-to-end Task validation requires two isolated actors: requester A publishes and later reviews/awards; participant B joins and submits. Each actor must have its own Account, wallet, OAuth authorization, Finch home, and clean context.
