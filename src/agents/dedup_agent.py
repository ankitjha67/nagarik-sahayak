"""
GovScheme SuperAgent â€” Deduplication Agent
Detects and removes duplicate schemes across multiple data sources
using fuzzy string matching and content hashing.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from src.agents.models import RawSchemeData, ClassifiedScheme
from src.config.settings import AgentConfig
logger = logging.getLogger("dedup_agent")
@dataclass
class DedupResult:
    """Result of deduplication check."""
    is_duplicate: bool
    duplicate_of: str | None = None  # scheme_name of the original
    similarity_score: float = 0.0
    match_method: str = ""  # hash, fuzzy_name, fuzzy_content
class DeduplicationAgent:
    """
    Multi-strategy deduplication agent:
    1. Content hash matching (exact duplicates)
    2. Fuzzy name matching (similar names from different sources)
    3. URL deduplication (same detail page from different crawlers)
    """
    def __init__(self, config: AgentConfig):
        self.config = config
        self.hash_index: dict[str, str] = {}   # content_hash â†’ scheme_name
        self.url_index: set[str] = set()        # detail URLs seen
        self.name_index: list[str] = []          # all scheme names for fuzzy matching
        self.duplicates_found = 0
    def check_raw(self, scheme: RawSchemeData) -> DedupResult:
        """Check if a raw scheme is a duplicate before classification."""
        # Strategy 1: Content hash
        if scheme.content_hash in self.hash_index:
            self.duplicates_found += 1
            return DedupResult(
                is_duplicate=True,
                duplicate_of=self.hash_index[scheme.content_hash],
                similarity_score=1.0,
                match_method="hash",
            )
        # Strategy 2: URL dedup
        if scheme.scheme_detail_url and scheme.scheme_detail_url in self.url_index:
            self.duplicates_found += 1
            return DedupResult(
                is_duplicate=True,
                similarity_score=1.0,
                match_method="url",
            )
        # Strategy 3: Fuzzy name matching
        if self.name_index:
            best_score, best_match = self._fuzzy_match(scheme.scheme_name)
            if best_score >= self.config.similarity_threshold:
                self.duplicates_found += 1
                return DedupResult(
                    is_duplicate=True,
                    duplicate_of=best_match,
                    similarity_score=best_score,
                    match_method="fuzzy_name",
                )
        # Not a duplicate â€” register it
        self.hash_index[scheme.content_hash] = scheme.scheme_name
        if scheme.scheme_detail_url:
            self.url_index.add(scheme.scheme_detail_url)
        self.name_index.append(scheme.scheme_name)
        return DedupResult(is_duplicate=False)
    def _fuzzy_match(self, name: str) -> tuple[float, str]:
        """Find the best fuzzy match for a scheme name."""
        try:
            from rapidfuzz import fuzz
            best_score = 0.0
            best_match = ""
            name_lower = name.lower().strip()
            for existing in self.name_index:
                score = fuzz.token_sort_ratio(name_lower, existing.lower().strip()) / 100.0
                if score > best_score:
                    best_score = score
                    best_match = existing
            return best_score, best_match
        except ImportError:
            # Fallback to simple matching without rapidfuzz
            return self._simple_similarity(name)
    def _simple_similarity(self, name: str) -> tuple[float, str]:
        """Simple Jaccard similarity fallback."""
        name_tokens = set(name.lower().split())
        best_score = 0.0
        best_match = ""
        for existing in self.name_index:
            existing_tokens = set(existing.lower().split())
            if not name_tokens or not existing_tokens:
                continue
            intersection = name_tokens & existing_tokens
            union = name_tokens | existing_tokens
            score = len(intersection) / len(union) if union else 0.0
            if score > best_score:
                best_score = score
                best_match = existing
        return best_score, best_match
    def deduplicate_batch(self, schemes: list[RawSchemeData]) -> list[RawSchemeData]:
        """Deduplicate a batch of raw schemes. Returns unique schemes only."""
        unique = []
        for scheme in schemes:
            result = self.check_raw(scheme)
            if not result.is_duplicate:
                unique.append(scheme)
            else:
                logger.debug(
                    "Duplicate: '%s' matches '%s' (%.0f%% via %s)",
                    scheme.scheme_name,
                    result.duplicate_of,
                    result.similarity_score * 100,
                    result.match_method,
                )
        logger.info(
            "Dedup: %d input â†’ %d unique (%d duplicates removed)",
            len(schemes), len(unique), len(schemes) - len(unique),
        )
        return unique
    def get_stats(self) -> dict:
        """Return deduplication statistics."""
        return {
            "total_indexed": len(self.hash_index),
            "urls_tracked": len(self.url_index),
            "duplicates_found": self.duplicates_found,
        }
