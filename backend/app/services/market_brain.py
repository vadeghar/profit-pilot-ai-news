from app.domain.models import MarketBrainEdge, MarketBrainNode, MarketBrainSnapshot, MarketPhase
from app.services.portfolio import PortfolioService
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository


class MarketBrainService:
    """Build the UI graph from persisted news, AI decisions, paper trades and P&L."""

    def __init__(
        self,
        news_repository: NewsEventRepository,
        decision_repository: AiDecisionRepository,
        paper_repository: PaperTradingRepository,
        portfolio: PortfolioService,
    ) -> None:
        self.news_repository = news_repository
        self.decision_repository = decision_repository
        self.paper_repository = paper_repository
        self.portfolio = portfolio

    async def snapshot(
        self,
        *,
        phase: MarketPhase = MarketPhase.MARKET_HOURS,
        limit: int = 50,
    ) -> MarketBrainSnapshot:
        events = self.news_repository.list_recent(limit)
        orders = self.paper_repository.list_orders(limit)
        orders_by_event = {order.event_id: order for order in orders}
        positions = {position.symbol: position for position in await self.portfolio.snapshots()}

        nodes: list[MarketBrainNode] = []
        edges: list[MarketBrainEdge] = []

        for event in events:
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
                    },
                )
            )
            edges.append(MarketBrainEdge(source=news_id, target=ai_id, relation="ANALYZED"))

            for symbol in event.symbols:
                stock_id = f"stock:{symbol}"
                nodes.append(
                    MarketBrainNode(
                        id=stock_id,
                        kind="STOCK",
                        label=symbol,
                        metadata={"symbol": symbol},
                    )
                )
                edges.append(MarketBrainEdge(source=ai_id, target=stock_id, relation="IMPACTS"))

                order = orders_by_event.get(event.id)
                if order is not None and order.symbol == symbol:
                    trade_id = f"trade:{order.id}"
                    nodes.append(
                        MarketBrainNode(
                            id=trade_id,
                            kind="PAPER_TRADE",
                            label=f"{order.side.value} {order.quantity} @ {order.fill_price:.2f}",
                            metadata={
                                "order_id": order.id,
                                "status": order.status,
                                "notional": order.notional,
                                "created_at": order.created_at,
                            },
                        )
                    )
                    edges.append(MarketBrainEdge(source=stock_id, target=trade_id, relation="EXECUTED"))

                    position = positions.get(symbol)
                    if position is not None:
                        position_id = f"position:{symbol}"
                        nodes.append(
                            MarketBrainNode(
                                id=position_id,
                                kind="POSITION",
                                label=f"{symbol} {position.quantity:+d}",
                                metadata={
                                    "quantity": position.quantity,
                                    "average_price": position.average_price,
                                    "current_price": position.current_price,
                                    "realized_pnl": position.realized_pnl,
                                    "unrealized_pnl": position.unrealized_pnl,
                                    "total_pnl": position.total_pnl,
                                },
                            )
                        )
                        edges.append(MarketBrainEdge(source=trade_id, target=position_id, relation="UPDATES"))

        return MarketBrainSnapshot(phase=phase, nodes=self._dedupe_nodes(nodes), edges=self._dedupe_edges(edges))

    @staticmethod
    def _dedupe_nodes(nodes: list[MarketBrainNode]) -> list[MarketBrainNode]:
        return list({node.id: node for node in nodes}.values())

    @staticmethod
    def _dedupe_edges(edges: list[MarketBrainEdge]) -> list[MarketBrainEdge]:
        return list({(edge.source, edge.target, edge.relation): edge for edge in edges}.values())
