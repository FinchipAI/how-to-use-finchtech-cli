"""Inputs: Synthetic Agent cards, Skill cards, Task rows and details standing in for Finch's public read APIs.
Outputs: Offline assertions for the no-sign-in discovery helper's requests, pricing, Task checks and envelope.
Role: Guards scripts/finch_discover.py without network access: each search command sends one request and keeps Finch's order.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import finch_discover as fd  # noqa: E402

USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)
STOCK = "\u7f8e\u80a1"      # "US stocks" in Chinese
ANALYSIS = "\u5206\u6790"   # "analysis" in Chinese
OFFER = "99999999-9999-4999-8999-999999999999"


def iso(delta_days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=delta_days)).isoformat().replace("+00:00", "Z")


def service(vid, name, description, unit="10000"):
    """A v1 catalog service, the base of an Agent detail."""
    return {
        "serviceVersionId": vid, "integrationFamily": "agenton_v2", "displayName": name,
        "description": description, "seller": "0x" + "1" * 40, "paymentToken": USDC,
        "unitPriceAtomic": unit, "availability": {"status": "online", "acceptingRequests": True},
        "slowmistAuditStatus": "passed", "promotional": None,
        "localization": {"source": {"name": name, "description": description}, "input": {"translations": {}}},
    }


def detail_for(svc, units="1", mode="task"):
    return {**svc, "chainId": 8453, "offers": [{
        "offerId": "o-" + svc["serviceVersionId"], "displayName": "Offer", "interactionMode": mode,
        "callRightUnits": units, "minQuantity": "1", "maxQuantity": "1", "maxDurationSeconds": 60,
        "inputSchema": {"type": "object", "required": ["content"], "properties": {"content": {
            "type": "array", "items": {"oneOf": [{"properties": {"type": {"const": "text"}}}]}}}},
        "artifactContract": {"count": {"minItems": 1, "maxItems": 2}, "allowedMediaTypes": ["text/csv"]},
    }]}


def call_option(mode="task", units=1, unit=10000, min_quantity=1, max_quantity=1):
    return {"offerId": None if mode is None else OFFER, "interactionMode": mode, "callRightUnits": str(units),
            "minQuantity": str(min_quantity), "maxQuantity": str(max_quantity), "priceAtomic": str(unit * units)}


def agent_card(vid, name, summary, unit=10000, options="one", zh_name=None, promo=None, accepting=True,
               integration="agenton_v2", audit="passed", category="Finance & Tax"):
    """A website Agent card as /api/market/search returns it, with ADR-0169 call options."""
    translations = {"zh": {"name": zh_name, "description": ""}} if zh_name else {}
    ref = {"serviceVersionId": vid, "integrationFamily": integration, "versionRevision": 1,
           "publicationGeneration": "1", "chainId": 8453, "slowmistAuditStatus": audit, "slowmistAuditReport": None,
           "availability": {"status": "online" if accepting else "offline", "acceptingRequests": accepting,
                            "checkedAt": None},
           "promotional": promo,
           "localization": {"source": {"name": name, "description": summary}, "status": "complete", "revision": 1,
                            "input": {"inputLocales": ["en"], "translations": translations}}}
    if options is not None:
        ref["callOptions"] = [call_option(unit=unit)] if options == "one" else options
    return {"id": f"agent-market:{vid}", "slug": f"agent-{vid}", "kind": "agent", "source": "agent-market",
            "agentMarketRef": ref, "name": name, "category": category, "summary": summary,
            "price": {"atomic": str(unit), "decimals": 6, "currency": "USDC"}, "badges": ["Finch Agent", "Online"]}


class FakeClient:
    """Records each request as (path, params) with unset parameters left out, as Client sends them."""
    base = "https://example.test"

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, path, params=None):
        sent = {k: v for k, v in (params or {}).items() if v is not None}
        self.calls.append((path, sent))
        if path not in self.routes:
            raise fd.FinchError("NOT_FOUND", path)
        value = self.routes[path]
        return value(sent) if callable(value) else value

    def paths(self):
        return [path for path, _ in self.calls]


def agents_args(**overrides):
    base = dict(query=None, limit=5, cursor=None, max_price=None, category=None, integration=None,
                free_trial=False, audited=False, include_offline=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def tasks_args(**overrides):
    base = dict(query=None, limit=10, page=1, section="active", when="all", sort=None, category=None,
                model=None, min_reward=None, min_per_entry=None, no_x=False, joinable=False)
    base.update(overrides)
    return argparse.Namespace(**base)


class Formatting(unittest.TestCase):
    def test_decimal_text(self):
        self.assertEqual(fd.decimal_text("3000.000000000000000000"), "3000")
        self.assertEqual(fd.decimal_text("0.015000"), "0.015")
        self.assertEqual(fd.decimal_text(5), "5")
        self.assertIsNone(fd.decimal_text("abc"))

    def test_money_uses_known_token_decimals(self):
        self.assertEqual(fd.money("1500000", fd.token_for(USDC)), {"amount": "1.5", "currency": "USDC"})
        self.assertEqual(fd.money("7", None)["currency"], "unknown token")

    def test_time_left(self):
        self.assertEqual(fd.time_left(NOW + timedelta(days=2, hours=3), NOW), "2d 3h")
        self.assertEqual(fd.time_left(NOW + timedelta(minutes=90), NOW), "1h 30m")
        self.assertEqual(fd.time_left(NOW - timedelta(seconds=1), NOW), "ended")

    def test_parse_time_accepts_five_fraction_digits(self):
        # Python 3.9 and 3.10 reject these unless the fraction is padded.
        self.assertEqual(fd.parse_time("2026-10-10T08:46:20.21406+00:00").microsecond, 214060)
        self.assertEqual(fd.parse_time("2026-10-12T02:28:12.203Z").microsecond, 203000)
        self.assertIsNone(fd.parse_time("not a time"))

    def test_extract_uuid_from_url(self):
        url = "https://www.finchtech.ai/market/chips/agent-E96E9A01-50aa-4686-bd0e-1aa9cdfcf967/run"
        self.assertEqual(fd.extract_uuid(url), "e96e9a01-50aa-4686-bd0e-1aa9cdfcf967")
        with self.assertRaises(fd.FinchError):
            fd.extract_uuid("not-an-id")


class Pricing(unittest.TestCase):
    def test_offer_price_multiplies_call_right_units(self):
        svc = service("a", "A", "d", unit="500000")
        options = fd.price_options(detail_for(svc, units="3"), fd.token_for(USDC))
        self.assertEqual(options[0]["price"], {"amount": "1.5", "currency": "USDC"})
        self.assertEqual(options[0]["per"], "task run")
        self.assertEqual(options[0]["input"]["message_parts"], ["text"])
        self.assertEqual(options[0]["output"], {"attachments": "1-2", "allowed_types": ["CSV"]})

    def test_direct_price_and_input(self):
        detail = {"integrationFamily": "direct_api_v1", "unitPriceAtomic": "9900000", "callRightUnits": "1",
                  "inputSchema": {"type": "object", "required": ["prompt"],
                                  "properties": {"prompt": {"type": "string"}}},
                  "artifactContract": {"count": {"minItems": 0, "maxItems": 0}}}
        option = fd.price_options(detail, fd.token_for(USDC))[0]
        self.assertEqual((option["price"]["amount"], option["per"]), ("9.9", "call"))
        self.assertEqual(option["input"]["fields"], {"prompt": "string"})
        self.assertEqual(option["output"], {"attachments": "none"})

    def test_empty_input_schema_is_reported_as_unconstrained(self):
        self.assertIn("any JSON", fd.summarize_input({})["accepts"])


class AgentsCommand(unittest.TestCase):
    STOCK_ID = "11111111-1111-4111-8111-111111111111"

    def setUp(self):
        self.stock = agent_card(self.STOCK_ID, "Stock Desk", "US stock analysis", zh_name=STOCK + ANALYSIS,
                                promo={"grantOperations": "10", "expiresAt": iso(5)})
        self.homes = agent_card("22222222-2222-4222-8222-222222222222", "Home Analyst", "Property analysis",
                                unit=2000000)
        self.offline = agent_card("33333333-3333-4333-8333-333333333333", "Stock Bot", "stock", accepting=False)
        self.cards = [self.homes, self.stock, self.offline]
        self.client = FakeClient({"/api/market/search": lambda params: {
            "items": self.cards, "nextCursor": "next-1", "totalCount": 7}})

    def names(self, data):
        return [a["name"] for a in data["agents"]]

    def test_sends_one_search_request_with_the_filters_finch_applies(self):
        data = fd.cmd_agents(self.client, agents_args(query="stock analysis", category="Finance & Tax",
                                                      free_trial=True, cursor="c-1"))
        self.assertEqual(self.client.calls, [("/api/market/search", {
            "kind": "agent", "q": "stock analysis", "category": "Finance & Tax", "price": "free", "cursor": "c-1"})])
        self.assertEqual(data["filters"], {"q": "stock analysis", "category": "Finance & Tax", "price": "free"})

    def test_browsing_without_a_query_sends_only_the_kind(self):
        data = fd.cmd_agents(self.client, agents_args())
        self.assertEqual(self.client.calls, [("/api/market/search", {"kind": "agent"})])
        self.assertEqual((data["filters"], data["post_filters"]), ({}, {"accepting_requests": True}))

    def test_keeps_finch_order(self):
        # Locally "Stock Desk" would win a "stock analysis" query; Finch's order decides.
        data = fd.cmd_agents(self.client, agents_args(query="stock analysis"))
        self.assertEqual(self.names(data), ["Home Analyst", "Stock Desk"])
        self.assertEqual([a["rank"] for a in data["agents"]], [1, 2])
        self.assertNotIn("match", data["agents"][0])

    def test_records_from_the_card(self):
        record = fd.cmd_agents(self.client, agents_args())["agents"][1]
        self.assertEqual((record["name_zh"], record["category"], record["security_audit"]),
                         (STOCK + ANALYSIS, "Finance & Tax", "passed"))
        self.assertEqual(record["free_trial"]["free_calls_per_account"], 10)
        # Free-call V1.1: the listing date is the window for an account registering now.
        self.assertIn("new_account_valid_until", record["free_trial"])
        self.assertEqual(record["url"], f"https://example.test/market/chips/agent-{self.STOCK_ID}")

    def test_prices_come_from_call_options(self):
        self.stock["agentMarketRef"]["callOptions"] = [
            call_option("conversation_turn", units=3, unit=500000),
            call_option("generation", units=1, unit=200000, min_quantity=2, max_quantity=10),
        ]
        self.homes["agentMarketRef"]["callOptions"] = [call_option(None, units=2, unit=2000000)]
        homes, stock = fd.cmd_agents(self.client, agents_args())["agents"]
        self.assertEqual(stock["price_from"], {"amount": "0.2", "currency": "USDC", "per": "generated item"})
        turn, generation = stock["call_options"]
        self.assertEqual((turn["price"], turn["per"], turn["offer_id"]),
                         ({"amount": "1.5", "currency": "USDC"}, "conversation turn", OFFER))
        self.assertEqual((generation["quantity_range"], generation["minimum_spend"]),
                         ([2, 10], {"amount": "0.4", "currency": "USDC"}))
        self.assertEqual(homes["call_options"], [{"offer_id": None, "mode": "direct_call",
                                                  "price": {"amount": "4", "currency": "USDC"}, "per": "call"}])

    def test_post_filters_run_on_the_page_and_report_every_exclusion(self):
        good = agent_card("44444444-4444-4444-8444-444444444444", "Good", "fits")
        direct = agent_card("55555555-5555-4555-8555-555555555555", "Direct", "d", integration="direct_api_v1")
        unaudited = agent_card("66666666-6666-4666-8666-666666666666", "Unaudited", "u", audit="in_progress")
        unpriced = agent_card("77777777-7777-4777-8777-777777777777", "Unpriced", "p", options=None)
        self.cards = [self.offline, direct, unaudited, self.homes, unpriced, good, self.stock]
        data = fd.cmd_agents(self.client, agents_args(integration="agenton_v2", audited=True, max_price=1, limit=1))
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(data["post_filters"], {"accepting_requests": True, "integration": "agenton_v2",
                                                "audited": True, "max_price": 1})
        self.assertEqual(data["excluded"], {
            "not_accepting_requests": ["Stock Bot"], "integration": ["Direct"], "not_audited": ["Unaudited"],
            "over_max_price": ["Home Analyst"], "price_unverified": ["Unpriced"]})
        self.assertEqual((self.names(data), data["beyond_limit"]), (["Good"], 1))
        accounted = data["returned"] + data["beyond_limit"] + sum(len(v) for v in data["excluded"].values())
        self.assertEqual(accounted, data["page_items"])

    def test_max_price_is_inclusive(self):
        data = fd.cmd_agents(self.client, agents_args(max_price=0.01))
        self.assertEqual((self.names(data), data["excluded"]["over_max_price"]), (["Stock Desk"], ["Home Analyst"]))

    def test_cards_without_call_options_are_unverified_and_said_so(self):
        del self.stock["agentMarketRef"]["callOptions"]
        data = fd.cmd_agents(self.client, agents_args())
        self.assertEqual(data["agents"][1]["price_from"], {"amount": "0.01", "currency": "USDC",
                                                           "per": "call right unit", "verified": False})
        self.assertIsNone(data["agents"][1]["call_options"])
        self.assertTrue(any("lower bound" in w for w in data["warnings"]))
        self.cards = [self.stock]
        data = fd.cmd_agents(self.client, agents_args(max_price=1))
        self.assertEqual((data["agents"], data["excluded"]["price_unverified"]), ([], ["Stock Desk"]))
        self.assertIn("could not be verified", data["hint"])

    def test_an_unverified_price_over_the_budget_is_over_budget(self):
        # The listing unit price is a lower bound, so a lower bound above --max-price is over budget for certain.
        del self.stock["agentMarketRef"]["callOptions"]  # unverified 0.01 USDC
        self.cards = [self.stock]
        data = fd.cmd_agents(self.client, agents_args(max_price=0.001))
        self.assertEqual(data["excluded"], {"not_accepting_requests": [], "over_max_price": ["Stock Desk"],
                                            "price_unverified": []})
        self.assertIn("over --max-price", data["hint"])

    def test_a_zero_max_price_is_a_real_limit(self):
        data = fd.cmd_agents(self.client, agents_args(max_price=0))
        self.assertEqual(data["post_filters"], {"accepting_requests": True, "max_price": 0})
        self.assertEqual((data["agents"], sorted(data["excluded"]["over_max_price"])),
                         ([], ["Home Analyst", "Stock Desk"]))

    def test_limit_cuts_the_page_and_keeps_finch_cursor(self):
        data = fd.cmd_agents(self.client, agents_args(limit=1, include_offline=True))
        self.assertEqual((data["returned"], data["beyond_limit"], data["page_items"]), (1, 2, 3))
        self.assertEqual((data["next_cursor"], data["total_matches"]), ("next-1", 7))
        self.assertEqual(data["excluded"], {})

    def test_hints(self):
        self.cards = []
        self.assertIn("Finch found no Agent", fd.cmd_agents(self.client, agents_args(query="legal"))["hint"])
        self.cards = [self.homes]
        self.assertIn("over --max-price", fd.cmd_agents(self.client, agents_args(max_price=1))["hint"])

    def test_agent_detail_and_unknown_rating(self):
        svc = service(self.STOCK_ID, "Stock Desk", "US stock analysis", unit="500000")
        path = f"/api/v1/agent-market/catalog/services/{self.STOCK_ID}"
        client = FakeClient({path: detail_for(svc, units="3"),
                             path + "/reviews": {"summary": {"reviewCount": 2, "averageRating": 4.5}, "reviews": []}})
        data = fd.cmd_agent(client, argparse.Namespace(id=self.STOCK_ID, reviews=3))
        self.assertEqual(data["price_from"], {"amount": "1.5", "currency": "USDC", "per": "task run"})
        self.assertEqual(data["rating"], {"average": 4.5, "count": 2})
        del client.routes[path + "/reviews"]
        data = fd.cmd_agent(client, argparse.Namespace(id=self.STOCK_ID, reviews=3))
        self.assertIsNone(data["rating"])
        self.assertTrue(data["warnings"])


class TasksCommand(unittest.TestCase):
    def task(self, **overrides):
        base = {
            "id": "44444444-4444-4444-8444-444444444444", "title": "Deposit into a vault",
            "description": "Connect your wallet and deposit", "goal": "Custom goal",
            "status": "open", "rewardAmount": "100.000000", "rewardCurrency": "USDC",
            "extraConfig": {"perSubmissionReward": 5, "targetCount": 3}, "confirmedCount": 0,
            "settlementMode": "weighted_lottery", "deadline": iso(3), "startAt": None,
            "requiresTwitter": False, "protocolPoolId": "p", "protocolChainId": 8453,
            "protocolCreateTxHash": "0xabc", "regionParticipationRestricted": False,
            "participationLimitReached": False, "participantCount": 2, "maxParticipants": 30,
            "goals": [{"seq": 0, "goalType": "x_follow", "required": True, "config": {"account": "finch"}}],
        }
        base.update(overrides)
        return base

    def summary(self, task, warnings=None):
        return fd.task_summary(task, "https://example.test", datetime.now(timezone.utc), warnings)

    def test_list_row_never_claims_open_without_the_detail(self):
        summary = self.summary(self.task())
        self.assertIsNone(summary["open_for_entries"])
        self.assertEqual(summary["winner_slots_left"], 3)
        self.assertEqual(len(summary["caution"]), 2)

    def test_list_row_rules_out_closed_full_capped_or_late_tasks(self):
        for overrides in ({"status": "judging"}, {"deadline": iso(-1)}, {"confirmedCount": 3},
                          {"participationLimitReached": True}):
            with self.subTest(**overrides):
                self.assertFalse(self.summary(self.task(**overrides))["open_for_entries"])
        # Null capacity means unknown, and a row without the fields (before ADR-0169) leaves it to the detail.
        self.assertIsNone(self.summary(self.task(participationLimitReached=None))["open_for_entries"])
        row = {k: v for k, v in self.task().items() if k not in ("participationLimitReached", "participantCount",
                                                                  "maxParticipants")}
        self.assertIsNone(self.summary(row)["open_for_entries"])
        self.assertNotIn("submitter_cap", self.summary(row))
        self.assertEqual((self.summary(self.task())["submitters"], self.summary(self.task())["submitter_cap"]),
                         (2, 30))

    def list_client(self, rows, has_more=False, details=()):
        routes = {"/api/tasks": {"items": rows, "total": len(rows) + 5, "hasMore": has_more}}
        routes.update({f"/api/tasks/{t['id']}": t for t in details})
        return FakeClient(routes)

    def test_sends_one_list_request_with_limit_as_page_size(self):
        client = self.list_client([self.task()], has_more=True)
        data = fd.cmd_tasks(client, tasks_args(query="follow", limit=7, page=2, sort="hot", model="competition"))
        self.assertEqual(client.calls, [("/api/tasks", {
            "section": "active", "sort": "hot", "taskStatus": "all", "q": "follow",
            "participationModel": "competition", "page": 2, "perPage": 7})])
        self.assertEqual((data["page"], data["next_page"], data["page_items"], data["total_visible"]), (2, 3, 1, 6))

    def test_sort_is_left_to_finch_by_default(self):
        client = self.list_client([])
        data = fd.cmd_tasks(client, tasks_args(query="follow"))
        self.assertEqual(client.calls, [("/api/tasks", {"section": "active", "taskStatus": "all", "q": "follow",
                                                        "page": 1, "perPage": 10})])
        self.assertIsNone(data["next_page"])
        self.assertIn("No Task", data["hint"])

    def test_keeps_finch_order(self):
        small = self.task(id="11111111-1111-4111-8111-111111111111", rewardAmount="5")
        big = self.task(id="22222222-2222-4222-8222-222222222222", rewardAmount="500")
        data = fd.cmd_tasks(self.list_client([small, big]), tasks_args(sort="top"))
        self.assertEqual([t["task_id"] for t in data["tasks"]], [small["id"], big["id"]])

    def test_missing_target_or_unreadable_deadline_is_unknown(self):
        check = fd.join_check(self.task(extraConfig={}), None, datetime.now(timezone.utc))
        self.assertIsNone(check["can_join_now"])
        check = fd.join_check(self.task(deadline="soon"), None, datetime.now(timezone.utc))
        self.assertIsNone(check["can_join_now"])

    def test_server_slots_are_used_and_drift_is_reported(self):
        warnings = []
        summary = self.summary(self.task(slotsRemaining=2, participationCount=40), warnings)
        self.assertEqual((summary["winner_slots_left"], summary["joined"]), (2, 40))
        self.assertEqual(len(warnings), 1)

    def test_x_requirement_also_comes_from_steps(self):
        self.assertTrue(fd.requirements_of(self.task(goals=[], goal="X follow + Visit a link"))["x_account"])
        self.assertTrue(fd.requirements_of(self.task())["x_account"])

    def test_joinable_loads_details_only_for_rows_the_list_cannot_rule_out(self):
        open_task = self.task(id="55555555-5555-4555-8555-555555555555", slotsRemaining=3)
        capped = self.task(id="66666666-6666-4666-8666-666666666666", slotsRemaining=3,
                           participationLimitReached=True, participantCount=60, maxParticipants=60)
        closed = self.task(id="77777777-7777-4777-8777-777777777777", status="judging", slotsRemaining=3)
        open_task["goals"].append({"seq": 1, "goalType": "custom", "required": True,
                                   "config": {"description": "Deposit 100 USDT"}})
        client = self.list_client([open_task, capped, closed], details=[open_task, capped, closed])
        data = fd.cmd_tasks(client, tasks_args(joinable=True))
        self.assertEqual(client.paths(), ["/api/tasks", f"/api/tasks/{open_task['id']}"])
        self.assertEqual([t["task_id"] for t in data["tasks"]], [open_task["id"]])
        self.assertEqual((data["excluded_by_list_check"], data["excluded_after_detail_check"]), (2, 0))
        self.assertTrue(data["tasks"][0]["can_join_now"])
        spends = [c for c in data["tasks"][0]["caution"] if c["flag"].startswith("Spends")]
        self.assertIn("Deposit 100 USDT", " ".join(spends[0]["context"]))  # from the step, not the list row
        self.assertEqual(self.accounted(data), data["page_items"])

    def test_joinable_detail_still_rules_out_caps_and_regions(self):
        # Rows without capacity (before ADR-0169) and the region restriction are left to the detail.
        capped = self.task(id="66666666-6666-4666-8666-666666666666", slotsRemaining=3,
                           participationLimitReached=True, participantCount=60, maxParticipants=60)
        region = self.task(id="88888888-8888-4888-8888-888888888888", slotsRemaining=3,
                           regionParticipationRestricted=True)
        rows = [{k: v for k, v in t.items() if k not in ("participationLimitReached", "participantCount",
                                                         "maxParticipants", "regionParticipationRestricted")}
                for t in (capped, region)]
        data = fd.cmd_tasks(self.list_client(rows, details=[capped, region]), tasks_args(joinable=True))
        ruled_out = {t["task_id"]: t["blockers"][0] for t in data["excluded_after_detail_check_tasks"]}
        self.assertIn("submitter cap", ruled_out[capped["id"]])
        self.assertIn("restricted in the region", ruled_out[region["id"]])
        self.assertEqual(self.accounted(data), data["page_items"])

    def accounted(self, data):
        return sum(data[k] for k in ("returned", "excluded_by_filters", "excluded_by_list_check",
                                     "excluded_after_detail_check", "unconfirmed"))

    def joinable_client(self, count, **row_overrides):
        tasks = [self.task(id=f"{i:08d}-8888-4888-8888-888888888888", slotsRemaining=3, **row_overrides)
                 for i in range(count)]
        return self.list_client([{k: v for k, v in t.items() if k != "goals"} for t in tasks], details=tasks)

    def test_joinable_checks_every_row_of_a_page_of_at_most_fifty(self):
        # Rows past the detail cap could be neither shown nor reached with next_page, so a larger page is refused.
        client = self.joinable_client(60)
        with self.assertRaises(fd.FinchError) as refused:
            fd.cmd_tasks(client, tasks_args(joinable=True, limit=fd.MAX_DETAIL_FETCHES + 1))
        self.assertEqual((refused.exception.code, client.calls), ("INVALID_INPUT", []))
        client = self.joinable_client(fd.MAX_DETAIL_FETCHES)
        data = fd.cmd_tasks(client, tasks_args(joinable=True, limit=fd.MAX_DETAIL_FETCHES))
        self.assertEqual(len(client.calls), 1 + fd.MAX_DETAIL_FETCHES)
        self.assertEqual(data["returned"], fd.MAX_DETAIL_FETCHES)
        self.assertNotIn("not_checked", data)
        self.assertEqual(self.accounted(data), data["page_items"])

    def test_a_zero_minimum_is_still_reported(self):
        data = fd.cmd_tasks(self.joinable_client(2, rewardAmount="10"), tasks_args(min_reward=0))
        self.assertEqual((data["post_filters"], data["excluded_by_filters"], data["returned"]),
                         ({"min_reward": 0}, 0, 2))

    def test_post_filters_are_reported(self):
        data = fd.cmd_tasks(self.joinable_client(3, rewardAmount="10"), tasks_args(min_reward=50))
        self.assertEqual((data["post_filters"], data["excluded_by_filters"], data["returned"]),
                         ({"min_reward": 50}, 3, 0))

    def test_no_x_is_checked_again_against_the_steps(self):
        # The list row says no X account is needed; the detail's first step is an X follow.
        data = fd.cmd_tasks(self.joinable_client(2, goal="Custom goal"), tasks_args(joinable=True, no_x=True))
        self.assertEqual((data["returned"], data["excluded_by_filters"]), (0, 2))
        self.assertEqual(self.accounted(data), data["page_items"])

    def test_task_detail_lists_blockers_and_pool(self):
        task = self.task(status="not_started", startAt=iso(1))
        client = FakeClient({
            f"/api/tasks/{task['id']}": task,
            "/api/tasks/types": {"goalTypes": [{"key": "x_follow", "label": "X follow",
                                                "isAutoVerifiable": True, "proofTypes": ["handle"]}]},
            f"/api/tasks/{task['id']}/vault": {"deposited": "100", "paid": "0", "refunded": "0",
                                               "available": "0"},
        })
        data = fd.cmd_task(client, argparse.Namespace(id=task["id"]))
        self.assertFalse(data["can_join_now"])
        self.assertEqual(len(data["blockers"]), 3)  # not open, not started, empty pool
        self.assertEqual(data["steps"][0]["instructions"], "Follow @finch on X.")
        self.assertEqual(data["steps"][0]["verification"], "automatic")
        self.assertEqual(data["pool"]["funding_tx"], "https://basescan.org/tx/0xabc")

    def test_unknown_verification_without_the_type_catalog(self):
        self.assertEqual(fd.verification_of("x_follow", {}), "unknown")
        self.assertEqual(fd.verification_of("custom", {}), "requester review")


def skill_card(skill_id, slug, name, summary, price="0", plaintext=True,
               badges=("Base Mainnet", "Onchain", "Public", "Available")):
    card = {"id": f"skill_protocol_v3:8453:{skill_id}", "slug": slug, "kind": "skill", "source": "v3",
            "v3SkillRef": {"chainId": 8453, "skillId": skill_id, "version": 1}, "legacyChipRef": None,
            "name": name, "summary": summary, "category": "Business & Operations",
            "price": {"atomic": price, "decimals": 18, "currency": "ETH"}, "badges": list(badges),
            "marketActivity": {"verifiedDownloads": 3, "primaryPurchases": None}, "creator": "0x" + "2" * 40,
            "cardBadges": {"certik": False, "slowmist": True, "curated": False, "highlyRated": False},
            "skillLocalization": {"sourceLocale": "en", "locales": {"en": {"name": name, "presentation": {
                "summary": summary, "description": summary + " Full text.", "tags": ["Notes"],
                "steps": ["Download the package.", "Load it into your agent."]}}}}}
    if plaintext is not None:
        card["plaintext"] = plaintext
    return card


def skills_args(**overrides):
    base = dict(query=None, limit=10, cursor=None, price="any", access="any", category=None, sort=None)
    base.update(overrides)
    return argparse.Namespace(**base)


class SkillsCommand(unittest.TestCase):
    def setUp(self):
        self.notes = skill_card("7", "note-diagnostics_finchip", "Note Diagnostics",
                                "Diagnose Xiaohongshu notes with an analysis report.")
        self.copy = skill_card("8", "note-copywriter_finchip", "Copywriter", "Writes Xiaohongshu notes.",
                               price="1000000000000000", plaintext=False)
        self.catalog = [self.copy, self.notes]
        self.client = FakeClient({
            "/api/skills/catalog": lambda params: {"items": self.catalog, "nextCursor": "next-1", "totalCount": 9},
            "/api/skills/resolve": {"skillId": "7", "currentVersion": 2},
            "/api/skills/reviews": {"summary": {"reviewCount": 2, "averageRating": 4.5,
                                                "averageOperationalIndependence": 4, "averageOutputQuality": 5,
                                                "averageModelCompatibility": 4.5},
                                    "reviews": [{"overallRating": 5, "body": "Works.",
                                                 "createdAt": "2026-10-14T16:00:00.000Z"}]},
        })

    def test_sends_one_search_request_with_every_filter(self):
        data = fd.cmd_skills(self.client, skills_args(query="xiaohongshu analysis copywriter", price="free",
                                                      access="public", category="Writing", sort="price",
                                                      cursor="c-1"))
        self.assertEqual(self.client.calls, [("/api/skills/catalog", {
            "q": "xiaohongshu analysis copywriter", "category": "Writing", "price": "free", "access": "public",
            "sort": "price", "cursor": "c-1"})])
        self.assertEqual(data["filters"], {"q": "xiaohongshu analysis copywriter", "category": "Writing",
                                           "price": "free", "access": "public", "sort": "price"})

    def test_browsing_leaves_finch_defaults_alone(self):
        fd.cmd_skills(self.client, skills_args())
        self.assertEqual(self.client.calls, [("/api/skills/catalog", {})])

    def test_keeps_finch_order(self):
        # "Note Diagnostics" holds both words; Finch put the Copywriter first, and its order decides.
        data = fd.cmd_skills(self.client, skills_args(query="xiaohongshu analysis"))
        self.assertEqual([(s["slug"], s["rank"]) for s in data["skills"]],
                         [(self.copy["slug"], 1), (self.notes["slug"], 2)])
        self.assertNotIn("match", data["skills"][0])

    def test_limit_cuts_the_page_and_keeps_finch_cursor(self):
        data = fd.cmd_skills(self.client, skills_args(limit=1))
        self.assertEqual((data["returned"], data["beyond_limit"], data["page_items"]), (1, 1, 2))
        self.assertEqual((data["next_cursor"], data["total_matches"]), ("next-1", 9))

    def test_no_result_hint(self):
        self.catalog = []
        self.assertIn("Finch found no Skill", fd.cmd_skills(self.client, skills_args(query="nothing"))["hint"])

    def test_access_comes_from_plaintext_not_badges(self):
        # The protected Copywriter has no Public badge; a public card keeps it. Neither badge decides.
        self.notes["badges"].remove("Public")
        notes, copy = (fd.skill_record(c, "https://example.test") for c in (self.notes, self.copy))
        self.assertEqual((notes["access"], copy["access"]), ("public", "protected"))

    def test_unknown_access_or_availability_is_unknown_and_said_so(self):
        no_plaintext = skill_card("14", "chain-read_finchip", "Chain Read", "Read from chain.", plaintext=None)
        no_badge = skill_card("15", "chain-write_finchip", "Chain Write", "Write.",
                              badges=("BNB Chain", "Custom Licence", "legacy"))
        self.catalog = [no_plaintext, no_badge]
        data = fd.cmd_skills(self.client, skills_args())
        self.assertEqual([(s["access"], s["available"]) for s in data["skills"]], [(None, True), ("public", None)])
        self.assertTrue(any("2 Skill(s)" in w for w in data["warnings"]))
        detail = fd.cmd_skill(self.client, argparse.Namespace(slug="chain-read_finchip", reviews=3))
        self.assertIsNone(detail["access"])
        self.assertTrue(any("public or available" in w for w in detail["warnings"]))

    def test_records_price_access_and_trust_signals(self):
        record = fd.cmd_skills(self.client, skills_args(query="copywriter"))["skills"][0]
        self.assertEqual(record["price"], {"amount": "0.001", "currency": "ETH", "free": False})
        self.assertEqual((record["access"], record["chain"], record["audits"]), ("protected", "Base", ["SlowMist"]))
        self.assertEqual(record["url"], "https://example.test/market/chips/note-copywriter_finchip")

    def test_skill_detail_from_a_page_url(self):
        data = fd.cmd_skill(self.client, argparse.Namespace(
            slug="https://www.finchtech.ai/market/chips/base/note-diagnostics_finchip/run", reviews=3))
        self.assertEqual(self.client.calls[0], ("/api/skills/catalog", {"q": "note-diagnostics_finchip"}))
        self.assertEqual((data["version"], data["price"]["free"]), (2, True))
        self.assertEqual(data["rating"]["output_quality"], 5)
        self.assertEqual(data["steps"][0], "Download the package.")
        self.assertIn("signed-in Finch CLI", data["next_step"])

    def test_unknown_or_malformed_slug(self):
        with self.assertRaises(fd.FinchError) as missing:
            fd.cmd_skill(self.client, argparse.Namespace(slug="nothing-here", reviews=3))
        self.assertEqual(missing.exception.code, "NOT_FOUND")
        self.assertIn("outside what search covers", str(missing.exception))
        self.assertNotIn("delisted", str(missing.exception))
        self.assertIn("/market/chips/nothing-here", str(missing.exception))
        with self.assertRaises(fd.FinchError) as bad:
            fd.skill_slug("not a slug!")
        self.assertEqual(bad.exception.code, "INVALID_INPUT")


class HoldingsCommand(unittest.TestCase):
    WALLET = "0x" + "a" * 40

    @staticmethod
    def total(chain_id, name, purchases=0, paid="0", synced=True, **state):
        # The /api/skills/purchase-cost entry shape, with its sync state.
        entry = {"chainId": chain_id, "chainName": name, "totalPaidAtomic": paid, "decimals": 18, "currency": "ETH",
                 "purchases": purchases, "unpricedPurchases": 0, "indexed": synced,
                 "coveredThrough": "2026-10-15T03:00:00Z" if synced else None,
                 "coverageLagSeconds": 60 if synced else None, "liveProgressLagSeconds": 30 if synced else None,
                 "historyComplete": synced, "liveComplete": synced}
        entry.update(state)
        return entry

    @staticmethod
    def cost(totals):
        return {"totals": totals, "coverage": {"protocols": ["skill_protocol_v3", "legacy"], "events": ["primary"],
                                               "excludes": ["secondary_market"], "freshnessSeconds": 3600}}

    def client(self, **overrides):
        routes = {
            "/api/skills/holdings": {"owned": [{"chainId": 8453, "skillId": "7", "version": 1, "balance": "1",
                                                "currentVersion": 2, "slug": "note-diagnostics_finchip",
                                                "name": "Note Diagnostics", "plaintext": False, "stale": True}],
                                     "verificationUnavailable": False},
            "/api/legacy/holdings": {"owned": []},
            "/api/skills/purchase-cost": self.cost([
                self.total(8453, "Base", purchases=1, paid="2000000000000000"),
                self.total(1, "Ethereum")]),
        }
        routes.update(overrides)
        return FakeClient(routes)

    def test_reports_versions_access_and_spend(self):
        data = fd.cmd_holdings(self.client(), argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        held = data["skills"][0]
        self.assertEqual((held["version_held"], held["current_version"], held["newer_version_available"]), (1, 2, True))
        self.assertEqual(held["access"], "protected")
        self.assertEqual(data["purchase_totals"], [{"chain": "Base", "purchases": 1,
                                                    "total_paid": {"amount": "0.002", "currency": "ETH"},
                                                    "unpriced_purchases": 0, "complete": True, "sync_issues": [],
                                                    "indexed_through": "2026-10-15T03:00:00Z", "lag_seconds": 60,
                                                    "history_complete": True, "live_complete": True}])
        self.assertFalse(any("synced" in w for w in data["warnings"]))  # the synced zero on Ethereum is dropped
        self.assertIn("does not show that the user controls the wallet", data["notes"][0])

    def test_unsynced_chains_stay_listed_and_are_never_read_as_complete(self):
        totals = [self.total(8453, "Base", purchases=2, paid="3000000000000000", historyComplete=False, indexed=False),
                  self.total(56, "BNB Chain", synced=False),
                  self.total(1, "Ethereum"),
                  {k: v for k, v in self.total(43114, "Avalanche").items() if k != "indexed"}]
        data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": self.cost(totals)}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        listed = {t["chain"]: t for t in data["purchase_totals"]}
        self.assertEqual(sorted(listed), ["Avalanche", "BNB Chain", "Base"])  # only Ethereum is a synced zero
        self.assertEqual((listed["Base"]["complete"], listed["Base"]["history_complete"]), (False, False))
        self.assertEqual((listed["BNB Chain"]["purchases"], listed["BNB Chain"]["complete"],
                          listed["BNB Chain"]["indexed_through"]), (0, False, None))
        self.assertFalse(listed["Avalanche"]["complete"])  # a missing `indexed` is unknown, not synced
        warning = next(w for w in data["warnings"] if "not fully synced" in w)
        for chain in ("Base (", "BNB Chain (", "Avalanche ("):
            self.assertIn(chain, warning)
        self.assertIn("a zero there means unknown", warning)
        self.assertEqual(listed["Base"]["sync_issues"], ["history_not_backfilled"])

    def test_a_lagging_index_says_so(self):
        # Production on 2026-10-18: Injective was backfilled and live, but counted 5,537 s behind.
        lagging = self.total(1776, "Injective", indexed=False, coverageLagSeconds=5537, liveProgressLagSeconds=40)
        data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": self.cost([lagging])}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        entry = data["purchase_totals"][0]
        self.assertEqual((entry["complete"], entry["history_complete"], entry["live_complete"]), (False, True, True))
        self.assertEqual((entry["sync_issues"], entry["lag_seconds"]), (["counts_behind"], 5537))
        self.assertTrue(any("Injective (counted only up to 5537 s ago; Finch allows 3600 s)" in w
                            for w in data["warnings"]))

    def test_never_indexed_and_unexplained_chains_say_so(self):
        never = self.total(10, "Optimism", synced=False)  # no coverage, no progress: never counted
        odd = self.total(137, "Polygon", indexed=False)  # every field looks synced, yet Finch says no
        data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": self.cost([never, odd])}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        issues = {t["chain"]: t["sync_issues"] for t in data["purchase_totals"]}
        self.assertEqual(issues, {"Optimism": ["not_started"], "Polygon": ["not_indexed"]})

    def test_a_synced_chain_without_a_purchase_count_is_still_listed(self):
        missing = {k: v for k, v in self.total(8453, "Base", paid="1000000000000000").items() if k != "purchases"}
        data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": self.cost([missing])}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        self.assertEqual([(t["chain"], t["purchases"]) for t in data["purchase_totals"]], [("Base", None)])

    def test_unpriced_purchases_make_the_total_a_lower_bound(self):
        priced_one = self.total(8453, "Base", purchases=3, paid="1000000000000000", unpricedPurchases=2)
        data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": self.cost([priced_one])}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        self.assertTrue(data["purchase_totals"][0]["complete"])
        self.assertTrue(any("2 on Base" in w and "lower bound" in w for w in data["warnings"]))

    def test_a_failed_totals_read_is_unknown_not_zero(self):
        for body in ({"error": {"code": "PURCHASE_COST_UNAVAILABLE"}}, {"totals": None}, {"totals": []}):
            with self.subTest(body=body):
                data = fd.cmd_holdings(self.client(**{"/api/skills/purchase-cost": body}),
                                       argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
                self.assertIsNone(data["purchase_totals"])
                self.assertTrue(any("Purchase totals unavailable" in w for w in data["warnings"]))

    def test_legacy_skills_say_whether_the_wallet_created_or_bought_them(self):
        owned = [{"chainId": 56, "chipAddress": "0x" + "b" * 40, "slug": "made_finchip", "name": "Made",
                  "grounds": "creator", "licences": "0", "deliverable": True},
                 {"chainId": 8453, "chipAddress": "0x" + "c" * 40, "slug": "bought_finchip", "name": "Bought",
                  "grounds": "holder", "licences": "2", "deliverable": False}]
        data = fd.cmd_holdings(self.client(**{"/api/legacy/holdings": {"owned": owned}}),
                               argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        self.assertEqual([(s["chain"], s["held_as"], s["licences"]) for s in data["legacy_skills"]],
                         [("Base", "buyer", "2"), ("BNB Chain", "creator", "0")])  # bought ones first

    def test_long_lists_are_cut_but_counted_in_full(self):
        made = [{"chainId": 8453, "slug": f"made-{n}_finchip", "name": f"Made {n}", "grounds": "creator",
                 "licences": "0", "deliverable": n != 0} for n in range(3)]
        bought = {"chainId": 56, "slug": "bought_finchip", "name": "Bought", "grounds": "holder",
                  "licences": "1", "deliverable": True}
        data = fd.cmd_holdings(self.client(**{"/api/legacy/holdings": {"owned": made + [bought]}}),
                               argparse.Namespace(wallet=self.WALLET, limit=2, offset=0))
        self.assertTrue(data["truncated"])
        self.assertEqual(data["next_offset"], 2)
        self.assertEqual([s["slug"] for s in data["legacy_skills"]], ["bought_finchip", "made-0_finchip"])
        self.assertEqual(data["summary"]["legacy_skills"], {
            "total": 4, "by_held_as": {"buyer": 1, "creator": 3}, "by_chain": {"BNB Chain": 1, "Base": 3},
            "not_deliverable": 1})
        self.assertEqual(data["summary"]["skills"]["newer_version_available"], 1)
        self.assertTrue(any("summary" in w and "only when the user asks" in w for w in data["warnings"]))
        self.assertFalse(any("higher --limit" in w for w in data["warnings"]))
        last = fd.cmd_holdings(self.client(**{"/api/legacy/holdings": {"owned": made + [bought]}}),
                               argparse.Namespace(wallet=self.WALLET, limit=2, offset=2))
        self.assertEqual([s["slug"] for s in last["legacy_skills"]], ["made-1_finchip", "made-2_finchip"])
        self.assertEqual((last["truncated"], last["next_offset"]), (True, None))
        self.assertEqual(last["summary"], data["summary"])

    def test_paging_options_are_bounded(self):
        parser = fd.build_parser()
        self.assertEqual(parser.parse_args(["holdings", self.WALLET]).offset, 0)
        for bad in (["--limit", "201"], ["--offset", "-1"]):
            with self.assertRaises(fd.FinchError):
                parser.parse_args(["holdings", self.WALLET, *bad])

    def test_partial_failures_are_unknown_not_empty(self):
        client = self.client()
        del client.routes["/api/legacy/holdings"]
        data = fd.cmd_holdings(client, argparse.Namespace(wallet=self.WALLET, limit=50, offset=0))
        self.assertIsNone(data["legacy_skills"])
        self.assertTrue(data["warnings"])
        with self.assertRaises(fd.FinchError):
            fd.cmd_holdings(client, argparse.Namespace(wallet="0x123", limit=50, offset=0))


class Cautions(unittest.TestCase):
    def flags(self, text):
        return [c["flag"].split(" ")[0] for c in fd.cautions(text)]

    def test_word_forms(self):
        for text in ("deposited 100 USDT", "buying tokens", "invested", "swapped", "minting", "trader"):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), ["Spends"])
        self.assertEqual(self.flags("connect two wallets"), ["Connects"])

    def test_english_words_touching_chinese(self):
        # Python counts Chinese characters as word characters, so \b needs re.ASCII here.
        for text, flag in (("\u5b8c\u6210KYC\u8ba4\u8bc1", "Opens"), ("\u5728DEX\u4e0aswap", "Spends"),
                           ("\u5148deposit\u5230\u91d1\u5e93", "Spends"), ("\u8fde\u63a5wallet", "Connects")):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), [flag])

    def test_more_chinese_spending_terms(self):
        for text in ("\u4ea4\u6613", "\u8d2d\u4e70", "\u6295\u8cc7", "\u5151\u6362", "\u8de8\u94fe", "\u501f\u8d37", "\u94f8\u9020", "\u5e74\u5316\u6536\u76ca"):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), ["Spends"])
        self.assertEqual(self.flags("\u6388\u6743 USDT"), ["Mentions"])
        self.assertEqual(self.flags("\u65e0\u9650\u6388\u6743"), ["Mentions"])
        # Plain "authorize" usually means a social sign-in, which is not the highest-risk class.
        self.assertEqual(self.flags("\u4f7f\u7528\u63a8\u7279\u6388\u6743\u767b\u5f55"), [])

    def test_transfers_and_sending_coins(self):
        for text in ("Send 10 USDT to the address below", "\u8f6c\u8d2610 USDT \u5230\u4e0b\u65b9\u5730\u5740", "transferred 5 USDC",
                     "sending 0.01 ETH"):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), ["Spends"])
        # Not spending: a DM, a payout to the participant (the Chinese is "paid after approval").
        for text in ("Send us a DM on X", "You get paid after review", "\u5ba1\u6838\u901a\u8fc7\u540e\u6253\u6b3e"):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), [])

    def test_social_accounts_and_lookalike_words_are_not_flagged(self):
        for text in ("please investigate the report", "Open your X account", "open a Discord account"):
            with self.subTest(text=text):
                self.assertEqual(self.flags(text), [])
        self.assertEqual(self.flags("open a brokerage account"), ["Opens"])

    def test_context_shows_whether_a_hit_is_a_request_or_a_reminder(self):
        text = ("Step 2. Upload a screenshot of the dashboard. The screenshot must not contain sensitive "
                "information such as private keys or recovery phrases.")
        found = fd.cautions("Connect Your Wallet", text)
        mentions = [c for c in found if c["flag"].startswith("Mentions")][0]
        self.assertEqual(mentions["places"], 1)  # both hits fall in one snippet
        self.assertEqual(mentions["context"][0], "The screenshot must not contain sensitive information "
                         "such as private keys or recovery phrases.")  # the whole sentence
        self.assertEqual(fd.cautions("Deposit " * 10)[0]["places"], 2)

    def test_step_title_and_instructions_are_not_run_together(self):
        task = {"title": "Quest", "goals": [{"seq": 0, "goalType": "custom", "config": {
            "custom_title": "Connect Your Wallet", "description": "Participation steps: open the app."}}]}
        context = fd.detail_cautions(task, {})[0]["context"]
        self.assertEqual(context, ["Connect Your Wallet"])

    def test_seed_phrases_and_private_keys_are_their_own_class(self):
        self.assertEqual(self.flags("Enter your recovery phrase"), ["Mentions"])
        self.assertEqual(self.flags("share the private key"), ["Mentions"])

    def test_chinese_terms(self):
        self.assertEqual(self.flags("\u5145\u503c 100 USDT"), ["Spends"])       # top up
        self.assertEqual(self.flags("\u5b8c\u6210\u5b9e\u540d"), ["Opens"])      # finish real-name check
        self.assertEqual(self.flags("\u52a9\u8bb0\u8bcd"), ["Mentions"])         # seed phrase
        self.assertEqual(self.flags("\u8fde\u63a5\u94b1\u5305"), ["Connects"])   # connect wallet

    def test_cards_need_a_financial_context(self):
        self.assertEqual(self.flags("open a MEXC Card"), ["Opens"])
        self.assertEqual(self.flags("show your employee card"), [])
        self.assertEqual(self.flags("stakeholder update"), [])


class Envelope(unittest.TestCase):
    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = fd.main(argv)
        return code, json.loads(out.getvalue())

    def test_chinese_output_survives_a_legacy_code_page(self):
        # Windows pipes default to cp1252; a real byte stream is needed, StringIO never encodes.
        raw = io.BytesIO()
        stdout = io.TextIOWrapper(raw, encoding="cp1252", newline="")
        owned = [{"chainId": 8453, "skillId": "7", "version": 1, "balance": "1", "currentVersion": 1,
                  "slug": "notes_finchip", "name": "\u7b14\u8bb0\u52a9\u624b", "plaintext": True, "stale": False}]
        client = FakeClient({"/api/skills/holdings": {"owned": owned, "verificationUnavailable": False},
                             "/api/legacy/holdings": {"owned": []}, "/api/skills/purchase-cost": {"totals": []}})
        original = fd.Client
        fd.Client = lambda base: client
        try:
            with contextlib.redirect_stdout(stdout):
                code = fd.main(["holdings", "0x" + "a" * 40])
        finally:
            fd.Client = original
        stdout.flush()
        body = json.loads(raw.getvalue().decode("utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(body["data"]["skills"][0]["name"], "\u7b14\u8bb0\u52a9\u624b")

    def test_usage_error_is_json(self):
        code, body = self.run_main(["tasks", "--limit", "0"])
        self.assertEqual(code, 1)
        self.assertEqual((body["skill"], body["helper"]), ("finch-market", "finch_discover"))
        self.assertEqual(body["error"]["code"], "INVALID_INPUT")

    def test_queries_finch_would_refuse_are_rejected_before_any_request(self):
        parser = fd.build_parser()
        self.assertEqual(parser.parse_args(["agents", "-q", "  stock  "]).query, "stock")
        # Skills and Tasks count UTF-16 code units; Agents count UTF-8 bytes after NFC (3 per Chinese character).
        for command in ("skills", "tasks"):
            self.assertEqual(len(parser.parse_args([command, "-q", STOCK * 100]).query), 200)
        self.assertEqual(len(parser.parse_args(["agents", "-q", STOCK * 33]).query), 66)
        self.assertEqual(len(parser.parse_args(["agents", "-q", "e\u0301" * 100]).query), 200)  # 200 bytes after NFC
        for argv in (["agents", "-q", "x" * 201], ["agents", "-q", "   "], ["agents", "--brief"],
                     ["agents", "-q", STOCK * 33 + "\u80a1"], ["agents", "-q", STOCK * 100],
                     ["skills", "-q", "x" * 201], ["agents", "--category", " "], ["skills", "--category", ""]):
            with self.subTest(argv=argv[:2]):
                with self.assertRaises(fd.FinchError) as refused:
                    parser.parse_args(argv)
                self.assertEqual(refused.exception.code, "INVALID_INPUT")

    def test_base_url_is_limited_to_finch(self):
        for value, allowed in (("https://staging.finchtech.ai", True), ("http://localhost:3000", True),
                               ("https://evil.example", False), ("https://finchtech.ai.evil.com", False)):
            with self.subTest(value=value):
                os.environ["FINCH_BASE_URL"] = value
                try:
                    if allowed:
                        self.assertTrue(fd.base_url())
                    else:
                        with self.assertRaises(fd.FinchError):
                            fd.base_url()
                finally:
                    del os.environ["FINCH_BASE_URL"]


if __name__ == "__main__":
    unittest.main()
