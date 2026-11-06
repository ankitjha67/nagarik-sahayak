"""Language support across the Eighth Schedule.

The property under test is not coverage. It is that the application never
misrepresents which language a person is reading, and never claims a quality of
translation it does not have.

Both failures land the same way. A citizen served English under a Santali
heading concludes the app has decided English is their language, and has no
button to say otherwise. A citizen served an unreviewed machine translation of
a consent notice gives a consent that is defective in law and, worse, believes
they understood what they agreed to. Silence about either is the bug.
"""
import pytest

from i18n import languages, resolve
from i18n.catalog import (
    KEYS, LOW_CONFIDENCE_LANGUAGES, MESSAGES, Quality, coverage, quality_of,
)


TRANSLATED = [c for c in MESSAGES if c != "en"]
ALL_CODES = [l.code for l in languages.LANGUAGES]


class TestLanguageRegistry:
    def test_the_whole_eighth_schedule_is_present(self):
        scheduled = [l for l in languages.LANGUAGES if l.eighth_schedule]
        assert len(scheduled) == 22, \
            "the Eighth Schedule has 22 languages; a missing one is a citizen " \
            "with no entitlement under s5(3)"

    def test_english_is_listed_but_not_claimed_as_scheduled(self):
        assert languages.get("en").eighth_schedule is False

    @pytest.mark.parametrize("language", languages.LANGUAGES,
                             ids=lambda l: l.code)
    def test_every_language_has_an_endonym_in_its_own_script(self, language):
        """A picker offering "Bengali" to somebody who reads বাংলা is unusable."""
        assert language.endonym
        if language.code not in ("en",):
            assert language.endonym != language.name_en, \
                f"{language.code} has no endonym, only its English name"

    @pytest.mark.parametrize("language", languages.LANGUAGES,
                             ids=lambda l: l.code)
    def test_every_language_declares_a_script_and_direction(self, language):
        assert language.script
        assert isinstance(language.rtl, bool)

    def test_right_to_left_languages_are_marked(self):
        """Urdu, Kashmiri and Sindhi render wrongly without this."""
        assert languages.rtl_codes() == {"ur", "ks", "sd"}

    def test_codes_are_unique(self):
        assert len(ALL_CODES) == len(set(ALL_CODES))


class TestNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("hi", "hi"), ("hi-IN", "hi"), ("HI_in", "hi"), ("hin", "hi"),
        ("ta-IN", "ta"), ("ory", "or"), ("ori", "or"), ("kok", "gom"),
        ("bn-BD", "bn"), ("  ur  ", "ur"),
    ])
    def test_real_world_codes_resolve(self, raw, expected):
        assert languages.normalise(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "klingon", "xx-YY", "!!"])
    def test_nonsense_falls_back_instead_of_raising(self, raw):
        """A strange locale header must not be able to break a page load."""
        assert languages.normalise(raw) == languages.DEFAULT

    def test_accept_language_is_parsed_in_order(self):
        assert languages.parse_accept_language(
            "ta-IN,ta;q=0.9,en-US;q=0.8") == ["ta", "en"]

    def test_an_unknown_first_choice_does_not_outrank_a_known_second(self):
        """Without this, "klingon,ta" would resolve to English."""
        assert languages.parse_accept_language("klingon,ta;q=0.9") == ["ta"]


class TestFallback:
    def test_no_indian_language_falls_back_to_another(self):
        """Sharing a script is not sharing a language. Maithili must not be
        served as Hindi because both are written in Devanagari."""
        for code in ALL_CODES:
            chain = languages.fallback_chain(code)
            others = [c for c in chain if c not in (code, languages.DEFAULT)]
            assert not others, f"{code} falls back to {others}"

    def test_english_does_not_fall_back_to_itself_twice(self):
        assert languages.fallback_chain("en") == ["en"]

    def test_a_fallback_is_always_reported(self, monkeypatch):
        """Every scheduled language now has full coverage, so nothing in the
        catalogue exercises this path. The mechanism is still what stops a
        future gap being served silently, so a gap is simulated rather than
        letting the test quietly stop testing anything."""
        thinned = dict(MESSAGES["ta"])
        thinned.pop("nav.schemes")
        monkeypatch.setitem(MESSAGES, "ta", thinned)

        res = resolve.resolve("nav.schemes", "ta")
        assert res.fell_back
        assert res.language == "en" and res.requested == "ta"

        b = resolve.bundle("ta")
        assert b["fallbacks"] == ["nav.schemes"]
        assert not b["fullyTranslated"]
        assert b["fallbackNotice"], \
            "silently serving English is the misrepresentation, not the fallback"

    def test_a_real_translation_is_not_marked_as_a_fallback(self):
        res = resolve.resolve("nav.schemes", "ta")
        assert not res.fell_back and res.language == "ta"

    def test_an_unknown_key_returns_the_key_not_a_blank(self):
        """A blank label in front of a citizen is worse than a visible key."""
        assert resolve.resolve("nav.nonexistent", "hi").text == "nav.nonexistent"


class TestCatalogueIntegrity:
    @pytest.mark.parametrize("code", TRANSLATED)
    def test_every_language_covers_every_key(self, code):
        """A key added to one language and forgotten in another shows up as a
        blank label, so it is caught here instead."""
        missing = [k for k in KEYS if not MESSAGES[code].get(k)]
        assert not missing, f"{code} is missing {missing}"

    @pytest.mark.parametrize("code", TRANSLATED)
    def test_no_language_carries_keys_the_interface_does_not_use(self, code):
        extra = set(MESSAGES[code]) - set(KEYS)
        assert not extra, f"{code} has undeclared keys {sorted(extra)}"

    @pytest.mark.parametrize("code", TRANSLATED)
    def test_translations_are_not_just_the_english_copied(self, code):
        """Copied English marked as a translation is the exact
        misrepresentation this module exists to prevent."""
        english = MESSAGES["en"]
        # Proper nouns and short labels legitimately coincide; require that the
        # bulk of the catalogue actually differs.
        same = [k for k in KEYS if MESSAGES[code][k] == english[k]]
        assert len(same) < len(KEYS) * 0.2, \
            f"{code} is {len(same)}/{len(KEYS)} identical to English"

    @pytest.mark.parametrize("code", TRANSLATED)
    def test_the_safety_messages_are_translated(self, code):
        """"Never pay anyone" and "this is not the government" are the two
        strings that protect a citizen from being defrauded. English-only
        versions protect only the English-reading."""
        for key in ("msg.no_fee", "msg.not_government", "msg.aadhaar_optional"):
            assert MESSAGES[code][key] != MESSAGES["en"][key]


class TestHonestQuality:
    def test_english_is_the_source_not_a_translation(self):
        assert quality_of("en") is Quality.SOURCE

    @pytest.mark.parametrize("code", TRANSLATED)
    def test_no_translation_claims_a_native_review(self, code):
        """None of these was written by a native speaker. Marking one reviewed
        would be a claim nobody has earned."""
        assert quality_of(code) in (Quality.DRAFT, Quality.LOW_CONFIDENCE)
        assert coverage(code)["needsNativeReview"] is True

    @pytest.mark.parametrize("code", sorted(LOW_CONFIDENCE_LANGUAGES))
    def test_unverifiable_orthography_warns_the_reader(self, code):
        """Bodo, Kashmiri, Manipuri and Santali are written in scripts this
        system cannot check. The text ships, because a citizen is entitled to
        their language — but it ships saying so, since a wrong sentence here
        looks exactly like a right one to the only person who could tell."""
        cov = coverage(code)
        assert cov["quality"] == Quality.LOW_CONFIDENCE.value
        assert cov["warnReader"] is True
        assert cov["readerWarning"] and cov["readerWarningHindi"]

    @pytest.mark.parametrize(
        "code", [c for c in TRANSLATED if c not in LOW_CONFIDENCE_LANGUAGES])
    def test_ordinary_drafts_do_not_cry_wolf(self, code):
        """A warning on every language is a warning on none."""
        assert coverage(code)["warnReader"] is False

    def test_the_reader_warning_is_not_only_in_the_suspect_language(self):
        """If the translation is wrong, a warning written inside it is wrong
        too. It is carried in English and Hindi for that reason."""
        cov = coverage("sat")
        assert "English or Hindi" in cov["readerWarning"]

    def test_every_scheduled_language_now_has_text(self):
        assert resolve.summary()["missing"] == []
        assert resolve.summary()["withTranslations"] == 22

    def test_the_summary_separates_translated_from_reviewed(self):
        s = resolve.summary()
        assert s["withTranslations"] > s["nativelyReviewed"]
        assert s["nativelyReviewed"] == 0, \
            "claiming a native review that did not happen is the failure mode " \
            "this whole module guards against"

    def test_full_coverage_is_not_reported_as_full_confidence(self):
        """22 of 22 must never read as 22 languages the project stands behind."""
        s = resolve.summary()
        assert set(s["lowConfidence"]) == set(LOW_CONFIDENCE_LANGUAGES)
        assert s["reviewPriority"], "no guidance on where review is worth buying"

    def test_legal_text_is_excluded_from_the_catalogue(self):
        """A mistranslated consent notice is a defective consent, so the notice
        and terms are served from dpdp/ in English and Hindi only."""
        assert not [k for k in KEYS
                    if k.startswith(("notice.", "terms.", "consent."))]
        assert "legalTextPolicy" in resolve.summary()


class TestBundles:
    @pytest.mark.parametrize("code", ALL_CODES)
    def test_every_language_yields_a_complete_usable_bundle(self, code):
        """Even an untranslated language must render a working interface."""
        b = resolve.bundle(code)
        assert set(b["strings"]) == set(KEYS)
        assert all(b["strings"].values())

    def test_a_translated_bundle_reports_no_fallbacks(self):
        b = resolve.bundle("ml")
        assert b["fullyTranslated"] and not b["fallbacks"]
        assert not b["fallbackNotice"]

    def test_a_low_confidence_bundle_is_complete_but_warns(self):
        """The reader gets their own language *and* is told it is unchecked."""
        b = resolve.bundle("mni")
        assert b["fullyTranslated"] and not b["fallbacks"]
        assert b["lowConfidence"] is True
        assert b["qualityWarning"] and b["qualityWarningHindi"]

    def test_a_solid_draft_bundle_carries_no_standing_warning(self):
        b = resolve.bundle("bn")
        assert b["lowConfidence"] is False
        assert not b["qualityWarning"]

    def test_an_unknown_language_falls_back_and_says_so(self):
        b = resolve.bundle("klingon")
        assert b["strings"]["nav.schemes"] == "Schemes"

    def test_the_bundle_names_the_script_and_direction(self):
        b = resolve.bundle("ur")
        assert b["language"]["direction"] == "rtl"
        assert b["language"]["endonym"] == "اردو"

    def test_an_unknown_code_still_serves_something(self):
        b = resolve.bundle("klingon")
        assert b["strings"]["nav.schemes"] == "Schemes"


class TestSuggestion:
    def test_a_states_own_language_ranks_first(self):
        """Someone applying for a Tamil Nadu scheme should be offered Tamil
        before Hindi."""
        assert resolve.suggest(state="Tamil Nadu")["recommended"] == "ta"
        assert resolve.suggest(state="Kerala")["recommended"] == "ml"
        assert resolve.suggest(state="West Bengal")["recommended"] == "bn"

    def test_a_low_confidence_state_language_is_offered_but_flagged(self):
        """Jharkhand has Santali speakers. Santali is offered — withholding it
        would be deciding for them that Hindi is close enough — and the caller
        is told to show the standing warning with it."""
        s = resolve.suggest(state="Jharkhand")
        assert "sat" in s["availableFromRanked"]
        assert "sat" in s["lowConfidenceFromRanked"]
        assert not s["unavailableFromRanked"]

    def test_the_browser_preference_is_used_when_no_state_is_known(self):
        s = resolve.suggest(accept_language="kn-IN,kn;q=0.9")
        assert s["recommended"] == "kn"

    def test_a_state_outranks_the_browser(self):
        s = resolve.suggest(state="Kerala", accept_language="hi-IN")
        assert s["recommended"] == "ml"
        assert "hi" in s["ranked"]

    def test_nothing_known_yields_english_without_pretending_otherwise(self):
        s = resolve.suggest()
        assert s["recommended"] == "en"

    def test_every_catalog_state_has_a_language_suggestion(self):
        """A State scheme with no offerable language means a citizen who
        reaches it in the app has nowhere to go."""
        from data.gov_forms import catalog_states
        for state in catalog_states():
            s = resolve.suggest(state=state)
            assert s["recommended"], state
            assert s["availableFromRanked"], state


class TestStateLanguageCoverage:
    def test_every_state_with_schemes_has_a_language_it_can_be_read_in(self):
        """Not necessarily an Indian one. English is the declared official
        language of Arunachal Pradesh, Meghalaya, Mizoram and Nagaland, so
        serving them in English is correct rather than a shortfall — but the
        State must resolve to *something*, or a citizen who reaches a scheme
        there has no readable interface at all."""
        from data.gov_forms import catalog_states
        for state in catalog_states():
            usable = [c for c in languages.for_state(state)
                      if quality_of(c) is not Quality.MISSING]
            assert usable, f"{state} resolves to no readable language"

    def test_states_served_only_in_english_are_ones_where_that_is_official(self):
        from data.gov_forms import catalog_states
        english_only = [
            s for s in catalog_states()
            if [c for c in languages.for_state(s)
                if quality_of(c) is not Quality.MISSING] == [languages.DEFAULT]
        ]
        assert set(english_only) <= {
            "Arunachal Pradesh", "Meghalaya", "Mizoram", "Nagaland"}, (
            "a State is being served only in English without English being its "
            "official language")

    def test_the_schedules_own_gaps_are_recorded_not_hidden(self):
        """Mizo, Khasi, Kokborok and the rest are not in the Eighth Schedule,
        so no statutory entitlement reaches them. That is a fact about the
        Schedule, and pretending English coverage closes it would misdescribe
        what a reader in Aizawl actually gets."""
        assert languages.unscheduled_languages_for("Mizoram") == ("Mizo (Lushai)",)
        assert "Khasi" in languages.unscheduled_languages_for("Meghalaya")
        assert languages.unscheduled_languages_for("Kerala") == ()

    def test_the_gap_reaches_the_suggestion_response(self):
        s = resolve.suggest(state="Mizoram")
        assert s["recommended"] == "en"
        assert "Mizo (Lushai)" in s["unscheduledLocalLanguages"]

    def test_hindi_belt_states_map_to_hindi(self):
        for state in ("Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"):
            assert "hi" in languages.for_state(state)

    def test_a_state_with_two_official_languages_offers_both(self):
        goa = languages.for_state("Goa")
        assert "gom" in goa and "mr" in goa
