from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EntityMatch:
    symbol: str
    canonical_name: str
    matched_alias: str
    confidence: float


class CompanyEntityResolver:
    """Deterministic company/entity resolver for news titles.

    Aliases are intentionally explicit and configurable so the resolver can be
    replaced later by an exchange master-data or ML entity-resolution service.
    """

    def __init__(self, entities: dict[str, dict[str, object]]) -> None:
        self._entities = entities
        self._patterns: list[tuple[str, str, str, re.Pattern[str]]] = []
        for symbol, definition in entities.items():
            canonical = str(definition.get("name", symbol))
            aliases = definition.get("aliases", [])
            if not isinstance(aliases, list):
                continue
            candidates = [canonical, symbol, *(str(alias) for alias in aliases)]
            for alias in candidates:
                cleaned = alias.strip()
                if not cleaned:
                    continue
                pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(cleaned)}(?![A-Za-z0-9])", re.IGNORECASE)
                self._patterns.append((symbol, canonical, cleaned, pattern))

    def resolve(self, text: str) -> list[EntityMatch]:
        matches: dict[str, EntityMatch] = {}
        for symbol, canonical, alias, pattern in self._patterns:
            if not pattern.search(text):
                continue
            confidence = 1.0 if alias.casefold() in {symbol.casefold(), canonical.casefold()} else 0.95
            existing = matches.get(symbol)
            if existing is None or confidence > existing.confidence or len(alias) > len(existing.matched_alias):
                matches[symbol] = EntityMatch(symbol, canonical, alias, confidence)
        return sorted(matches.values(), key=lambda match: (-match.confidence, match.symbol))

    def resolve_symbols(self, text: str) -> list[str]:
        return [match.symbol for match in self.resolve(text)]
