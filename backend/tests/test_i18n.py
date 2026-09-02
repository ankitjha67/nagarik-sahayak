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
from i18n.catalog import KEYS, MESSAGES, Quality, coverage, quality_of


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

    def test_a_fallback_is_always_reported(self):
        res = resolve.resolve("nav.schemes", "sat")
        assert res.fell_back
        assert res.language == "en" and res.requested == "sat"

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
    def test_generated_translations_are_marked_draft(self, code):
        """None of these was written by a native speaker. Marking them reviewed
        would be a claim nobody has earned."""
        assert quality_of(code) is Quality.DRAFT
        assert coverage(code)["needsNativeReview"] is True

    def test_absent_languages_are_marked_missing_with_a_reason(self):
        cov = coverage("sat")
        assert cov["quality"] == Quality.MISSING.value
        assert cov["translatedKeys"] == 0
        assert cov["reason"], "a gap with no explanation cannot be commissioned"

    def test_the_summary_separates_translated_from_reviewed(self):
        s = resolve.summary()
        assert s["withTranslations"] > s["nativelyReviewed"]
        assert s["nativelyReviewed"] == 0, \
            "claiming a native review that did not happen is the failure mode " \
            "this whole module guards against"

    def test_the_summary_names_which_languages_are_missing(self):
        assert set(resolve.summary()["missing"]) == {
            "brx", "doi", "ks", "gom", "mai", "mni", "sat", "sd"}

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

    def test_an_untranslated_bundle_carries_a_visible_notice(self):
        b = resolve.bundle("mni")
        assert not b["fullyTranslated"]
        assert len(b["fallbacks"]) == len(KEYS)
        assert b["fallbackNotice"], \
            "silently serving English is the misrepresentation, not the fallback"

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

    def test_an_unavailable_state_language_is_named_not_hidden(self):
        """Jharkhand has Santali speakers and no Santali strings. The gap must
        be reported, not papered over with Hindi."""
        s = resolve.suggest(state="Jharkhand")
        assert "sat" in s["unavailableFromRanked"]
        assert s["recommended"] in s["availableFromRanked"]

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
    def test_the_states_the_catalog_serves_have_usable_languages(self):
        """Not a hard requirement — English is a lawful fallback — but a State
        scheme offered only in English reaches the wrong half of that State."""
        from data.gov_forms import catalog_states
        uncovered = []
        for state in catalog_states():
            local = [c for c in languages.for_state(state)
                     if c != languages.DEFAULT
                     and quality_of(c) is not Quality.MISSING]
            if not local:
                uncovered.append(state)
        assert not uncovered, (
            f"these States have schemes but no local-language interface: "
            f"{uncovered}")

    def test_hindi_belt_states_map_to_hindi(self):
        for state in ("Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan"):
            assert "hi" in languages.for_state(state)

    def test_a_state_with_two_official_languages_offers_both(self):
        goa = languages.for_state("Goa")
        assert "gom" in goa and "mr" in goa
