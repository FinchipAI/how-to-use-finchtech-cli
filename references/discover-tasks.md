# Task fields and eligibility

Finch Tasks are reward campaigns: a requester funds a USDC pool on chain, participants complete steps (follow, post, join, register, custom actions) and submit proof, and accepted entries are paid from the pool.

## Status

| `status` | Meaning |
| --- | --- |
| `not_started` | Funded; opens at `starts_at` (`opens_in` shows how long until then) |
| `open` | Accepting entries |
| `judging` | Closed to new entries; payout being decided. This can happen before the deadline |
| `closed`, `settled` | Finished; `settled` means payouts are complete |
| `cancelled` | Withdrawn by the requester |

`open_for_entries` on a list row is `false` when the status, deadline, winner slots or a reached submitter cap already rule entries out, and `null` otherwise, because the region restriction is only in the Task detail. `--joinable` loads the detail of each Task the list row does not rule out, so it takes `--limit` 50 or less (a larger page is refused), and keeps only Tasks whose `can_join_now` is `true`, adding `can_join_now`, `blockers` and `unknowns` to each row and replacing `requirements` and `caution` with versions computed from the detail, steps included. The rows still do not list the steps, pool or winner count, so run `task` for each Task you recommend. In `task` output, `open_for_entries` equals `can_join_now`. Every Task on the page lands in exactly one count, so with `--joinable` these add up to `page_items`: `returned`; `excluded_by_filters` (removed by `--min-reward`, `--min-per-entry` or `--no-x`, including Tasks whose steps turned out to need X); `excluded_by_list_check` (the list row already ruled it out: closed, past the deadline, no winner slots, submitter cap reached); `excluded_after_detail_check` (the detail ruled it out); and `unconfirmed` (the detail could not confirm it). `excluded_after_detail_check_tasks` and `unconfirmed_tasks` name those Tasks with their `blockers` or `unknowns` (for example the region restriction), so explaining why an open-looking Task is not joinable needs no extra lookup. More joinable Tasks may be on later pages (`next_page`). Without `--joinable`, a list row's `caution` covers only the title, description and goal summary; run `task` for the steps. `time_left` counts down to the deadline and is shown only for `open` and `not_started` Tasks.

## Money

- `reward_pool`: total funded amount shared by all paid entries.
- `reward_per_entry`: what one accepted entry earns.
- `pool` (from `task`): this Task's live balance inside Finch's shared TaskVault contract on Base: `deposited`, `paid_out`, `refunded`, `available`, plus the funding transaction link. `vault_address` is shared by all Tasks, so cite `available`, not the contract's total holdings. `available` of zero means nothing is left to pay.

## Counts

| Field | Meaning |
| --- | --- |
| `winner_count` | How many entries the pool pays (from `task`) |
| `winner_slots_left` | Paid slots not yet confirmed. It falls only as the requester or rules confirm payouts, so it can stay high while entries pile up. List rows use Finch's own value and warn if it differs from targetCount minus confirmed payouts; the detail computes it. `null` means unknown |
| `entries` | Submissions so far |
| `joined` | Accounts that joined, submitted or not (list only) |
| `submitters`, `submitter_cap` | Accounts that submitted, and the cap on them, which Finch sets from `winner_count` (from `task`, and on list rows that carry them; `null` means unknown). Reaching the cap blocks new accounts. `submitters` can exceed the cap, because earlier submissions are kept when the cap is reached or lowered; that is not a data error |

Competition for paid slots is roughly `entries` against `winner_count`; say so when it is high.

## Participation models

`participation_model` is `collaborative` when every accepted entry earns `reward_per_entry` until the winner slots run out, and `competition` when entries compete for a fixed number of winners (one by default). `--model` filters on it.

## Payout modes

| `payout_mode` | How winners are decided |
| --- | --- |
| `fcfs_realtime` | Paid automatically as entries are verified, first come first served |
| `weighted_lottery` | Lottery among valid entries after the deadline |
| `merchant_manual` | Requester reviews and chooses |
| `delayed_auto_7d` | Requester reviews within 7 days after the deadline |
| `merchant_review_7d` | Requester reviews for 7 days; entries not rejected are paid by the platform about 9 days after the deadline |

Only `fcfs_realtime` pays without a draw or a review. Say so when the user asks "how much will I get". When more entries qualify than `winner_slots_left`, the listing does not say how winners are chosen; say that rather than guessing. `award_deadline` is the last moment the pool can pay out.

## Steps

`steps[]` come from the Task's goals, in order. `verification` is `automatic` for steps Finch checks itself (X follow, X post, retweet or quote, Discord join, link visit), `requester review` for custom, register, Telegram join, Agent goal and other proof-based steps, and `unknown` when the goal-type catalog could not be loaded or the type is new. An Agent goal (`agent_native`) is a proof-based step whose proof type is in `proof`, like any other; when its wording repeats another step, each step still needs its own submission. `proof` lists what the participant must submit: `handle`, `tweet_url`, `screenshot`, `account_id`, `text`, `link`, `video`, `oauth`, or `none` (nothing to submit, as for a link visit). `instructions` keeps the requester's full text, including rejection criteria; summarize it, but keep the conditions that decide approval.

`requirements` lists account prerequisites: `x_account` (a bound X account), `human_check`, and X thresholds such as `min_x_followers`. Proof needs are per step, not in `requirements`, and so are other accounts: a Discord or Telegram join, or an account on the requester's platform, shows only as a step. Check the steps before telling a user with only an X account that they can do a Task. `x_account` is true when the Task's flag says so or any step is on X. The website sets the flag from the steps, but a Task created through the API may leave it false. On a list row, which has no steps, the flag and the goal summary text are all the helper sees, so `x_account: false` there is provisional; the value from `task` or `--joinable` is final.

## Eligibility

`can_join_now` is `false` when any `blockers` entry applies: the Task is not open, has not started, is past its deadline, is restricted in the lookup's region, has reached its submitter cap, has no winner slots left, or has an empty pool. It is `null` when nothing blocks but something could not be confirmed, listed in `unknowns` (an unreadable deadline or unreported winner slots); never present `null` as yes. A requester can never join their own Task. Join and submit can also be paused by Finch operators; the signed-in join in [task.md](task.md) reports that.

Region: anonymous visibility and `regionParticipationRestricted` reflect the network location where the helper ran, not necessarily the user's. The helper cannot report that location, so say the result applies to wherever the lookup ran and that the user's own signed-in view decides.

## Caution flags

`caution` is a keyword check over the title, description and steps. English keywords match in any word form, also where an English word touches Chinese text. Chinese matches a fixed word list in Simplified and Traditional (listed below), not every way of saying the same thing. Each entry has:

- `flag`: the class, one of four:
  - mentions a seed phrase, private key or token approval (the highest risk). It also fires when the text only warns about them.
  - spends or locks the user's own funds (deposit, transfer, sending coins or tokens, trade, stake, swap, buy, invest, bridge, lend, mint, yield and similar)
  - opens an account or financial product (registration, KYC, opening a card or a non-social account)
  - connects or discloses a crypto wallet
- `context`: up to three snippets, each the sentence around a hit (at most 100 characters before and 60 after). Read them to tell a request ("deposit 100 USDT") from a warning ("the screenshot must not contain your private key") or an unrelated use (the Chinese for "transaction hash" contains the Chinese for "trade").
- `places`: how many distinct snippets matched. When it exceeds three, read the full `description` and `steps`.

Chinese words covered: seed phrase, private key, token or contract or unlimited approval, approval limit, approving a contract or token (plain "authorize" is left out, because it usually means signing in with a social account); top up, pay in, pledge or stake, deposit, buy in, purchase, trade, invest, exchange, cross-chain, lending, loan, mint, annualized yield, wealth product, transfer, transfer in, pay (the payout word for the requester paying participants is left out); open a card, real-name verification, register, open an account, ID card; wallet.

It is a prompt to inform the user, not a judgment of the Task. It misses actions described only by a link or in words outside these lists, so a Task without flags can still carry risk.

## Listing behavior

`goal` is a one-line summary of the steps (for example "X follow + Visit a link"), written by the creator's client; where it or the title disagrees with `steps`, the steps are what entries are checked against. Some descriptions are generated by Finch from the step list (for example "Complete the published goals: ..."); describe the steps instead of quoting such text as the requester's words. Most current Tasks have no `category`, so the website's category filter usually returns nothing; use `--query` instead. `--sort top` follows Finch's own ranking, which is not strictly by reward; when the user wants the largest reward, sort the returned Tasks by `reward_pool` or `reward_per_entry` yourself and say that the order covers the page returned.
