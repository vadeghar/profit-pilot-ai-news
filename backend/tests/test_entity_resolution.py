from app.services.entity_catalog import resolver
from app.services.entity_resolution import CompanyEntityResolver


def test_resolves_canonical_name_and_alias() -> None:
    matches = resolver.resolve("Reliance Industries and RIL announce new investment")
    assert matches
    assert matches[0].symbol == "RELIANCE"
    assert matches[0].canonical_name == "Reliance Industries"


def test_resolves_multiple_companies_without_substring_false_positive() -> None:
    matches = resolver.resolve("TCS wins contract while Infosys expands operations")
    assert {match.symbol for match in matches} == {"TCS", "INFY"}


def test_custom_catalog_is_supported() -> None:
    custom = CompanyEntityResolver({"ABC": {"name": "Acme Bank", "aliases": ["Acme"]}})
    assert custom.resolve_symbols("Acme Bank results") == ["ABC"]


def test_aliases_are_boundary_matched() -> None:
    assert resolver.resolve_symbols("The catapults were discussed") == []
