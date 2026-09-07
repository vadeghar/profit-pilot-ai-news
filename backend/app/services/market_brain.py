from datetime import datetime, timedelta, timezone

from app.domain.models import MarketBrainEdge, MarketBrainNode, MarketBrainSnapshot, MarketPhase
from app.services.entity_catalog import resolver
from app.services.market_phase import current_market_phase
from app.services.portfolio import PortfolioService
from app.services.source_reliability import SourceReliabilityRegistry
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository


class MarketBrainService:
    """Build the UI graph from recent persisted news, AI decisions, paper trades and P&L."""

    def __init__(
        self,
        news_repository: NewsEventRepository,
        decision_repository: AiDecisionRepository,
        paper_repository: PaperTradingRepository,
        portfolio: PortfolioService,
        source_reliability: SourceReliabilityRegistry | None = None,
    ) -> None:
        self.news_repository = news_repository
        self.decision_repository = decision_repository
        self.paper_repository = paper_repository
        self.portfolio = portfolio
        self.source_reliability = source_reliability or SourceReliabilityRegistry()

    async def snapshot(
        self,
        *,
        phase: MarketPhase | None = None,
        limit: int = 50,
        hours: int | None = 6,
    ) -> MarketBrainSnapshot:
        actual_phase = phase or current_market_phase()
        history_limit = 5000 if hours is None else limit
        events = self.news_repository.list_recent(history_limit)
        if hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, hours))
            events = [event for event in events if self._within_window(event.published_at, cutoff)]

        orders = self.paper_repository.list_orders(5000 if hours is None else limit)
        orders_by_event = {order.event_id: order for order in orders}
        positions = {position.symbol: position for position in await self.portfolio.snapshots()}

        nodes: list[MarketBrainNode] = []
        edges: list[MarketBrainEdge] = []
        trade_count = 0

        for event in events:
            reliability = self.source_reliability.evaluate(event.source)
            matches = resolver.resolve(event.title)
            matches_by_symbol = {match.symbol: match for match in matches}
            news_id = f"news:{event.id}"
            nodes.append(
                MarketBrainNode(
                    id=news_id,
                    kind="NEWS",
                    label=event.title,
                    metadata={
                        "source": event.source,
                        "published_at": event.published_at,
                        "materiality": event.materiality,
                        "source_reliability": reliability.score,
                        "source_tier": reliability.tier,
                        "source_reliability_reason": reliability.reason,
                    },
                )
            )

            decisions = self.decision_repository.list_for_event(event.id)
            if not decisions:
                continue

            decision = decisions[0]
            ai_id = f"ai:{event.id}"
            nodes.append(
                MarketBrainNode(
                    id=ai_id,
                    kind="AI",
                    label=decision.signal.value,
                    metadata={
                        "confidence": decision.confidence,
                        "reasoning": decision.reasoning,
                        "prompt_version": decision.prompt_version,
                        "model": decision.model,
                        "analyzed_at": decision.created_at or "",
                        "source_reliability": reliability.score,
                        "source_tier": reliability.tier,
                    },
                )
            )
            edges.append(MarketBrainEdge(source=news_id, target=ai_id, relation="ANALYZED"))

            for symbol in event.symbols:
                match = matches_by_symbol.get(symbol)
                stock_id = f"stock:{symbol}"
                stock_metadata: dict[str, str | float | int | bool] = {
                    "symbol": symbol,
                    "ai_signal": decision.signal.value,
                    "ai_confidence": decision.confidence,
                    "ai_reasoning": decision.reasoning,
                    "latest_news": event.title,
                    "news_published_at": event.published_at,
                    "ai_analyzed_at": decision.created_at or "",
                    "news_source": event.source,
                    "news_materiality": event.materiality,
                    "ai_model": decision.model,
                }
                if match is not None:
                    stock_metadata.update(
                        {
                            "canonical_name": match.canonical_name,
                            "matched_alias": match.matched_alias,
                            "entity_confidence": match.confidence,
                            "entity_match_type": (
                                "exact symbol/company name"
                                if match.confidence == 1.0
                                else "known alias"
                            ),
                        }
                    )
                nodes.append(
                    MarketBrainNode(
                        id=stock_id,
                        kind="STOCK",
                        label=match.canonical_name if match is not None else symbol,
                        metadata=stock_metadata,
                    )
                )
                edges.append(MarketBrainEdge(source=ai_id, target=stock_id, relation="IMPACTS"))

                order = orders_by_event.get(event.id)
                if order is not None and order.symbol == symbol:
                    trade_count += 1
                    trade_id = f"trade:{order.id}"
                    nodes.append(
                        MarketBrainNode(
                            id=trade_id,
                            kind="TRADE",
                            label=f"{order.side.value} {order.quantity} @ {order.fill_price:.2f}",
                            metadata={
                                "order_id": order.id,
                                "status": order.status,
                                "side": order.side.value,
                                "quantity": order.quantity,
                                "fill_price": order.fill_price,
                                "notional": order.notional,
                                "created_at": order.created_at,
                                "symbol": symbol,
                            },
                        )
                    )
                    edges.append(MarketBrainEdge(source=stock_id, target=trade_id, relation="EXECUTED"))

        total_realized = sum(float(position.realized_pnl) for position in positions.values())
        total_unrealized = sum(float(position.unrealized_pnl) for position in positions.values())
        total_pnl = total_realized + total_unrealized
        pnl_id = "total-pnl"
        nodes.append(
            MarketBrainNode(
                id=pnl_id,
                kind="TOTAL_PNL",
                label=(f"+{total_pnl:.2f}" if total_pnl >= 0 else f"{total_pnl:.2f}"),
                metadata={
                    "realized_pnl": total_realized,
                    "unrealized_pnl": total_unrealized,
                    "total_pnl": total_pnl,
                    "trade_count": trade_count,
                    "status": "PROFIT" if total_pnl > 0 else "LOSS" if total_pnl < 0 else "FLAT",
                    "as_of": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

        for node in nodes:
            if node.kind == "TRADE":
                edges.append(MarketBrainEdge(source=node.id, target=pnl_id, relation="CONTRIBUTES"))

        return MarketBrainSnapshot(phase=actual_phase, nodes=self._dedupe_nodes(nodes), edges=self._dedupe_edges(edges))

    @staticmethod
    def _within_window(value: str, cutoff: datetime) -> bool:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc) >= cutoff
        except ValueError:
            return False

    @staticmethod
    def _dedupe_nodes(nodes: list[MarketBrainNode]) -> list[MarketBrainNode]:
        deduped: dict[str, MarketBrainNode] = {}
        for node in nodes:
            if node.id not in deduped:
                deduped[node.id] = node
        return list(deduped.values())

    @staticmethod
    def _dedupe_edges(edges: list[MarketBrainEdge]) -> list[MarketBrainEdge]:
        return list({(edge.source, edge.target, edge.relation): edge for edge in edges}.values())
