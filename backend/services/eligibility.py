"""Eligibility matching - Prisma-backed and in-memory sync variants."""
import re
import json
import logging
import time as _time
from database import prisma, find_user
from config import AGNOST_WRITE_KEY
from services.search import search_schemes_prisma, SCHEMES_SEED

logger = logging.getLogger(__name__)


def _track(user_id, input_val, output_val, properties, success, latency):
    if not AGNOST_WRITE_KEY:
        return
    try:
        import agnost
        agnost.track(
            user_id=user_id, agent_name="nagarik_tool",
            input=input_val, output=output_val,
            properties=properties, success=success, latency=latency,
        )
    except Exception:
        pass


async def eligibility_matcher_prisma(user_id: str, scheme_name: str = "") -> dict:
    """MCP Tool 2: Fetch User profile + Schemes from Prisma, compare eligibility.
    Income in profile is YEARLY (सालाना). Defaults to Vidyasiri Scholarship."""
    t0 = _time.time()
    user = await find_user(user_id)
    if not user:
        return {"match_found": False, "results": [], "summary": "User not found"}
    profile = json.loads(user.profile) if isinstance(user.profile, str) and user.profile else (user.profile or {})
    name = profile.get("name", "")
    income_yearly = profile.get("income") or 0
    state = (profile.get("state") or "").lower()

    # Full structured profile for the strict rule engine (the chat's four fields
    # plus anything supplied elsewhere). Map the chat's "income" to the engine's
    # "annual_income" so income rules can evaluate.
    from dpdp import profile_store
    from eligibility_engine import evaluate_scheme
    from data.gov_forms import get_by_name
    eng_profile = dict(profile_store.load(user) or profile or {})
    if eng_profile.get("income") and not eng_profile.get("annual_income"):
        eng_profile["annual_income"] = eng_profile["income"]

    await search_schemes_prisma("scholarship eligibility")

    vidyasiri = await prisma.scheme.find_first(where={"name": {"contains": "Vidyasiri"}})
    if scheme_name:
        schemes = await prisma.scheme.find_many(where={"name": {"contains": scheme_name}})
    else:
        schemes = await prisma.scheme.find_many()
    if vidyasiri:
        schemes = [vidyasiri] + [s for s in schemes if s.id != vidyasiri.id]

    documents_scanned = [s.name for s in schemes]
    results = []

    for scheme in schemes:
        # Strict, rule-based verdict (ELIGIBLE / NOT_ELIGIBLE / INCOMPLETE). Only
        # a definite ELIGIBLE is treated as eligible here, so a scheme whose
        # rules cannot yet be decided ("needs more info") is NOT marked eligible
        # and does not get a downloadable form - which is what gates downloads to
        # schemes the citizen genuinely qualifies for.
        entry = get_by_name(scheme.name)
        if entry:
            er = evaluate_scheme(eng_profile, entry)
            eligible = er.is_eligible
            verdict = er.verdict.value
            reason = er.summary_hi or er.summary_en or ("पात्र" if eligible else "अपात्र")
        else:
            eligible = False
            verdict = "incomplete"
            reason = "पात्रता नियम उपलब्ध नहीं - विस्तार के लिए कार्यालय से संपर्क करें"

        results.append({
            "scheme": scheme.name, "scheme_hi": scheme.name, "scheme_id": scheme.id,
            "eligible": eligible, "verdict": verdict,
            "reasons": [reason], "reason": reason,
            "benefit": scheme.eligibilityCriteriaText,
        })

    latency = int((_time.time() - t0) * 1000)
    _track(
        user_id, json.dumps(profile, ensure_ascii=False, default=str),
        str(any(r["eligible"] for r in results)),
        {"tool": "eligibility_matcher"},
        any(r["eligible"] for r in results), latency,
    )

    summary_lines = [f"नमस्ते {name}! प्रोफाइल आधारित पात्रता जांच:", ""]
    for r in results:
        icon = "+" if r["eligible"] else "-"
        summary_lines.append(f"[{icon}] {r['scheme']}: {'पात्र' if r['eligible'] else 'अपात्र'}")
        summary_lines.append(f"    कारण: {r['reason']}")
        if r["eligible"] and r.get("benefit"):
            summary_lines.append(f"    लाभ: {r['benefit']}")
        summary_lines.append("")

    return {
        "tool_name": "eligibility_matcher", "tool_input": {"user_id": user_id},
        "documents_scanned": documents_scanned, "match_found": len(results) > 0,
        "results": results, "summary": "\n".join(summary_lines),
    }


def eligibility_matcher_sync(profile_data: dict, query: str = "") -> dict:
    """Sync eligibility matcher using in-memory rules."""
    age = profile_data.get("age", 0) or 0
    income = profile_data.get("income", 0) or 0
    name = profile_data.get("name", "")

    SCHEME_RULES = {
        0: {"scheme": "PM-KISAN Samman Nidhi", "scheme_hi": "पीएम-किसान सम्मान निधि",
            "criteria": {"income_limit": 200000, "min_age": 18, "requires": "cultivable_land"},
            "benefit": "₹6,000/year (₹2,000 every 4 months via DBT)"},
        1: {"scheme": "Ayushman Bharat (PM-JAY)", "scheme_hi": "आयुष्मान भारत (पीएम-जय)",
            "criteria": {"income_limit": 50000, "min_age": 0, "requires": "secc_2011_listing"},
            "benefit": "₹5,00,000/year health cover per family"},
        2: {"scheme": "Sukanya Samriddhi Yojana", "scheme_hi": "सुकन्या समृद्धि योजना",
            "criteria": {"income_limit": None, "min_age": 18, "requires": "girl_child_under_10"},
            "benefit": "~8.2% interest p.a., ₹1.5L tax deduction under 80C"},
    }

    results = []
    for idx in [0, 1, 2]:
        rule = SCHEME_RULES[idx]
        criteria = rule["criteria"]
        reasons, eligible = [], True
        if criteria["min_age"] > 0 and age < criteria["min_age"]:
            eligible = False
            reasons.append(f"Age {age} below minimum {criteria['min_age']}")
        if criteria["income_limit"] is not None:
            if income > criteria["income_limit"]:
                eligible = False
                reasons.append(f"Income ₹{income:,}/month exceeds ₹{criteria['income_limit']:,}/month limit")
            else:
                reasons.append(f"Income ₹{income:,}/month within ₹{criteria['income_limit']:,}/month limit")
        req = criteria.get("requires", "")
        if req == "cultivable_land":
            reasons.append("Requires cultivable agricultural land")
        elif req == "secc_2011_listing":
            reasons.append("Requires SECC 2011 listing")
        elif req == "girl_child_under_10":
            reasons.append("Requires girl child below 10 years")
        results.append({
            "scheme": rule["scheme"], "scheme_hi": rule["scheme_hi"],
            "eligible": eligible, "reasons": reasons, "reason": "; ".join(reasons),
            "benefit": rule["benefit"],
        })

    summary_parts = [f"नमस्ते {name}! प्रोफाइल आधारित पात्रता:", ""]
    for r in results:
        summary_parts.append(f"[{'+' if r['eligible'] else '-'}] {r['scheme_hi']}: {'पात्र' if r['eligible'] else 'अपात्र'}")
        summary_parts.append(f"    कारण: {r['reason']}")
        if r["eligible"]:
            summary_parts.append(f"    लाभ: {r['benefit']}")
        summary_parts.append("")

    return {
        "tool_name": "eligibility_matcher", "tool_input": {"profile": profile_data},
        "documents_scanned": [r["scheme"] for r in results], "match_found": len(results) > 0,
        "results": results, "summary": "\n".join(summary_parts),
    }
