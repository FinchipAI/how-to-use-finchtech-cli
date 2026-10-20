#!/usr/bin/env python3
"""Inputs: Finch's public anonymous read APIs (www.finchtech.ai or an allowed FINCH_BASE_URL) and command-line filters.
Outputs: One JSON envelope per run: Agents or Skills in Finch's search order, one Agent's or Skill's detail, Task summaries, or one Task's detail.
Role: Lets the finch-market Skill find and compare Agents, reward Tasks and Skills before login; it never buys, invokes, joins, submits, downloads or signs.

Each search command sends one search request and keeps Finch's order. Filters Finch cannot apply run
on the returned page only and are reported in the output.

Commands
  agents  Search published Agents and return them with their price per call.
  agent   One Agent in depth: offers, cost per call, accepted input, output files,
          reviews, security audit, and page link.
  tasks   Browse reward Tasks with filters and return compact, comparable summaries.
  task    One Task in depth: steps, eligibility blockers, on-chain pool balance, page link.
  skills  Search Skills and return price, access and trust signals.
  skill   One Skill in depth: description, usage steps, current version, reviews, page link.
  holdings  Skills a wallet holds and what it paid, from public chain data.

Every run prints exactly one JSON object on stdout:
  {"ok": true,  "skill": "finch-market", "helper": "finch_discover", "version": "...", "command": "...", "data": {...}}
  {"ok": false, "skill": "finch-market", "helper": "finch_discover", "version": "...", "command": "...",
   "error": {"code": "...", "message": "..."}}
Exit status is 0 on success and 1 on error.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

SKILL = "finch-market"
HELPER = "finch_discover"
VERSION = "2.0.0"
DESCRIPTION = "Find Agents, reward Tasks and Skills on the Finch marketplace without signing in."
DEFAULT_BASE_URL = "https://www.finchtech.ai"
USER_AGENT = f"{SKILL}-discover/{VERSION} (+https://www.finchtech.ai/llms.txt)"
TIMEOUT_SECONDS = 30
MAX_DETAIL_FETCHES = 50
WORKERS = 6

# Finch's searches trim the query and refuse more than 200 characters (UTF-16 code units) with HTTP 400.
MAX_QUERY_CHARS = 200
# Agent search also refuses more than 200 UTF-8 bytes after NFC normalization (the v1 catalog contract).
MAX_AGENT_QUERY_BYTES = 200
# The website search (/api/market/search, /api/skills/catalog) returns at most 50 cards per page.
WEBSITE_PAGE_SIZE = 50

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# Payment tokens whose symbol and decimals are known without another lookup.
KNOWN_TOKENS = {
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": ("USDC", 6),  # USDC on Base (chain 8453)
}
EXPLORERS = {8453: "https://basescan.org"}

MODE_UNITS = {
    "conversation_turn": "conversation turn",
    "task": "task run",
    "generation": "generated item",
}
PAYOUT_LABELS = {
    "merchant_manual": "Requester reviews entries and picks who is paid.",
    "fcfs_realtime": "Paid automatically as entries are verified, first come first served.",
    "weighted_lottery": "Winners are drawn by lottery from valid entries after the deadline.",
    "delayed_auto_7d": "Requester reviews entries within 7 days after the deadline.",
    "merchant_review_7d": "Requester reviews for 7 days after the deadline; entries not rejected "
                          "are paid by the platform about 9 days after the deadline.",
}
# Goal types that predate the public goal-type catalog, labelled as the website labels them.
GOAL_LABELS = {
    "custom": "Custom action",
    "agent_native": "Agent goal",
    "tg_join": "Join Telegram group",
    "publication_custom": "Finch-reviewed custom action",
    "register": "Register on platform",
    "community": "Community activity",
    "survey": "User survey",
    "content_publish": "Publish content",
    "content_custom": "Custom content",
    "feedback_review": "Product review",
}
MEDIA_LABELS = {
    "application/json": "JSON",
    "application/pdf": "PDF",
    "application/zip": "ZIP",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
    "text/csv": "CSV",
    "text/markdown": "Markdown",
    "text/plain": "Text",
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WebP",
    "video/mp4": "MP4",
    "audio/mpeg": "MP3",
}

class FinchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message: str):  # report usage errors in the JSON envelope
        raise FinchError("INVALID_INPUT", message)


# ---------------------------------------------------------------- HTTP

class Client:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def get(self, path: str, params: dict | None = None):
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base}{path}" + (f"?{query}" if query else "")
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        failure = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                failure = server_error(exc, path)
                if exc.code < 500:
                    raise failure from None
            except json.JSONDecodeError:
                raise FinchError("INVALID_RESPONSE", f"{path} did not return JSON.") from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                reason = getattr(exc, "reason", exc)
                failure = FinchError("NETWORK_ERROR", f"Could not reach {self.base}: {reason}")
            if attempt == 0:
                time.sleep(1)
        raise failure


def server_error(exc: urllib.error.HTTPError, path: str) -> FinchError:
    code, message = f"HTTP_{exc.code}", f"{path} returned HTTP {exc.code}."
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        error = body.get("error") or {}
        code = error.get("code") or code
        message = error.get("message") or message
    except (ValueError, AttributeError):
        pass
    if exc.code == 404:
        code = "NOT_FOUND"
    return FinchError(code, message)


# ---------------------------------------------------------------- formatting

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    # Python 3.9 and 3.10 accept only 3 or 6 fractional digits; Finch also sends 5.
    text = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), text, count=1)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def utc_text(value) -> str | None:
    moment = parse_time(value)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if moment else value


def time_left(deadline: datetime | None, now: datetime) -> str | None:
    if deadline is None:
        return None
    seconds = int((deadline - now).total_seconds())
    if seconds <= 0:
        return "ended"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {rest // 60}m" if hours else f"{rest // 60}m"


def decimal_text(value) -> str | None:
    """'3000.000000' -> '3000'; '0.015000' -> '0.015'."""
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return format(number.normalize(), "f")


def token_for(address: str | None, card_price: dict | None = None):
    known = KNOWN_TOKENS.get((address or "").lower())
    if known:
        return known
    if card_price and card_price.get("currency") and card_price.get("decimals") is not None:
        return card_price["currency"], int(card_price["decimals"])
    return None


def money(atomic, token) -> dict:
    if atomic is None:
        return None
    if token is None:
        return {"atomic": str(atomic), "currency": "unknown token"}
    symbol, decimals = token
    return {"amount": decimal_text(Decimal(int(atomic)).scaleb(-decimals)), "currency": symbol}


def clip(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit].rsplit(" ", 1)[0]
    return cut + "..."


def extract_uuid(value: str) -> str:
    match = UUID_RE.search(value or "")
    if not match:
        raise FinchError("INVALID_INPUT", f"No ID found in {value!r}; pass the UUID or the page URL.")
    return match.group(0).lower()


# ---------------------------------------------------------------- agents

def translations(service: dict) -> dict:
    localization = service.get("localization") or {}
    return ((localization.get("input") or {}).get("translations")) or {}


def localized_name(service: dict, locale: str) -> str | None:
    name = (translations(service).get(locale) or {}).get("name")
    return name.strip() if name else None


def active_promotion(service: dict, now: datetime) -> dict | None:
    """Free calls under free-call V1.1: each Account gets them per canonical Agent for 30 Beijing
    days from the later of its registration and the Agent's first publication. The listing's
    expiresAt is that window for an Account registering now; an older Account's may end sooner."""
    promo = service.get("promotional")
    if not promo:
        return None
    until = parse_time(promo.get("expiresAt"))
    if until and until <= now:
        return None
    return {"free_calls_per_account": int(promo.get("grantOperations") or 0),
            "new_account_valid_until": promo.get("expiresAt")}


def summarize_input(schema) -> dict | None:
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties") or {}
    if not properties and not schema.get("required"):
        return {"accepts": "any JSON; the seller declared no input schema"}
    summary: dict = {"required_fields": schema.get("required") or []}
    content = properties.get("content")
    if isinstance(content, dict) and content.get("type") == "array":
        items = content.get("items") or {}
        parts = []
        for option in items.get("oneOf") or items.get("anyOf") or [items]:
            kind = ((option.get("properties") or {}).get("type") or {}).get("const")
            if kind:
                parts.append(kind)
        summary["message_parts"] = parts or ["unspecified"]
    fields = {}
    for name, spec in properties.items():
        if name == "content" or not isinstance(spec, dict):
            continue
        kind = spec.get("type", "any")
        fields[name] = "/".join(kind) if isinstance(kind, list) else kind
    if fields:
        summary["fields"] = fields
    uploads = schema.get("x-finch-input-artifacts")
    if isinstance(uploads, dict):
        summary["file_uploads"] = {
            "max_files": uploads.get("maxAssets"),
            "max_total_mb": round(int(uploads.get("maxTotalBytes") or 0) / 1048576),
        }
    return summary


def summarize_output(contract) -> dict | None:
    """File attachments the seller allows next to the answer: an upper bound, not a promise."""
    if not isinstance(contract, dict):
        return None
    count = contract.get("count") or {}
    if count.get("maxItems") == 0:
        return {"attachments": "none"}
    return {
        "attachments": f"{count.get('minItems', 0)}-{count.get('maxItems')}",
        "allowed_types": [MEDIA_LABELS.get(t, t) for t in contract.get("allowedMediaTypes") or []],
    }


def price_options(detail: dict, token) -> list[dict]:
    unit = int(detail.get("unitPriceAtomic") or 0)
    if detail.get("integrationFamily") == "direct_api_v1":
        return [{
            "name": "Direct API call",
            "mode": "direct_call",
            "price": money(unit * int(detail.get("callRightUnits") or 1), token),
            "per": "call",
            "max_duration_seconds": detail.get("maxDurationSeconds"),
            "input": summarize_input(detail.get("inputSchema")),
            "output": summarize_output(detail.get("artifactContract")),
        }]
    options = []
    for offer in detail.get("offers") or []:
        per_unit = unit * int(offer.get("callRightUnits") or 1)
        option = {
            "offer_id": offer.get("offerId"),
            "name": localized_name(offer, "en") or offer.get("displayName"),
            "mode": offer.get("interactionMode"),
            "price": money(per_unit, token),
            "per": MODE_UNITS.get(offer.get("interactionMode"), "call"),
            "max_duration_seconds": offer.get("maxDurationSeconds"),
            "max_follow_up_rounds": offer.get("maxInputRounds"),
            "input": summarize_input(offer.get("inputSchema")),
            "output": summarize_output(offer.get("artifactContract")),
        }
        min_quantity = int(offer.get("minQuantity") or 1)
        max_quantity = int(offer.get("maxQuantity") or 1)
        if max_quantity > 1:
            option["quantity_range"] = [min_quantity, max_quantity]
            option["minimum_spend"] = money(per_unit * min_quantity, token)
        options.append(option)
    return options


def cheapest(options: list[dict]) -> dict | None:
    priced = [o for o in options if o["price"] and "amount" in o["price"]]
    if not priced:
        return None
    best = min(priced, key=lambda o: Decimal(o["price"]["amount"]))
    return {**best["price"], "per": best["per"]}


def rating_of(reviews: dict | None) -> dict | None:
    if reviews is None:  # unknown, which is not the same as "no reviews"
        return None
    summary = reviews.get("summary") or {}
    if not summary.get("reviewCount"):
        return {"average": None, "count": 0}
    return {"average": summary.get("averageRating"), "count": summary.get("reviewCount")}


def load_agent(client: Client, version_id: str, review_count: int = 1):
    detail = client.get(f"/api/v1/agent-market/catalog/services/{version_id}")
    try:
        reviews = client.get(f"/api/v1/agent-market/catalog/services/{version_id}/reviews",
                             {"perPage": review_count})
    except FinchError:
        reviews = None
    return detail, reviews


def agent_url(base: str, version_id: str) -> str:
    return f"{base}/market/chips/agent-{version_id}"


def call_options(ref: dict, token) -> list[dict] | None:
    """What one call costs for each way to call the Agent, which Finch computes from the current
    detail (ADR-0169). None when the card carries no call options."""
    entries = ref.get("callOptions")
    if entries is None:
        return None
    options = []
    for entry in entries:
        price = int(entry["priceAtomic"])
        mode = entry.get("interactionMode")
        option = {
            "offer_id": entry.get("offerId"),
            "mode": mode or "direct_call",
            "price": money(price, token),
            "per": MODE_UNITS.get(mode, "call"),
        }
        min_quantity, max_quantity = int(entry["minQuantity"]), int(entry["maxQuantity"])
        if max_quantity > 1:
            option["quantity_range"] = [min_quantity, max_quantity]
            option["minimum_spend"] = money(price * min_quantity, token)
        options.append(option)
    return options


def unit_price(card: dict, token) -> dict | None:
    """Unit price from the card: a lower bound, because a call costs at least one unit."""
    price = money((card.get("price") or {}).get("atomic"), token)
    return {**price, "per": "call right unit", "verified": False} if price else None


def agent_record(base: str, card: dict, now: datetime) -> dict:
    ref = card.get("agentMarketRef") or {}
    version_id = ref.get("serviceVersionId")
    token = token_for(None, card.get("price"))
    options = call_options(ref, token)
    availability = ref.get("availability") or {}
    return {
        "service_version_id": version_id,
        "name": (card.get("name") or "").strip(),
        "name_zh": localized_name(ref, "zh"),
        "category": card.get("category"),
        "integration": ref.get("integrationFamily"),
        "summary": clip(card.get("summary"), 300),
        "price_from": cheapest(options or []) or unit_price(card, token),
        "call_options": options,
        "free_trial": active_promotion(ref, now),
        "security_audit": ref.get("slowmistAuditStatus"),
        "online": availability.get("status"),
        "accepting_requests": availability.get("acceptingRequests"),
        "url": agent_url(base, version_id),
    }


def known_amount(price: dict | None) -> Decimal | None:
    return Decimal(price["amount"]) if price and "amount" in price else None


def agent_post_filters(args) -> dict:
    """Filters Finch's Agent search cannot apply; the helper applies them to the returned page."""
    filters = {"accepting_requests": not args.include_offline, "integration": args.integration,
               "audited": args.audited, "max_price": args.max_price}
    return {k: v for k, v in filters.items() if v is not None and v is not False}  # 0 is a real limit


def agent_exclusion(record: dict, args, max_price: Decimal | None) -> str | None:
    if not args.include_offline and not record["accepting_requests"]:
        return "not_accepting_requests"
    if args.integration and record["integration"] != args.integration:
        return "integration"
    if args.audited and record["security_audit"] != "passed":
        return "not_audited"
    if max_price is not None:
        price = record["price_from"]
        amount = known_amount(price)
        if amount is not None and amount > max_price:
            return "over_max_price"  # an unverified price is a lower bound, so it is over budget too
        if amount is None or price.get("verified") is False:
            return "price_unverified"
    return None


EXCLUSION_KEYS = {"accepting_requests": ("not_accepting_requests",), "integration": ("integration",),
                  "audited": ("not_audited",), "max_price": ("over_max_price", "price_unverified")}


def cmd_agents(client: Client, args) -> dict:
    """One search request; Finch matches and orders the Agents and returns their per-call prices."""
    now = now_utc()
    warnings: list[str] = []
    params = {"kind": "agent", "q": args.query, "category": args.category,
              "price": "free" if args.free_trial else None, "cursor": args.cursor}
    page = client.get("/api/market/search", params)
    items = page.get("items") or []
    post_filters = agent_post_filters(args)
    excluded = {key: [] for name in post_filters for key in EXCLUSION_KEYS[name]}
    max_price = Decimal(str(args.max_price)) if args.max_price is not None else None
    kept = []
    for card in items:
        record = agent_record(client.base, card, now)
        reason = agent_exclusion(record, args, max_price)
        if reason:
            excluded[reason].append(record["name"])
        else:
            kept.append(record)
    results = kept[:args.limit]
    for rank, record in enumerate(results, 1):
        record["rank"] = rank
    unpriced = sum(1 for r in results if r["call_options"] is None)
    if unpriced:
        warnings.append(f"{unpriced} Agent(s) carry no per-call prices, so price_from is the listing unit price, "
                        "a lower bound (verified: false); check them with `agent <id>` before quoting a price.")
    data = {
        "query": args.query,
        "filters": {k: v for k, v in params.items() if v is not None and k not in ("kind", "cursor")},
        "post_filters": post_filters,
        "total_matches": page.get("totalCount"),
        "page_items": len(items),
        "excluded": excluded,
        "returned": len(results),
        "beyond_limit": len(kept) - len(results),
        "next_cursor": page.get("nextCursor"),
        "agents": results,
        "warnings": warnings,
    }
    if not items:
        data["hint"] = ("Finch found no Agent. Retry once with other words, in English or in the user's language "
                        "(one language per query), then drop --query to browse; say so if nothing fits."
                        if args.query else "No Agent matches these filters.")
    elif not results and excluded.get("over_max_price") and not excluded.get("price_unverified"):
        data["hint"] = ("Every Agent on this page is over --max-price. Tell the user the cheapest relevant option, "
                        "and also browse without --query and --max-price: a general-purpose Agent may fit the need "
                        "within budget.")
    elif not results and excluded.get("price_unverified"):
        data["hint"] = ("No Agent on this page is confirmed within --max-price; some prices could not be verified. "
                        "Check those Agents with `agent <id>` or tell the user the price is unconfirmed.")
    return data


def cmd_agent(client: Client, args) -> dict:
    version_id = extract_uuid(args.id)
    now = now_utc()
    detail, reviews = load_agent(client, version_id, review_count=args.reviews)
    warnings = [] if reviews is not None else ["Reviews unavailable; rating unknown."]
    token = token_for(detail.get("paymentToken"))
    source = (detail.get("localization") or {}).get("source") or {}
    availability = detail.get("availability") or {}
    options = price_options(detail, token)
    report = detail.get("slowmistAuditReport")
    latest = []
    for review in (reviews or {}).get("reviews") or []:
        latest.append({
            "rating": review.get("overallRating"),
            "text": clip(review.get("body") or review.get("text") or review.get("content"), 400),
            "date": utc_text(review.get("createdAt") or review.get("publishedAt")),
        })
    return {
        "service_version_id": version_id,
        "name": (detail.get("displayName") or "").strip(),
        "name_zh": localized_name(detail, "zh"),
        "integration": detail.get("integrationFamily"),
        "description": detail.get("description"),
        "deliverable": source.get("deliverable") or None,
        "service_boundary": source.get("serviceBoundary") or None,
        "offers": options,
        "price_from": cheapest(options),
        "free_trial": active_promotion(detail, now),
        "online": availability.get("status"),
        "accepting_requests": availability.get("acceptingRequests"),
        "availability_checked_at": availability.get("checkedAt"),
        "rating": rating_of(reviews),
        "latest_reviews": latest,
        "security_audit": {
            "status": detail.get("slowmistAuditStatus"),
            "report_url": (f"{client.base}/api/agent-market/slowmist-audit-reports/{version_id}"
                           if report else None),
        },
        "seller_wallet": detail.get("seller"),
        "support_contact": detail.get("supportContact"),
        "chain_id": detail.get("chainId"),
        "url": agent_url(client.base, version_id),
        "warnings": warnings,
        "next_step": ("To try it free, the user can sign in to the Finch website (no wallet needed) and open the "
                      "url, which also shows their free calls left. To check, buy Call Rights or run it from here, "
                      "sign in with the Finch CLI and Remote MCP as this Skill describes (references/agent.md)."),
    }


# ---------------------------------------------------------------- tasks

def task_url(base: str, task_id: str) -> str:
    return f"{base}/market/tasks/{task_id}"


X_GOAL_TYPES = frozenset({"x_follow", "x_retweet", "x_post"})
X_GOAL_RE = re.compile(r"\bX (follow|retweet|post)\b")


def requirements_of(task: dict) -> dict:
    config = task.get("extraConfig") or {}
    # requiresTwitter is set by the website form when a step is on X, but Tasks created through
    # the API may leave it false. The steps (detail only) decide; on list rows the goal summary,
    # free text the creator's client wrote, can only add the requirement, never rule it out.
    x_steps = (any(g.get("goalType") in X_GOAL_TYPES for g in task.get("goals") or [])
               or bool(X_GOAL_RE.search(task.get("goal") or "")))
    needs = {
        "x_account": bool(task.get("requiresTwitter")) or x_steps,
        "human_check": bool(task.get("requiresHuman")),
    }
    for key, label in (("minimumXFollowers", "min_x_followers"),
                       ("minimumXAccountAgeDays", "min_x_account_age_days"),
                       ("minimumXTweets", "min_x_posts")):
        if config.get(key):
            needs[label] = config[key]
    if config.get("requireXVerified"):
        needs["x_verified"] = True
    return needs


# Keyword flags in English (any word form) and a fixed list of Chinese terms, Simplified and
# Traditional, written as escapes. Chinese, in order: seed phrase, private key, token / contract /
# unlimited approval, approving a contract, approval limit, approving a token; top up, pay in,
# pledge/stake, deposit (two words), buy in, purchase, trade, invest, exchange/swap, cross-chain,
# lending, loan, mint, annualized (yield), wealth product, transfer, transfer in, pay (two words);
# open a card, real-name check, register, open an account, ID card; wallet. Plain "authorize" and
# the payout word "da kuan" are left out: they usually mean signing in with a social account and
# the requester paying participants. re.ASCII keeps word boundaries working where an English word
# touches Chinese text, as in "KYC" followed by Chinese.
CAUTION_FLAGS = re.IGNORECASE | re.ASCII
CAUTION_RULES = (
    ("Mentions a seed phrase, private key or token approval. Never share a seed phrase or private "
     "key, and check every approval before signing.",
     re.compile(r"\b((seed|recovery|mnemonic|secret) phrases?|mnemonics?|private keys?|(token|spending|unlimited) "
                r"approvals?|approve (the |a |your )?(token|spending|usdt|usdc)s?|set ?approval\w*)\b"
                r"|\u52a9\u8bb0\u8bcd|\u52a9\u8a18\u8a5e|\u79c1\u94a5|\u79c1\u9470|(\u4ee3\u5e01|\u4ee3\u5e63|\u5408\u7ea6|\u5408\u7d04|\u65e0\u9650|\u7121\u9650)(\u6388\u6743|\u6388\u6b0a)|(\u6388\u6743|\u6388\u6b0a)(\u5408\u7ea6|\u5408\u7d04|\u989d\u5ea6|\u984d\u5ea6)"
                r"|(\u6388\u6743|\u6388\u6b0a) ?(usdt|usdc|\u4ee3\u5e01|\u4ee3\u5e63)", CAUTION_FLAGS)),
    ("Spends or locks your own funds (deposit, trade, stake, swap or similar).",
     re.compile(r"\b(deposit\w*|stak(e|es|ed|ing)|trad(e|es|ed|ing|er|ers)|swap\w*|bridg(e|es|ed|ing)"
                r"|invest(s|ed|ing|ment|ments|or|ors)?|buy\w*|bought|purchas\w*|borrow\w*|lend(s|ing)?|loans?"
                r"|apy|yield\w*|mint(s|ed|ing)?|transfer(s|red|ring)?"
                # "send 10 USDT", but not "send us a DM".
                r"|(send|sends|sending|sent) (\S+ ){0,2}?(usdt|usdc|eth|btc|bnb|sol|tokens?|coins?|funds?|crypto))\b"
                r"|\u5145\u503c|\u5165\u91d1|\u8d28\u62bc|\u8cea\u62bc|\u5b58\u5165|\u5b58\u6b3e|\u4e70\u5165|\u8cb7\u5165|\u8d2d\u4e70|\u8cfc\u8cb7|\u4ea4\u6613|\u6295\u8d44|\u6295\u8cc7|\u5151\u6362|\u514c\u63db|\u8de8\u94fe|\u8de8\u93c8"
                r"|\u501f\u8d37|\u501f\u8cb8|\u8d37\u6b3e|\u8cb8\u6b3e|\u94f8\u9020|\u9444\u9020|\u5e74\u5316|\u7406\u8d22|\u7406\u8ca1"
                r"|\u8f6c\u8d26|\u8f49\u8cec|\u8f49\u5e33|\u8f6c\u5165|\u8f49\u5165|\u4ed8\u6b3e|\u652f\u4ed8", CAUTION_FLAGS)),
    ("Opens an account or financial product (registration, KYC or card).",
     re.compile(r"\b(regist\w*|sign[ -]?ups?|kyc"
                # "open your X account" is a social account, not a financial one.
                r"|open(s|ed|ing)? (a |an |your )?(?!(x|twitter|discord|telegram|tg|google|github|email)\b)"
                r"(\w+ )?(cards?|accounts?)"
                r"|(debit|credit|crypto|virtual|prepaid|bank) cards?)\b"
                r"|\u5f00\u5361|\u958b\u5361|\u5b9e\u540d|\u5be6\u540d|\u6ce8\u518c|\u8a3b\u518a|\u5f00\u6237|\u958b\u6236|\u8eab\u4efd\u8bc1|\u8eab\u4efd\u8b49", CAUTION_FLAGS)),
    ("Connects or discloses a crypto wallet.", re.compile(r"\bwallets?\b|\u94b1\u5305|\u9322\u5305", CAUTION_FLAGS)),
)
CONTEXT_BEFORE, CONTEXT_AFTER = 100, 60
MAX_CONTEXTS = 3
# Sentence ends in English and Chinese (full-width full stop, exclamation, question, semicolon).
SENTENCE_END_RE = re.compile(r"[.!?;](\s|$)|[\u3002\uff01\uff1f\uff1b]")


def snippet(text: str, start: int, end: int) -> tuple[str, int]:
    """The sentence around a hit, within CONTEXT_BEFORE and CONTEXT_AFTER characters and not cut
    inside a word, so a negation such as "must not" stays in view. Returns (snippet, end)."""
    low, high = max(0, start - CONTEXT_BEFORE), min(len(text), end + CONTEXT_AFTER)
    ends = [m.end() for m in SENTENCE_END_RE.finditer(text, low, start)]
    stop = SENTENCE_END_RE.search(text, end, high)
    lead = tail = "..."
    if ends:
        low, lead = ends[-1], ""
    elif low and text[low - 1].isalnum() and " " in text[low:start]:
        low = text.index(" ", low, start) + 1
    if stop:
        high, tail = stop.end(), ""
    elif high < len(text) and text[high].isalnum() and " " in text[end:high]:
        high = text.rindex(" ", end, high)
    return ((lead if low else "") + text[low:high].strip() + (tail if high < len(text) else "")), high


def cautions(*texts) -> list[dict]:
    """Keyword flags so the user notices money, account and key actions before joining.

    Each flag carries the text around its first hits, because a keyword cannot tell "deposit
    100 USDT" from "do not include your private key in the screenshot".
    """
    flat = list(dict.fromkeys(" ".join(t.split()) for t in texts if t))
    found = []
    for label, pattern in CAUTION_RULES:
        context = []
        for text in flat:
            covered = -1
            for hit in pattern.finditer(text):
                if hit.start() < covered:
                    continue
                piece, covered = snippet(text, hit.start(), hit.end())
                context.append(piece)
        unique = list(dict.fromkeys(context))
        if unique:
            found.append({"flag": label, "context": unique[:MAX_CONTEXTS], "places": len(unique)})
    return found


def computed_winner_slots(task: dict) -> int | None:
    """targetCount - confirmedCount, the formula the website list uses (mapTaskListRow)."""
    config = task.get("extraConfig") or {}
    target = config.get("targetCount") or (1 if task.get("participationModel") == "competition" else None)
    if target is None:
        return None
    return max(0, int(target) - int(task.get("confirmedCount") or 0))


def winner_slots(task: dict, warnings: list[str] | None = None) -> int | None:
    """List rows carry the server's slotsRemaining; detail rows do not, so it is computed there.

    On list rows the computed value is compared with the server's, so a change to the website
    formula shows up as a warning instead of drifting silently. None means unknown.
    """
    computed = computed_winner_slots(task)
    if "slotsRemaining" not in task:
        return computed
    server = task["slotsRemaining"]
    if server != computed and warnings is not None:
        warnings.append(f"Task {task.get('id')}: slotsRemaining {server} differs from targetCount - "
                        f"confirmedCount ({computed}); using the server value.")
    return server


def deadline_of(task: dict) -> tuple[datetime | None, bool]:
    """(deadline, known). A deadline that is present but unreadable is unknown, never open-ended."""
    raw = task.get("deadline")
    moment = parse_time(raw)
    return moment, not (raw and moment is None)


def entry_state(task: dict, slots: int | None, now: datetime) -> bool | None:
    """False when the list row already rules entries out; otherwise None, because the region
    restriction is only in the Task detail. Rows carry the submitter cap since ADR-0169; a row
    without it, or with null (unknown), leaves the cap to the detail."""
    deadline, known = deadline_of(task)
    if (task.get("status") != "open" or (known and deadline and deadline <= now) or slots == 0
            or task.get("participationLimitReached") is True):
        return False
    return None


def task_summary(task: dict, base: str, now: datetime, warnings: list[str] | None = None) -> dict:
    config = task.get("extraConfig") or {}
    deadline, _ = deadline_of(task)
    start = parse_time(task.get("startAt"))
    mode = task.get("settlementMode")
    status = task.get("status")
    slots = winner_slots(task, warnings)
    summary = {
        "task_id": task.get("id"),
        "title": task.get("title"),
        "status": status,
        "open_for_entries": entry_state(task, slots, now),
        "category": task.get("category"),
        "goal": task.get("goal"),
        "reward_pool": {"amount": decimal_text(task.get("rewardAmount")),
                        "currency": task.get("rewardCurrency")},
        "reward_per_entry": decimal_text(config.get("perSubmissionReward")),
        "participation_model": task.get("participationModel"),
        "payout": PAYOUT_LABELS.get(mode, mode),
        "payout_mode": mode,
        "winner_slots_left": slots,
        "entries": task.get("submissionCount"),
        "starts_at": task.get("startAt"),
        "opens_in": time_left(start, now) if status == "not_started" and start else None,
        "deadline": task.get("deadline"),
        "time_left": time_left(deadline, now) if status in ("open", "not_started") else None,
        "requirements": requirements_of(task),
        "caution": cautions(task.get("title"), task.get("description"), task.get("goal")),
        "url": task_url(base, task.get("id")),
    }
    if "participationCount" in task:  # list rows only: accounts that joined, submitted or not
        summary["joined"] = task["participationCount"]
    if "participationLimitReached" in task:  # every detail, and list rows since ADR-0169
        summary["submitters"] = task.get("participantCount")
        summary["submitter_cap"] = task.get("maxParticipants")
    return summary


def join_check(task: dict, vault: dict | None, now: datetime) -> dict:
    """Blockers decide "no"; unknowns leave the answer open (None) rather than assuming "yes"."""
    blockers, unknowns = [], []
    start = parse_time(task.get("startAt"))
    deadline, known = deadline_of(task)
    if task.get("status") != "open":
        blockers.append(f"Task status is '{task.get('status')}', not 'open'.")
    if start and start > now:
        blockers.append(f"Task opens at {task.get('startAt')}.")
    if not known:
        unknowns.append("The deadline could not be read.")
    elif deadline and deadline <= now:
        blockers.append("The deadline has passed.")
    if task.get("regionParticipationRestricted"):
        blockers.append("Participation is restricted in the region this lookup ran from.")
    if task.get("participationLimitReached"):
        blockers.append(f"The submitter cap is reached ({task.get('participantCount')}/"
                        f"{task.get('maxParticipants')}); new accounts cannot join.")
    slots = winner_slots(task)
    if slots == 0:
        blockers.append("No winner slots are left.")
    elif slots is None:
        unknowns.append("The number of winner slots is not reported.")
    if vault and Decimal(str(vault.get("available") or 0)) <= 0:
        blockers.append("The reward pool has no funds left.")
    return {"can_join_now": False if blockers else (None if unknowns else True),
            "blockers": blockers, "unknowns": unknowns}


def excluded_entry(summary: dict, key: str, reasons: list[str]) -> dict:
    return {"task_id": summary["task_id"], "title": summary["title"], key: reasons, "url": summary["url"]}


def cmd_tasks(client: Client, args) -> dict:
    """One list request for one page of --limit Tasks, in Finch's order. Filters Finch cannot apply
    run on that page; --joinable then loads the detail of each remaining candidate (at most fifty),
    because only the detail carries the region restriction and the steps."""
    if args.joinable and args.limit > MAX_DETAIL_FETCHES:
        # Rows past the detail cap could be neither shown nor reached through next_page.
        raise FinchError("INVALID_INPUT", f"--joinable loads every candidate's detail, at most {MAX_DETAIL_FETCHES} "
                                          f"per run; use --limit {MAX_DETAIL_FETCHES} or less and --page for more.")
    now = now_utc()
    warnings: list[str] = []
    params = {
        "section": args.section,
        "sort": args.sort,
        "taskStatus": args.when,
        "category": args.category,
        "q": args.query,
        "participationModel": args.model,
        "page": args.page,
        "perPage": args.limit,
    }
    result = client.get("/api/tasks", params)
    tasks = result.get("items") or []

    min_reward = Decimal(str(args.min_reward)) if args.min_reward is not None else None
    min_entry = Decimal(str(args.min_per_entry)) if args.min_per_entry is not None else None
    summaries, ruled_out_by_list, filtered_out = [], 0, 0
    for task in tasks:
        summary = task_summary(task, client.base, now, warnings)
        if ((min_reward is not None and Decimal(summary["reward_pool"]["amount"] or 0) < min_reward)
                or (min_entry is not None and Decimal(summary["reward_per_entry"] or 0) < min_entry)
                or (args.no_x and summary["requirements"]["x_account"])):
            filtered_out += 1
            continue
        if args.joinable and summary["open_for_entries"] is False:
            ruled_out_by_list += 1
            continue
        summaries.append(summary)

    not_joinable, unconfirmed = [], []
    if args.joinable:
        # The list row cannot see the region restriction or the steps; the detail can.
        with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
            futures = [pool.submit(client.get, f"/api/tasks/{s['task_id']}") for s in summaries]
        checked = []
        for summary, future in zip(summaries, futures):
            try:
                detail = future.result()
            except FinchError as exc:
                unconfirmed.append(excluded_entry(summary, "unknowns",
                                                  [f"The Task detail could not be loaded ({exc.code})."]))
                continue
            requirements = requirements_of(detail)
            if args.no_x and requirements["x_account"]:  # a step is on X though the row did not say so
                filtered_out += 1
                continue
            check = join_check(detail, None, now)
            summary.update(open_for_entries=check["can_join_now"], **check,
                           requirements=requirements, caution=detail_cautions(detail, {}))
            if check["can_join_now"] is True:
                checked.append(summary)
            elif check["can_join_now"] is None:
                unconfirmed.append(excluded_entry(summary, "unknowns", check["unknowns"]))
            else:
                not_joinable.append(excluded_entry(summary, "blockers", check["blockers"]))
        summaries = checked

    data = {
        "filters": {k: v for k, v in params.items() if v is not None and k not in ("page", "perPage")},
        "post_filters": {k: v for k, v in (("min_reward", args.min_reward),
                                           ("min_per_entry", args.min_per_entry),
                                           ("no_x", args.no_x), ("joinable", args.joinable))
                         if v is not None and v is not False},  # 0 is a real minimum
        "total_visible": result.get("total"),
        "page": args.page,
        "page_items": len(tasks),
        "returned": len(summaries),
        "next_page": args.page + 1 if result.get("hasMore") else None,
        "tasks": summaries,
        "warnings": warnings,
        "notes": ["Anonymous Task visibility is region-filtered by the caller's network location; "
                  "a signed-in user in another region may see a different list."],
    }
    if data["post_filters"]:
        data["excluded_by_filters"] = filtered_out
    if args.joinable:
        # With --joinable these four counts plus "returned" add up to "page_items".
        data["excluded_by_list_check"] = ruled_out_by_list
        data["excluded_after_detail_check"] = len(not_joinable)
        data["unconfirmed"] = len(unconfirmed)
        # Which Tasks the detail ruled out or left open, and why, so they need no extra lookup.
        data["excluded_after_detail_check_tasks"] = not_joinable
        data["unconfirmed_tasks"] = unconfirmed
    if not summaries:
        data["hint"] = ("No Task on this page matched. "
                        + ("Ask for --page next_page, loosen filters, " if data["next_page"] else "Loosen filters, ")
                        + "check --when upcoming for Tasks that open soon, or drop the keyword.")
    return data


# Goal types that need proof reviewed by the requester, per the website's format verification.
MANUAL_GOAL_TYPES = frozenset({"custom", "publication_custom", "register", "agent_native", "tg_join",
                               "community", "survey", "content_publish", "content_custom",
                               "feedback_review"})


def verification_of(kind: str | None, types: dict) -> str:
    if kind in types:
        return "automatic" if types[kind].get("isAutoVerifiable") else "requester review"
    return "requester review" if kind in MANUAL_GOAL_TYPES else "unknown"


def detail_cautions(task: dict, types: dict) -> list[dict]:
    """Cautions over the title, description and every step, which only the Task detail has.
    Step titles and instructions stay separate texts, so a snippet never runs one into the other."""
    steps = [describe_goal(g, types) for g in task.get("goals") or []]
    return cautions(task.get("title"), task.get("description"), task.get("goal"),
                    *[text for s in steps for text in (s["title"], s["instructions"])])


def describe_goal(goal: dict, types: dict) -> dict:
    kind = goal.get("goalType")
    meta = types.get(kind) or {}
    config = goal.get("config") or {}
    instructions = config.get("description")
    target = (config.get("account") or config.get("target_url") or config.get("target_tweet_url")
              or config.get("invite_link") or config.get("register_url"))
    if not instructions:
        if kind == "x_follow" and config.get("account"):
            instructions = f"Follow @{config['account']} on X."
        elif kind == "x_retweet":
            action = config.get("interaction_type") or "retweet or quote"
            instructions = f"{action.replace('_', ' ').capitalize()} the target X post."
        elif kind == "x_post":
            instructions = "Publish an X post with the required content."
            if config.get("tweet_content"):
                target = config["tweet_content"]
        elif kind == "discord_join":
            instructions = "Join the Discord server."
        elif kind == "visit_link":
            instructions = "Visit the link."
        elif kind == "register":
            instructions = f"Register on {config.get('platform_name') or 'the platform'}."
    return {
        "step": (goal.get("seq") or 0) + 1,
        "type": kind,
        "label": meta.get("label") or GOAL_LABELS.get(kind, kind),
        "title": goal.get("title") or config.get("custom_title"),
        "required": goal.get("required", True),
        "instructions": clip(instructions, 4000),
        "target": target,
        "proof": config.get("proof_types") or meta.get("proofTypes"),
        "verification": verification_of(kind, types),
    }


def cmd_task(client: Client, args) -> dict:
    task_id = extract_uuid(args.id)
    now = now_utc()
    warnings: list[str] = []
    task = client.get(f"/api/tasks/{task_id}")
    try:
        catalog = client.get("/api/tasks/types")
        types = {t["key"]: t for t in catalog.get("goalTypes") or [] if t.get("key")}
    except FinchError as exc:
        warnings.append(f"Goal type catalog unavailable ({exc.code}); automatic checks show as unknown.")
        types = {}
    vault = None
    if task.get("protocolPoolId"):
        try:
            vault = client.get(f"/api/tasks/{task_id}/vault")
        except FinchError as exc:
            warnings.append(f"Pool balance unavailable ({exc.code}).")

    steps = [describe_goal(g, types) for g in sorted(task.get("goals") or [],
                                                       key=lambda g: g.get("seq") or 0)]
    summary = task_summary(task, client.base, now)
    check = join_check(task, vault, now)
    summary.update({
        "open_for_entries": check["can_join_now"],
        "description": task.get("description"),
        "steps": steps,
        "caution": detail_cautions(task, types),
        "winner_count": task.get("winnerCount"),
        "submitters": task.get("participantCount"),
        "submitter_cap": task.get("maxParticipants"),
        **check,
        "pool": None,
        "requester_wallet": task.get("protocolPublisherWallet"),
        "award_deadline": task.get("protocolAwardDeadline"),
        "warnings": warnings,
        "next_step": ("To join or submit, sign in with the Finch CLI and Remote MCP as this Skill "
                      "describes (references/task.md: task_market_task_join, then task_market_task_submit) "
                      "or open the url. A requester cannot join their own Task."),
    })
    if vault:
        chain = task.get("protocolChainId")
        tx = task.get("protocolCreateTxHash")
        explorer = EXPLORERS.get(chain)
        summary["pool"] = {
            "currency": task.get("rewardCurrency"),
            "deposited": decimal_text(vault.get("deposited")),
            "paid_out": decimal_text(vault.get("paid")),
            "refunded": decimal_text(vault.get("refunded")),
            "available": decimal_text(vault.get("available")),
            "chain_id": chain,
            "vault_address": task.get("protocolVaultAddress"),
            "funding_tx": f"{explorer}/tx/{tx}" if explorer and tx else tx,
        }
    return summary


# ---------------------------------------------------------------- skills

CHAIN_NAMES = {1: "Ethereum", 8453: "Base", 56: "BNB Chain", 43114: "Avalanche", 137: "Polygon",
               42161: "Arbitrum One", 10: "Optimism", 1776: "Injective"}
AVAILABILITY_BADGES = ("Available", "Unavailable")
SKILL_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")
WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
# Why a wallet holds a legacy Skill: its creator holds token 0 and can open it without buying a licence.
LEGACY_GROUNDS = {"creator": "creator", "holder": "buyer"}


def skill_locales(card: dict) -> dict:
    return ((card.get("skillLocalization") or {}).get("locales")) or {}


def skill_price(card: dict) -> dict | None:
    """Price of one acquisition in the chain's native token; network fees are extra."""
    price = card.get("price") or {}
    if price.get("atomic") is None:
        return None
    atomic = int(price["atomic"])
    token = (price.get("currency") or "unknown token", int(price.get("decimals") or 18))
    return {**money(atomic, token), "free": atomic == 0}


def skill_url(base: str, slug: str) -> str:
    return f"{base}/market/chips/{urllib.parse.quote(slug)}"


def badges_known(card: dict) -> bool:
    """Every projected card carries Available or Unavailable. A card without either (a changed badge
    wording, or Finch's direct chain read of a legacy Skill) cannot say whether it is available."""
    return any(b in AVAILABILITY_BADGES for b in card.get("badges") or [])


def access_of(card: dict) -> str | None:
    """Finch's `plaintext` (ADR-0169): true when the package is readable after download. Null or
    absent means Finch cannot tell, which is unknown, not protected."""
    plaintext = card.get("plaintext")
    return None if plaintext is None else ("public" if plaintext else "protected")


def skill_record(card: dict, base: str) -> dict:
    ref = card.get("v3SkillRef") or card.get("legacyChipRef") or {}
    badges = card.get("badges") or []
    known = badges_known(card)
    activity = card.get("marketActivity") or {}
    flags = card.get("cardBadges") or {}
    name = (card.get("name") or "").strip()
    name_zh = (skill_locales(card).get("zh") or {}).get("name")
    return {
        "slug": card.get("slug"),
        "name": name,
        "name_zh": name_zh if name_zh and name_zh != name else None,
        "category": card.get("category"),
        "summary": clip(card.get("summary"), 300),
        "price": skill_price(card),
        "chain": CHAIN_NAMES.get(ref.get("chainId"), ref.get("chainId")),
        "chain_id": ref.get("chainId"),
        "protocol": card.get("source"),
        "version": (card.get("v3SkillRef") or {}).get("version"),
        "access": access_of(card),
        "available": ("Available" in badges) if known else None,
        "verified_downloads": activity.get("verifiedDownloads"),
        "primary_purchases": activity.get("primaryPurchases"),
        "audits": [label for key, label in (("certik", "CertiK"), ("slowmist", "SlowMist")) if flags.get(key)],
        "curated": bool(flags.get("curated")),
        "highly_rated": bool(flags.get("highlyRated")),
        "creator_wallet": card.get("creator"),
        "url": skill_url(base, card.get("slug") or ""),
    }


def cmd_skills(client: Client, args) -> dict:
    """One search request; Finch matches, filters and orders the Skills."""
    warnings: list[str] = []
    params = {"q": args.query, "category": args.category,
              "price": None if args.price == "any" else args.price,
              "access": None if args.access == "any" else args.access,
              "sort": args.sort, "cursor": args.cursor}
    page = client.get("/api/skills/catalog", params)
    items = page.get("items") or []
    results = [skill_record(card, client.base) for card in items[:args.limit]]
    for rank, record in enumerate(results, 1):
        record["rank"] = rank
    unknown = sum(1 for r in results if r["access"] is None or r["available"] is None)
    if unknown:
        warnings.append(f"For {unknown} Skill(s), Finch does not say whether they are public or available; "
                        "check their pages before saying how to get them.")
    data = {
        "query": args.query,
        "filters": {k: v for k, v in params.items() if v is not None and k != "cursor"},
        "total_matches": page.get("totalCount"),
        "page_items": len(items),
        "returned": len(results),
        "beyond_limit": len(items) - len(results),
        "next_cursor": page.get("nextCursor"),
        "skills": results,
        "warnings": warnings,
    }
    if not items:
        data["hint"] = ("Finch found no Skill. Retry once with other words, such as the tool's English name, a "
                        "platform or a file format, or in the user's language, or browse a --category; say so if "
                        "nothing fits." if args.query else "No Skill matches these filters.")
    return data


def skill_slug(value: str) -> str:
    text = (value or "").strip()
    path = urllib.parse.urlparse(text).path if "://" in text or text.startswith("/") else text
    if "/market/" in path:
        parts = [p for p in path.split("/") if p and p not in ("run", "manage")]
        text = urllib.parse.unquote(parts[-1]) if parts else ""
    if not SKILL_SLUG_RE.match(text):
        raise FinchError("INVALID_INPUT", f"No Skill slug found in {value!r}; pass the slug or the Skill page URL.")
    return text


def cmd_skill(client: Client, args) -> dict:
    slug = skill_slug(args.slug)
    warnings: list[str] = []
    page = client.get("/api/skills/catalog", {"q": slug})
    card = next((c for c in page.get("items") or [] if c.get("slug") == slug), None)
    if card is None:
        # No anonymous read looks a Skill up by slug, so search is the only way in; do not guess why it missed.
        raise FinchError("NOT_FOUND", f"Finch's Skill search returned no Skill with slug {slug!r}; it may be "
                         f"outside what search covers. Its page, if it exists: {skill_url(client.base, slug)}")
    record = skill_record(card, client.base)
    if record["access"] is None or record["available"] is None:
        warnings.append("Finch does not say whether this Skill is public or available; check its page before "
                        "saying how to get it.")
    v3, legacy = card.get("v3SkillRef"), card.get("legacyChipRef") or {}
    if v3:
        try:
            resolved = client.get("/api/skills/resolve", {"chainId": v3["chainId"], "skillId": v3["skillId"]})
            record["version"] = resolved.get("currentVersion") or record["version"]
        except FinchError as exc:
            warnings.append(f"Current version unavailable ({exc.code}); showing the listed version.")
        review_params = {"protocol": "v3", "chainId": v3["chainId"], "skillId": v3["skillId"],
                         "version": record["version"]}
    else:
        review_params = {"protocol": "legacy", "chainId": legacy.get("chainId"), "address": legacy.get("address")}
    try:
        reviews = client.get("/api/skills/reviews", {**review_params, "perPage": args.reviews})
    except FinchError as exc:
        warnings.append(f"Reviews unavailable ({exc.code}); rating unknown.")
        reviews = None
    locales = skill_locales(card)
    source_locale = (card.get("skillLocalization") or {}).get("sourceLocale") or "en"
    presentation = (locales.get(source_locale) or locales.get("en") or {}).get("presentation") or {}
    summary = (reviews or {}).get("summary") or {}
    if reviews is None:
        rating = None
    elif not summary.get("reviewCount"):
        rating = {"average": None, "count": 0}
    else:
        rating = {"average": summary.get("averageRating"), "count": summary.get("reviewCount"),
                  "runs_without_help": summary.get("averageOperationalIndependence"),
                  "output_quality": summary.get("averageOutputQuality"),
                  "model_compatibility": summary.get("averageModelCompatibility")}
    record.update({
        "description": presentation.get("description") or card.get("summary"),
        "tags": presentation.get("tags") or [],
        "steps": presentation.get("steps") or [],
        "parameters": presentation.get("parameters") or [],
        "example_input": presentation.get("exampleInput"),
        "demo_video_url": presentation.get("demoVideoURL"),
        "release_notes": (presentation.get("releaseNotes") or [])[:3],
        "rating": rating,
        "latest_reviews": [{"rating": r.get("overallRating"), "text": clip(r.get("body"), 400),
                            "date": utc_text(r.get("createdAt"))} for r in (reviews or {}).get("reviews") or []],
        "warnings": warnings,
        "next_step": ("A public Skill needs no purchase but downloading it needs a signed-in Finch CLI; a protected "
                      "Skill must be acquired on chain first, even at price zero. Follow references/skill.md, or open "
                      "the url."),
    })
    return record


def sync_issues(total: dict, freshness) -> list[tuple[str, str]]:
    """Why Finch does not count a chain's purchase totals as synced, from the fields it decides by."""
    if (total.get("coveredThrough") is None and total.get("coverageLagSeconds") is None
            and total.get("liveProgressLagSeconds") is None):
        return [("not_started", "indexing has not started")]  # neither behind nor stalled: never counted
    issues = []
    if total.get("historyComplete") is not True:
        issues.append(("history_not_backfilled", "earlier purchases not fully backfilled"))
    if total.get("liveComplete") is not True:
        issues.append(("live_streams_incomplete", "live indexing incomplete"))
    limit = f"; Finch allows {freshness} s" if freshness is not None else ""
    for key, code, what in (("coverageLagSeconds", "counts_behind", "counted only up to"),
                            ("liveProgressLagSeconds", "indexer_stalled", "indexer last moved")):
        lag = total.get(key)
        if lag is None:
            issues.append((code, f"{what} an unknown time ago"))
        elif freshness is None or lag > freshness:
            issues.append((code, f"{what} {lag} s ago{limit}"))
    return issues or [("not_indexed", "not indexed, no reason given")]


def cmd_holdings(client: Client, args) -> dict:
    """Skills a wallet holds and what it paid, from public chain-derived reads. Anyone can look up
    any address, so this shows holdings, not that the user controls the wallet."""
    wallet = (args.wallet or "").strip()
    if not WALLET_RE.match(wallet):
        raise FinchError("INVALID_INPUT", f"{wallet!r} is not a wallet address (0x followed by 40 hex digits).")
    warnings: list[str] = []
    v3 = client.get("/api/skills/holdings", {"wallet": wallet})
    if v3.get("verificationUnavailable"):
        warnings.append("Some recent purchases could not be verified yet; holdings may be incomplete.")
    try:
        legacy = client.get("/api/legacy/holdings", {"wallet": wallet}).get("owned") or []
    except FinchError as exc:
        warnings.append(f"Legacy holdings unavailable ({exc.code}).")
        legacy = None
    try:
        cost = client.get("/api/skills/purchase-cost", {"wallet": wallet})
    except FinchError as exc:
        warnings.append(f"Purchase totals unavailable ({exc.code}).")
        cost = None
    totals = cost.get("totals") if isinstance(cost, dict) else None
    if cost is not None and (not isinstance(totals, list) or not totals):
        # Finch answers with one entry per configured chain; anything else is a failed read, not "no purchases".
        warnings.append("Purchase totals unavailable (Finch returned no per-chain totals).")
        totals = None
    coverage = cost.get("coverage") if isinstance(cost, dict) else None
    freshness = coverage.get("freshnessSeconds") if isinstance(coverage, dict) else None
    owned = v3.get("owned") or []
    skills = [{
        "name": h.get("name"),
        "slug": h.get("slug"),
        "chain": CHAIN_NAMES.get(h.get("chainId"), h.get("chainId")),
        "version_held": h.get("version"),
        "current_version": h.get("currentVersion"),
        "newer_version_available": bool(h.get("stale")),
        "copies": h.get("balance"),
        "access": "public" if h.get("plaintext") else "protected",
        "url": skill_url(client.base, h.get("slug") or ""),
    } for h in owned]
    legacy_skills = None if legacy is None else [{
        "name": h.get("name"),
        "slug": h.get("slug"),
        "chain": CHAIN_NAMES.get(h.get("chainId"), h.get("chainId")),
        "held_as": LEGACY_GROUNDS.get(h.get("grounds"), h.get("grounds")),
        "licences": h.get("licences"),
        "deliverable": h.get("deliverable"),
        "url": skill_url(client.base, h.get("slug") or ""),
    } for h in legacy]
    purchases = None
    if totals is not None:
        # Finch returns every configured chain, zeros included, because only its sync state says
        # whether a zero or a total can be believed. Anything short of `indexed: true` is unknown.
        purchases, syncing, unpriced = [], [], []
        for t in totals:
            chain = t.get("chainName") or CHAIN_NAMES.get(t.get("chainId"), t.get("chainId"))
            complete = t.get("indexed") is True
            issues = [] if complete else sync_issues(t, freshness)
            if not complete:
                syncing.append(f"{chain} ({'; '.join(text for _, text in issues)})")
            elif t.get("purchases") == 0:
                continue  # a synced chain with no purchases adds nothing; a missing count is still shown
            if t.get("unpricedPurchases"):
                unpriced.append(f"{t.get('unpricedPurchases')} on {chain}")
            purchases.append({
                "chain": chain,
                "purchases": t.get("purchases"),
                "total_paid": money(t.get("totalPaidAtomic"), (t.get("currency"), int(t.get("decimals") or 18))),
                "unpriced_purchases": t.get("unpricedPurchases"),
                "complete": complete,
                "sync_issues": [code for code, _ in issues],
                "indexed_through": t.get("coveredThrough"),
                "lag_seconds": t.get("coverageLagSeconds"),
                "history_complete": t.get("historyComplete"),
                "live_complete": t.get("liveComplete"),
            })
        if syncing:
            warnings.append(f"Purchase totals are not fully synced on {', '.join(syncing)} (complete: false): "
                            "their counts and amounts may be too low, and a zero there means unknown, not none.")
        if unpriced:
            warnings.append(f"Purchases without a recorded price ({', '.join(unpriced)}) are counted in "
                            "`purchases` but left out of `total_paid`, so that total is a lower bound.")
    # A publisher's wallet can hold hundreds of its own legacy Skills; list the bought ones first and
    # keep the counts over everything, so a cut list never changes the numbers.
    summary = {"skills": {"total": len(skills), "by_chain": dict(Counter(s["chain"] for s in skills)),
                          "newer_version_available": sum(s["newer_version_available"] for s in skills)}}
    if legacy_skills is not None:
        legacy_skills.sort(key=lambda s: s["held_as"] != "buyer")
        summary["legacy_skills"] = {"total": len(legacy_skills),
                                    "by_held_as": dict(Counter(s["held_as"] for s in legacy_skills)),
                                    "by_chain": dict(Counter(s["chain"] for s in legacy_skills)),
                                    "not_deliverable": sum(s["deliverable"] is False for s in legacy_skills)}
    start, end = args.offset, args.offset + args.limit
    longest = max(len(skills), len(legacy_skills or []))
    truncated = start > 0 or longest > end
    if truncated:
        warnings.append(f"Lists show entries {start + 1} to {min(end, longest)} of up to {longest} (bought legacy "
                        "Skills first); `summary` counts all of them, so answer counts from it. Page with --offset "
                        "next_offset only when the user asks for the full list.")
    return {
        "wallet": wallet,
        "summary": summary,
        "truncated": truncated,
        "next_offset": end if longest > end else None,
        "skills": skills[start:end],
        "legacy_skills": None if legacy_skills is None else legacy_skills[start:end],
        "purchase_totals": purchases,
        "warnings": warnings,
        "notes": ["Public chain data: anyone can read any address, so this does not show that the user "
                  "controls the wallet. Agent Call Rights, free calls and Task participation are per Finch "
                  "Account and need sign-in (references/agent.md, references/task.md)."],
    }


# ---------------------------------------------------------------- CLI

def positive_int(maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not 1 <= number <= maximum:
            raise argparse.ArgumentTypeError(f"must be between 1 and {maximum}")
        return number
    return parse


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return number


def page_number(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return number


def search_query(value: str) -> str:
    """Finch's searches trim the query and refuse one longer than 200 characters, so a longer one
    is refused here, before any request, instead of being shortened."""
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("is empty; leave --query out to browse")
    if len(text.encode("utf-16-le")) // 2 > MAX_QUERY_CHARS:
        raise argparse.ArgumentTypeError(f"is longer than Finch search accepts ({MAX_QUERY_CHARS} characters)")
    return text


def market_category(value: str) -> str:
    """Finch compares the whole website category name, ignoring case; an empty one would match nothing useful."""
    text = value.strip()
    if not text:
        raise argparse.ArgumentTypeError("is empty; leave --category out for every category")
    return text


def agent_query(value: str) -> str:
    """Agent search counts UTF-8 bytes after NFC, so about 66 Chinese characters is the most it takes."""
    text = search_query(value)
    if len(unicodedata.normalize("NFC", text).encode("utf-8")) > MAX_AGENT_QUERY_BYTES:
        raise argparse.ArgumentTypeError(f"is longer than Finch's Agent search accepts ({MAX_AGENT_QUERY_BYTES} "
                                         "UTF-8 bytes, about 66 Chinese characters)")
    return text


def build_parser() -> Parser:
    parser = Parser(prog="finch_discover.py", description=DESCRIPTION)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)

    agents = commands.add_parser("agents", help="Search Agents; Finch matches and orders them.")
    agents.add_argument("--query", "-q", type=agent_query, help="A few topic words in one language.")
    agents.add_argument("--limit", type=positive_int(WEBSITE_PAGE_SIZE), default=5,
                        help="Most Agents returned from the page of up to 50 Finch sends.")
    agents.add_argument("--cursor", help="next_cursor of an earlier run with the same query and filters.")
    agents.add_argument("--category", type=market_category,
                        help="Whole website category name, e.g. 'Finance & Tax'; case does not matter, but part of a "
                             "name ('finance') finds nothing. Finch applies it.")
    agents.add_argument("--free-trial", action="store_true",
                        help="Only Agents Finch marks Free: the Agent's shared free calls are not used up today; not the "
                             "user's own remaining calls (Finch applies it).")
    agents.add_argument("--max-price", type=float,
                        help="Highest allowed price (inclusive) of the cheapest way to call, per its own unit "
                             "(applied to the returned page).")
    agents.add_argument("--integration", choices=["agenton_v2", "direct_api_v1"],
                        help="Applied to the returned page.")
    agents.add_argument("--audited", action="store_true",
                        help="Only Agents with a passed audit (applied to the returned page).")
    agents.add_argument("--include-offline", action="store_true",
                        help="Keep Agents not accepting requests, which are otherwise dropped from the page.")

    agent = commands.add_parser("agent", help="Show one Agent in depth.")
    agent.add_argument("id", help="serviceVersionId or Agent page URL.")
    agent.add_argument("--reviews", type=positive_int(10), default=3)

    tasks = commands.add_parser("tasks", help="Browse reward Tasks in Finch's order.")
    tasks.add_argument("--query", "-q", type=search_query, help="A few words matched by Finch's Task search.")
    tasks.add_argument("--limit", type=positive_int(100), default=10, help="Page size Finch returns.")
    tasks.add_argument("--page", type=page_number, default=1, help="next_page of an earlier run.")
    tasks.add_argument("--section", choices=["active", "ended"], default="active")
    tasks.add_argument("--when", choices=["all", "active", "upcoming", "ended"], default="all")
    tasks.add_argument("--sort", choices=["latest", "hot", "top", "relevance"],
                       help="Finch's order. Default: relevance with --query, latest without.")
    tasks.add_argument("--category", choices=["twitter", "activity", "content", "feedback", "custom"])
    tasks.add_argument("--model", choices=["competition", "collaborative"])
    tasks.add_argument("--min-reward", type=float, help="Minimum total reward pool (applied to the page).")
    tasks.add_argument("--min-per-entry", type=float, help="Minimum reward per entry (applied to the page).")
    tasks.add_argument("--no-x", action="store_true",
                       help="Exclude Tasks that need an X account (applied to the page; rechecked against the "
                            "steps with --joinable).")
    tasks.add_argument("--joinable", action="store_true",
                       help="Only Tasks a new account can join now (applied to the page); loads each "
                            "candidate's detail.")

    task = commands.add_parser("task", help="Show one Task in depth.")
    task.add_argument("id", help="Task ID or Task page URL.")

    skills = commands.add_parser("skills", help="Search Skills; Finch matches and orders them.")
    skills.add_argument("--query", "-q", type=search_query, help="A few topic words in one language.")
    skills.add_argument("--limit", type=positive_int(WEBSITE_PAGE_SIZE), default=10,
                        help="Most Skills returned from the page of up to 50 Finch sends.")
    skills.add_argument("--cursor", help="next_cursor of an earlier run with the same query and filters.")
    skills.add_argument("--price", choices=["any", "free", "paid"], default="any")
    skills.add_argument("--access", choices=["any", "public", "protected"], default="any",
                        help="public: readable package; protected: encrypted, delivered to holders.")
    skills.add_argument("--category", type=market_category,
                        help="Whole website category name, e.g. 'Finance & Tax'; case does not matter, but part of a "
                             "name ('finance') finds nothing.")
    skills.add_argument("--sort", choices=["relevance", "recent", "price"],
                        help="Finch's order. Default: relevance with --query, recent without. price: lowest listed "
                             "number first, whatever the currency.")

    skill = commands.add_parser("skill", help="Show one Skill in depth.")
    skill.add_argument("slug", help="Skill slug or Skill page URL.")
    skill.add_argument("--reviews", type=positive_int(10), default=3)

    holdings = commands.add_parser("holdings", help="Skills a wallet holds and what it paid (public chain data).")
    holdings.add_argument("wallet", help="Wallet address, 0x followed by 40 hex digits.")
    holdings.add_argument("--limit", type=positive_int(200), default=50,
                          help="Most entries listed per list; summary counts always cover all.")
    holdings.add_argument("--offset", type=non_negative_int, default=0,
                          help="Entries to skip in each list, for paging with next_offset.")
    return parser


def base_url() -> str:
    value = os.environ.get("FINCH_BASE_URL", DEFAULT_BASE_URL).strip()
    if not re.match(r"^https://([a-z0-9-]+\.)*finchtech\.ai(:\d+)?/?$"
                    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?/?$", value, re.IGNORECASE):
        raise FinchError("INVALID_INPUT",
                         "FINCH_BASE_URL must be https://finchtech.ai or a subdomain, or local http.")
    return value


COMMANDS = {"agents": cmd_agents, "agent": cmd_agent, "tasks": cmd_tasks, "task": cmd_task,
            "skills": cmd_skills, "skill": cmd_skill, "holdings": cmd_holdings}


def write_envelope(envelope: dict, stream=None) -> None:
    """Write the whole envelope as UTF-8, whatever the console or pipe encoding.

    Windows pipes default to a legacy code page such as cp1252, which cannot encode the Chinese
    names in Finch's catalog. Serializing first also means a failure can never leave half a JSON.
    """
    stream = sys.stdout if stream is None else stream
    text = json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"
    buffer = getattr(stream, "buffer", None)
    if buffer is None:  # an in-memory text stream such as io.StringIO takes str directly
        stream.write(text)
        return
    stream.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def main(argv: list[str] | None = None) -> int:
    envelope = {"ok": False, "skill": SKILL, "helper": HELPER, "version": VERSION, "command": None,
                "fetched_at": now_utc().isoformat(timespec="seconds").replace("+00:00", "Z")}
    try:
        args = build_parser().parse_args(argv)
        envelope["command"] = args.command
        data = COMMANDS[args.command](Client(base_url()), args)
        envelope.update(ok=True, data=data)
    except FinchError as exc:
        envelope["error"] = {"code": exc.code, "message": exc.message}
    except Exception as exc:  # never leak a traceback into the agent's context
        envelope["error"] = {"code": "INTERNAL_ERROR", "message": f"Unexpected {type(exc).__name__}."}
    write_envelope(envelope)
    return 0 if envelope["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
