# Task Market

## Requester

Use `task_market:discover`, `task_market:requester:read`, and `task_market:requester:write` as needed.

In a mounted Finch MCP harness, use these exact requester tools to create and prepare work: `task_market_task_create_draft`, `task_market_task_prepare_publish`, `task_market_task_review_board`, `task_market_task_prepare_review`, and, only when explicitly requested, `task_market_task_prepare_reclaim`. The atomic CLI actions perform `confirm_publish`, `confirm_review`, or `confirm_reclaim` with their own minimum-scope local grant; do not make a second manual confirm call after a successful CLI result. Draft `rewardAmount` and `perSubmissionReward` values are decimal USDC amounts; returned custody preparations use atomic-unit string fields such as `amountAtomic` and carry the authoritative `signingAuthority`.

1. Collect the title, instructions, collaboration and settlement modes, verification requirements, reward asset and amounts, submission limits, deadline, and participant constraints. Do not invent review policy or funding.
2. Create the draft and prepare publication through MCP. Call `identity_actor_get`, compare it with `finch status`, and hard stop if Account, wallet, or environment differs. Inspect the frozen pool preparation, show the exact transaction summary for approval, then run the returned `finch task publish-submit` action. It validates authority, broadcasts once, checkpoints the hash, and confirms atomically.
3. Re-read the Task and require the expected open and funded state.
4. Read the review board. For each user-authorized decision, prepare review through MCP, repeat the MCP/CLI identity comparison, show the award summary, and run `finch task award-sign`. The command records one EIP-712 signature batch and confirms review atomically; the runtime broadcasts the award. Do not create another signature batch after an unknown response. Verify approved submission, participation, award operation, fee, and remaining pool.
5. Reclaim only when the user explicitly requests it and the Task is eligible: prepare through MCP, repeat the identity comparison, show the transaction summary, and run `finch task reclaim-submit`. It broadcasts once, checkpoints the hash, and confirms atomically. Do not close or reclaim a Task merely to clean up a run.

### Expired requester award reservations

For an explicit requester cancellation, use the mounted `task_market_task_prepare_review` with `action: "cancel_award"` and the exact submission IDs (at most 100 per headless request). Only expired, unused, unsigned and unrelayed merchant-controlled preparations can be released. The server verifies chain usage and expiry; the last valid on-chain second is still valid. A successful cancellation releases the reservation and returns the submission to pending without a new wallet signature. Reassign only if the Task award window remains open. This does not revoke an already paid reward.

For persisted or externally paid awards, recover the existing receipt instead of generating a second signature/payment. Separately paid or partially paid batches may require restoring each submission separately; obey the returned recovery error. Re-read the review board after cancellation or recovery before preparing new awards.

## Participant

Use `task_market:discover`, `task_market:participant:read`, and `task_market:participant:write` as needed.

In a mounted Finch MCP harness, use `task_market_tasks_list`, `task_market_task_get`, `task_market_task_join`, `task_market_task_submit`, and `task_market_task_my_submission` directly. Do not spend time searching for alternate Task tool names after these mounted tools are available.

1. List and inspect the exact open Task, its verification requirements, deadline, reward, and remaining capacity.
2. Call `identity_actor_get` and verify that this participant is a different Account from the Task requester. A requester cannot join or submit to its own Task. Use a separately authorized Account B rather than silently switching Account A's wallet or OAuth identity.
3. Join once with a stable idempotency key. Submit only user-provided content, proof URL, and attachments that satisfy the published requirements. Attachments must be uploaded Finch proof locators or HTTP(S) links; local paths and `file:filename` placeholders are not uploaded evidence. Task covers are retired; omit `imageLocator` or pass null when creating a draft.
4. Read `my_submission` and report its stable participation and submission IDs. Do not self-approve or infer an award.
5. After requester review, re-read the submission and Task; distinguish approved, rejected, pending, and paid states.

When X verification returns `manual_review` with `x_daily_credit_limit_exceeded` or `x_credit_budget_unavailable`, report that requester review is required. Web and MCP share the daily budget; changing clients or retrying does not bypass it. Respect returned retry limits for each goal. A manual verification decision is separate from reward settlement; use the requester review and award flow only for the user's explicit decision.

X verification has an Account-wide limit of 30 verification executions in a rolling 24-hour window, shared by Web and MCP. Short-window Task/Goal limits and the platform API budget still apply. The automatic retry within one owned execution reuses its Account allowance, while provider calls remain subject to the platform budget. On `TWITTER_VERIFICATION_LIMIT_REACHED` (HTTP 429), report the retry time in the error and wait until then. On `TWITTER_VERIFICATION_IN_PROGRESS` (HTTP 409), wait two minutes and retry the same request with the same idempotency key and payload. A completed request reuses its stored result; an uncertain provider attempt may consume another allowance when recovered. On `IDEMPOTENCY_CONFLICT` (HTTP 409), reconcile the original request before submitting any changed intent with a new key. Switching clients or identities is not a recovery path for these limits.

Task join and submit may also be restricted by current operator controls, independently of the displayed Task lifecycle. Re-read the Task and report the returned restriction; Web and MCP share these controls. Resume only when the operation is allowed again.

Keep a Task's publication, participant mutation, review, and reclaim idempotency keys separate. A delayed response is not permission to create a second Task, submission, or award. Recover an irreversible requester action only with `finch task recover <TASK_ID> <KIND>`, where `KIND` is exactly `publish`, `award`, or `reclaim` as reported by the journal. The command reuses the recorded hash or signature batch and idempotency key; it does not need the original preparation file. A journal containing a hash or signatures can only be recovered, never abandoned or deleted by hand.

An end-to-end Task validation requires two isolated actors: requester A publishes and later reviews/awards; participant B joins and submits. Each actor must have its own Account, wallet, OAuth authorization, Finch home, and clean context.

## X and Telegram evidence

For an original X post or Quote Tweet, submit the participant's exact post URL; validation checks that post's author and the Task requirements, including the quoted target. Native Retweet uses the bound account and queries one page of up to 20 recent results within two hours. Only an empty result triggers a 30-second wait and one automatic re-query. If both results are empty, `x_retweet_search_empty` remains retryable: report that the action is unconfirmed and a new Verify attempt can be made later, respecting returned limits. Replaying a completed request retrieves its stored result rather than running a fresh check. Older activity or missing results may not be verifiable; do not claim that an arbitrary historical retweet is guaranteed to qualify.

Telegram participation uses a screenshot URL submitted as evidence for requester review. It is not automatic group-membership verification. Collect real user-provided evidence and never fabricate a screenshot or claim a successful membership check.

In the Web workbench, supported proof images and videos are uploaded and verified before submission (up to 10 MB per file). Upload success alone does not send evidence to the requester: submit the evidence or the final Task. Final submission saves pending manual/Telegram goal evidence first; `manual_review` makes those goals ready for requester submission, not automatically approved or paid. Re-read saved evidence after an interrupted submission before retrying. A historical filename-only record contains no recoverable file bytes and requires the participant to upload again.
