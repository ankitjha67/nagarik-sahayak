"""Central and State scheme catalog — structure, domicile, and non-exclusion.

Three properties matter here and none of them is "the catalog is big":

1. **A State scheme must not be offered to someone who cannot claim it.** A
   citizen of Bihar shown Ladli Behna will travel to an office and be turned
   away. Every State entry therefore carries a domicile rule.

2. **A State resident must still see Central schemes.** The opposite failure —
   filtering a Bihar user down to Bihar-only schemes — hides most of the money
   they are entitled to. This is the more damaging of the two errors, because
   it is invisible: nothing tells the user what they were not shown.

3. **Missing data must never read as ineligible.** A profile with no `state`
   yet must come back INCOMPLETE, not NOT_ELIGIBLE.
"""
import pytest

from data.gov_forms import (
    all_profile_keys, catalog_states, get_by_name, get_catalog,
)
from eligibility_engine import Verdict, evaluate_scheme

CATALOG = get_catalog()


def _id(entry):
    return entry["schemeName"]


class TestCatalogStructure:
    def test_catalog_spans_both_levels(self):
        levels = {e["level"] for e in CATALOG}
        assert levels == {"Central", "State"}

    def test_every_entry_declares_a_level(self):
        for e in CATALOG:
            assert e.get("level") in ("Central", "State"), e["schemeName"]

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_state_field_matches_level(self, entry):
        if entry["level"] == "Central":
            assert entry["state"] is None, "a Central scheme is not tied to a State"
        else:
            assert entry["state"], "a State scheme must name its State"

    def test_scheme_names_are_unique(self):
        names = [e["schemeName"] for e in CATALOG]
        assert len(names) == len(set(names)), "duplicate scheme names collide in lookup"

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_entry_is_bilingual(self, entry):
        assert entry.get("schemeNameHindi"), "no Hindi name"
        assert entry.get("descriptionHindi"), "no Hindi description"
        crit = entry.get("eligibilityCriteria", {})
        assert crit.get("summary") and crit.get("summaryHindi")

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_entry_has_fields_and_a_portal(self, entry):
        assert entry.get("extractedFields"), "no fields to fill"
        assert entry["totalFields"] == len(entry["extractedFields"])
        # Most of these schemes are portal-only, so a PDF is optional — but a
        # citizen must always be told where to actually apply.
        assert entry.get("officialWebsite"), "no way to reach the department"

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_fields_are_well_formed(self, entry):
        sections = {s["name"] for s in entry.get("sections", [])}
        for f in entry["extractedFields"]:
            assert f.get("labelEnglish") and f.get("labelHindi"), f
            assert f.get("profileKey"), f
            assert f.get("type"), f
            if f["type"] == "select":
                assert f.get("options"), f"{f['fieldName']} is a select with no options"
            if f.get("section"):
                assert f["section"] in sections, \
                    f"{entry['schemeName']}: field in undeclared section {f['section']}"

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_a_profile_key_means_one_thing(self, entry):
        """The same profileKey must not carry two different field types.

        profileKey is how an answer is reused across schemes. If `annual_income`
        is a number on one form and a select on another, reuse silently
        corrupts the second form.
        """
        canonical = all_profile_keys()
        for f in entry["extractedFields"]:
            ref = canonical[f["profileKey"]]
            assert f["type"] == ref["type"], (
                f"{f['profileKey']} is {f['type']} here but {ref['type']} elsewhere")


class TestDomicile:
    @pytest.mark.parametrize(
        "entry", [e for e in CATALOG if e["level"] == "State"], ids=_id)
    def test_state_scheme_gates_on_residence(self, entry):
        rules = entry.get("eligibilityCriteria", {}).get("rules", [])
        domicile = [r for r in rules
                    if r["field"] == "state" and r["op"] == "=="]
        assert domicile, f"{entry['schemeName']} would be offered to the whole country"
        assert domicile[0]["value"] == entry["state"], \
            "domicile rule names a different State than the entry"

    @pytest.mark.parametrize(
        "entry", [e for e in CATALOG if e["level"] == "Central"], ids=_id)
    def test_central_scheme_does_not_gate_on_residence(self, entry):
        rules = entry.get("eligibilityCriteria", {}).get("rules", [])
        assert not [r for r in rules if r["field"] == "state"], \
            f"{entry['schemeName']} is Central but restricted to one State"

    def test_out_of_state_applicant_is_refused(self):
        scheme = get_by_name("Mukhyamantri Ladli Behna Yojana (Madhya Pradesh)")
        result = evaluate_scheme({
            "state": "Bihar", "gender": "Female", "age": 30,
            "annual_income": 100000, "is_income_tax_payer": "No",
            "is_govt_employee": "No", "land_holding_acres": 2,
        }, scheme)
        assert result.verdict == Verdict.NOT_ELIGIBLE
        assert "state" in {r.field for r in result.failed}

    def test_in_state_applicant_is_accepted(self):
        scheme = get_by_name("Mukhyamantri Ladli Behna Yojana (Madhya Pradesh)")
        result = evaluate_scheme({
            "state": "Madhya Pradesh", "gender": "Female", "age": 30,
            "annual_income": 100000, "is_income_tax_payer": "No",
            "is_govt_employee": "No", "land_holding_acres": 2,
        }, scheme)
        assert result.verdict == Verdict.ELIGIBLE

    def test_unknown_state_is_incomplete_not_refused(self):
        """A citizen who has not yet said where they live has not been refused."""
        scheme = get_by_name("Lakshmir Bhandar (West Bengal)")
        result = evaluate_scheme({"gender": "Female", "age": 40}, scheme)
        assert result.verdict == Verdict.INCOMPLETE


class TestFiltering:
    def test_level_filter(self):
        assert all(e["level"] == "Central" for e in get_catalog(level="Central"))
        assert all(e["level"] == "State" for e in get_catalog(level="State"))
        assert (len(get_catalog(level="Central")) + len(get_catalog(level="State"))
                == len(CATALOG))

    def test_state_filter_keeps_central_schemes(self):
        """The failure this guards is silent: a Bihar user shown only Bihar
        schemes is never told what was withheld."""
        bihar = get_catalog(state="Bihar")
        central = [e for e in bihar if e["level"] == "Central"]
        assert central, "Central schemes were filtered out of a State view"
        assert len(central) == len(get_catalog(level="Central"))

    def test_state_filter_drops_other_states(self):
        bihar = get_catalog(state="Bihar")
        foreign = [e for e in bihar
                   if e["level"] == "State" and e["state"] != "Bihar"]
        assert not foreign

    def test_no_filter_returns_everything(self):
        assert len(get_catalog()) >= len(get_catalog(state="Bihar"))

    def test_catalog_states_are_derived_not_hardcoded(self):
        states = catalog_states()
        assert states == sorted(set(states)), "not sorted / has duplicates"
        for s in states:
            assert get_catalog(state=s), f"{s} listed but has no schemes"

    def test_coverage_is_more_than_a_token_state(self):
        """One or two States would leave most of the country with nothing."""
        assert len(catalog_states()) >= 10


class TestNoOneIsLockedOut:
    """Regressions that would quietly exclude a real applicant."""

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_no_rule_references_an_undeclared_field(self, entry):
        """A rule on a field no form collects can never pass — the scheme would
        sit permanently at INCOMPLETE with nothing the citizen can do."""
        keys = {f["profileKey"] for f in entry["extractedFields"]}
        # `age` is derived from date_of_birth by the engine rather than asked.
        derived = {"age"}
        for rule in entry.get("eligibilityCriteria", {}).get("rules", []):
            assert rule["field"] in keys | derived, (
                f"{entry['schemeName']} tests {rule['field']}, which it never asks for")

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_select_rules_use_a_value_the_form_offers(self, entry):
        """A rule expecting "No" against a dropdown offering "no" refuses
        everybody."""
        by_key = {f["profileKey"]: f for f in entry["extractedFields"]}
        for rule in entry.get("eligibilityCriteria", {}).get("rules", []):
            f = by_key.get(rule["field"])
            if f and f["type"] == "select" and rule["op"] == "==":
                assert rule["value"] in f["options"], (
                    f"{entry['schemeName']}: no applicant can ever select "
                    f"{rule['value']!r} for {rule['field']}")

    @pytest.mark.parametrize("entry", CATALOG, ids=_id)
    def test_every_field_is_in_the_processing_register(self, entry):
        """DPDP s6(1): data processed outside a declared purpose is unlawful.

        Adding a scheme is the easiest way to start collecting an undeclared
        field, so the check runs per scheme and names the offender.
        """
        from dpdp import registry
        for f in entry["extractedFields"]:
            assert registry.record_for(f["profileKey"]), (
                f"{entry['schemeName']} collects {f['profileKey']}, "
                "which is not declared in the processing register")

    @pytest.mark.parametrize(
        "entry", [e for e in CATALOG if e["level"] == "State"], ids=_id)
    def test_a_resident_meeting_every_rule_is_eligible(self, entry):
        """Constructs a profile that satisfies each rule and asserts the scheme
        actually resolves to ELIGIBLE — catching contradictory rule pairs that
        would make a scheme unclaimable by anyone."""
        profile = {}
        for rule in entry["eligibilityCriteria"]["rules"]:
            field, op, value = rule["field"], rule["op"], rule["value"]
            if op == "==":
                profile[field] = value
            elif op == "<=":
                profile[field] = value
            elif op == "<":
                profile[field] = value - 1
            elif op == ">=":
                profile[field] = value
            elif op == ">":
                profile[field] = value + 1
        result = evaluate_scheme(profile, entry)
        assert result.verdict == Verdict.ELIGIBLE, (
            f"{entry['schemeName']} has rules no applicant can satisfy: "
            f"{[(r.field, r.outcome.value) for r in result.failed]}")
