from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import NewsEvent


@dataclass(frozen=True)
class CompanyEntity:
    symbol: str
    company_name: str
    aliases: tuple[str, ...] = ()


class EntityResolutionService:
    """Resolve company mentions to canonical NSE symbols deterministically."""

    def __init__(self, entities: list[CompanyEntity]) -> None:
        self.entities = tuple(entities)

    @classmethod
    def default(cls) -> "EntityResolutionService":
        return cls([
            CompanyEntity("RELIANCE", "Reliance Industries Limited", ("reliance", "reliance industries", "ril")),
            CompanyEntity("TCS", "Tata Consultancy Services Limited", ("tcs", "tata consultancy services", "tata consultancy")),
            CompanyEntity("INFY", "Infosys Limited", ("infosys", "infy", "infosys limited")),
            CompanyEntity("HDFCBANK", "HDFC Bank Limited", ("hdfc bank", "hdfcbank")),
            CompanyEntity("ICICIBANK", "ICICI Bank Limited", ("icici bank", "icicibank")),
            CompanyEntity("SBIN", "State Bank of India", ("state bank of india", "sbi", "sbin")),
            CompanyEntity("ITC", "ITC Limited", ("itc", "itc limited")),
            CompanyEntity("BHARTIARTL", "Bharti Airtel Limited", ("bharti airtel", "airtel", "bharti airtel limited")),
            CompanyEntity("LT", "Larsen & Toubro Limited", ("larsen", "larsen & toubro", "l&t", "lt")),
            CompanyEntity("HINDUNILVR", "Hindustan Unilever Limited", ("hindustan unilever", "hul", "hindunilvr")),
            CompanyEntity("KOTAKBANK", "Kotak Mahindra Bank Limited", ("kotak mahindra bank", "kotak bank", "kotakbank")),
            CompanyEntity("AXISBANK", "Axis Bank Limited", ("axis bank", "axisbank")),
            CompanyEntity("MARUTI", "Maruti Suzuki India Limited", ("maruti", "maruti suzuki")),
            CompanyEntity("TATAMOTORS", "Tata Motors Limited", ("tata motors", "tatamotors")),
            CompanyEntity("SUNPHARMA", "Sun Pharmaceutical Industries Limited", ("sun pharma", "sun pharmaceutical", "sunpharma")),
            CompanyEntity("WIPRO", "Wipro Limited", ("wipro",)),
            CompanyEntity("HCLTECH", "HCL Technologies Limited", ("hcl technologies", "hcltech", "hcl tech")),
            CompanyEntity("ADANIENT", "Adani Enterprises Limited", ("adani enterprises", "adani", "adanient")),
            CompanyEntity("ADANIPORTS", "Adani Ports and Special Economic Zone Limited", ("adani ports", "adani ports sez", "adaniports")),
        ])

    @staticmethod
    def _contains(text: str, alias: str) -> bool:
        escaped = re.escape(alias.casefold().strip())
        return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.casefold()))

    def resolve(self, text: str) -> list[CompanyEntity]:
        return [entity for entity in self.entities if any(self._contains(text, alias) for alias in entity.aliases)]

    def symbols_for(self, text: str) -> list[str]:
        return [entity.symbol for entity in self.resolve(text)]

    def enrich(self, event: NewsEvent) -> NewsEvent:
        resolved = self.symbols_for(event.title)
        merged = list(dict.fromkeys([*event.symbols, *resolved]))
        return event.model_copy(update={"symbols": merged})
