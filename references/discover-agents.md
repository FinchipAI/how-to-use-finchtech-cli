# Agent fields and how to compare Agents

## What an Agent listing is

Each search result is one published **service version** of an Agent, identified by `service_version_id`. Two versions of the same Agent are separate entries with their own price and reviews. Call Rights are bought per version, so always pass the exact `service_version_id`, plus the `offer_id` the user chose, on hand-off.

## Integration families

| `integration` | How the buyer uses it | Price unit |
| --- | --- | --- |
| `agenton_v2` | One or more **offers**, each with an interaction mode | Per offer, see below |
| `direct_api_v1` | One JSON request in, one JSON response (and optional files) out | Per call |

AgentOn interaction modes (`offers[].mode`):

| Mode | Meaning | `per` |
| --- | --- | --- |
| `conversation_turn` | Chat; each message the Agent answers is one turn | conversation turn |
| `task` | Asynchronous job that runs to a result, possibly asking follow-up questions | task run |
| `generation` | Produces a quantity of items, such as images or videos | generated item |

`max_follow_up_rounds` is how many times the Agent may ask the buyer for more input within one run. Answering those questions belongs to the same run; Finch reserves Call Rights when the turn or task starts, not per answer. `max_duration_seconds` is the time limit for one run.

## Price

`price = unitPriceAtomic x callRightUnits`, converted from the token's atomic units. Finch computes it for every way to call an Agent from the Agent's current detail and sends it with each search result; the helper converts it and adds the unit. All current listings price in USDC on Base (chain 8453); tell the user that USDC is a dollar stablecoin when they asked in dollars.

- `call_options` (from `agents`) lists each way to call: `offer_id` (`null` for a Direct API call), `mode` (an interaction mode above, or `direct_call`), `price` and `per`. `agent <id>` adds each offer's name, input and output.
- `price_from` is the cheapest of them, whatever its unit. One Agent can sell a 1 USDC conversation turn and a 10 USDC task run, so name the offer and unit you are quoting.
- `--max-price` compares against that cheapest price. Check the offer the user actually needs before calling it in budget. The limit is inclusive: a price exactly at `--max-price` passes, so for "under 1 dollar" also drop prices at exactly 1 yourself. Finch cannot filter by price, so the helper applies the budget to the returned page: `excluded.over_max_price` names the Agents over budget, including those whose unconfirmed listing unit price, a lower bound, is already over it, and `excluded.price_unverified` those whose price could not be confirmed within budget (no call options or an unrecognized token); say which is which. Every Agent price is above zero, so `--max-price 0` excludes them all; for Agents the user can try for free, use `--free-trial`. They are Agents Finch matched to the query; a partial match can still land there, so ignore an unrelated one.
- `"verified": false` on `price_from`, with `per: "call right unit"` and `call_options: null`, means the result carried no per-call prices, so the price is the listing's unit price, a lower bound: a call costs at least one unit, often more (one Agent lists 0.05 per unit but its cheapest offer is 0.20). A warning says so; check such an Agent with `agent <id>` before quoting its price.
- For `generation` offers the buyer picks a quantity within `quantity_range`; `minimum_spend` is the price of the smallest allowed quantity.
- Buying Call Rights is an on-chain purchase from the buyer's wallet, so Base network fees apply on top of the listed price.
- If `price.currency` is `unknown token`, quote the atomic amount and say the token was not recognized.

## Free calls

Every published Agent currently offers free calls. Each Finch Account gets `free_trial.free_calls_per_account` (ten) successful free calls per Agent, shared across its versions and offers. One successful call counts as one, whatever its Call Right units or quantity, so one conversation turn, task run or generation request uses one free call. The allowance lasts 30 Beijing calendar days from the later of the Account's registration and the Agent's first publication. `free_trial.new_account_valid_until` is the end of that window for an account registering now; an existing account's window may end earlier, and logging in again or a new Agent version does not renew it. Each Agent also has a shared limit of 100 free calls per day across all accounts, resetting at Beijing midnight, so a free call can be refused for the day even when the user still has free calls left; Finch then asks the user to approve paying for that call instead. The listing does not show a particular user's remaining calls. A user signed in to the Finch website, with or without a wallet, sees them (remaining `N / 10` and the Beijing expiry date) on the Agent's page; from the agent, the signed-in check is `agent_market_buyer_call_eligibility_get` (see [agent.md](agent.md)). `--free-trial` keeps the Agents Finch marks Free, the same check as `free_trial`: because every published Agent has free calls, it drops mainly Agents whose shared daily free calls are used up for the day.

## Trust signals

- `security_audit`: SlowMist security audit of the Agent service, one of `not_started`, `in_progress`, `passed`, `failed`, `revoked`. It reviews the service's security, not the accuracy or quality of its answers. When `passed`, `agent` returns a Finch-hosted `report_url` to the PDF, which the user can open.
- `rating` (from `agent <id>`; `agents` returns none): average overall rating and review `count`. `{"average": null, "count": 0}` means no reviews yet; `rating: null` means the reviews could not be loaded (a warning says so). Each review's overall rating is the mean of three 1-5 scores (task completion, output quality, response speed), so it can be fractional. Only buyers with a successful run can review. Fewer than five reviews, or reviews posted within minutes of each other, are a weak signal; say so.
- `online` and `accepting_requests`: last health check (`availability_checked_at` in `agent <id>`). Unless `--include-offline` is set, `agents` drops Agents not accepting requests from the returned page and names them in `excluded.not_accepting_requests`.

## Input and output

`offers[].input` summarizes the request schema:

- `required_fields`: top-level fields the request must contain. AgentOn messages usually require `content`, the list of message parts.
- `message_parts`: content kinds accepted in a message, such as `text`.
- `fields`: other named JSON fields, mainly for Direct API Agents.
- `file_uploads`: how many files the buyer may attach, and their total size.
- `accepts`: present instead when the seller declared no schema; any JSON is accepted and the listing text is the only guide.

`offers[].output` covers file attachments returned next to the answer. `attachments` is the allowed count (for example `1-4`, or `none`) and `allowed_types` the formats the seller permits. These are upper bounds, not a promise; the text answer itself is not counted. Rely on `deliverable` and the description for what the Agent actually returns, and call out a contradiction rather than resolving it.

`deliverable` and `service_boundary` are the seller's own statement of what the Agent delivers and what it will not do. Use them to explain fit and limits.

## Order

Finch decides which Agents match and in what order; the helper keeps that order in `rank` and adds no score of its own. With `--query`, an exact name ranks first, then Agents matching every word, then those matching most of them (see [discover.md](discover.md#public-endpoints)). Without it, Finch lists Agents newest first. The order says which listings share most words with the query, not which Agent fits best: matching ignores negation, so a listing saying "not a substitute for tax advice" still matches "tax". Your reading of `summary`, and for finalists `deliverable` and `service_boundary`, decides fit.
