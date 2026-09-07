import { CommonModule } from '@angular/common';
import { AfterViewInit, ChangeDetectorRef, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import * as d3 from 'd3';

import { environment } from '../environments/environment';

interface BrainNode {
  id: string;
  kind: string;
  label: string;
  metadata: Record<string, string | number | boolean>;
  x?: number;
  y?: number;
}

interface BrainEdge { source: string | BrainNode; target: string | BrainNode; relation: string; }
interface BrainSnapshot { phase: string; nodes: BrainNode[]; edges: BrainEdge[]; }
interface HealthStatus {
  status: string;
  market_phase: string;
  market_data_provider: string;
  news_provider: string;
  llm_provider: string;
  news_loop: string;
  poll_interval_seconds: number;
  ai_queue_pending: number;
  last_cycle_at: string | null;
  last_cycle_new: number;
  last_cycle_processed: number;
  last_cycle_error: string | null;
}
interface NewsEvent { id: string; title: string; source: string; published_at: string; }

@Component({
  selector: 'app-root', standalone: true, imports: [CommonModule],
  templateUrl: './app.component.html', styleUrl: './app.component.css',
})
export class AppComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('brainCanvas') brainCanvas?: ElementRef<SVGSVGElement>;
  snapshot: BrainSnapshot = { phase: 'CONNECTING', nodes: [], edges: [] };
  selectedNode?: BrainNode;
  health?: HealthStatus;
  recentNews: NewsEvent[] = [];
  activity: string[] = ['SYSTEM // INITIALIZING MARKET INTELLIGENCE'];
  socketState = 'CONNECTING';
  readonly windowOptions = [
    { label: 'LAST 6 HOURS', hours: 6 },
    { label: '12 HOURS', hours: 12 },
    { label: '1 DAY', hours: 24 },
    { label: '2 DAYS', hours: 48 },
    { label: '1 WEEK', hours: 168 },
    { label: 'ALL', hours: null },
  ];
  selectedWindowHours: number | null = 6;
  private socket?: WebSocket;
  private simulation?: d3.Simulation<BrainNode, any>;
  private telemetryTimer?: ReturnType<typeof setInterval>;
  private newsTimer?: ReturnType<typeof setInterval>;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private reconnectAttempts = 0;
  private destroyed = false;

  constructor(private readonly cdr: ChangeDetectorRef) {}

  get graphWindow(): string { return this.windowOptions.find(option => option.hours === this.selectedWindowHours)?.label ?? 'LAST 6 HOURS'; }

  ngOnInit(): void {
    this.connectBrain();
    void this.refreshTelemetry();
    void this.refreshNews();
    this.telemetryTimer = setInterval(() => void this.refreshTelemetry(), 5000);
    this.newsTimer = setInterval(() => void this.refreshNews(), 10000);
  }

  ngAfterViewInit(): void { this.renderGraph(); }

  changeWindow(value: string): void {
    const hours = value === 'ALL' ? null : Number(value);
    this.selectedWindowHours = hours;
    this.selectedNode = undefined;
    this.snapshot = { ...this.snapshot, nodes: [], edges: [] };
    this.simulation?.stop();
    this.socket?.close();
    this.pushActivity(`GRAPH // WINDOW CHANGED // ${this.graphWindow}`);
    this.connectBrain();
    this.cdr.markForCheck();
  }

  private connectBrain(): void {
    if (this.destroyed) return;
    const wsBaseUrl = environment.apiBaseUrl.replace(/^http/i, 'ws').replace(/\/$/, '');
    const windowQuery = this.selectedWindowHours === null ? 'all' : String(this.selectedWindowHours);
    this.socketState = 'CONNECTING';
    this.cdr.markForCheck();
    this.socket = new WebSocket(`${wsBaseUrl}/ws/market-brain?hours=${windowQuery}`);
    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.socketState = 'LIVE';
      this.pushActivity(`STREAM // MARKET BRAIN CONNECTED // ${this.graphWindow}`);
      this.cdr.markForCheck();
    };
    this.socket.onmessage = (event: MessageEvent<string>) => {
      this.snapshot = JSON.parse(event.data) as BrainSnapshot;
      if (this.selectedNode) this.selectedNode = this.snapshot.nodes.find(n => n.id === this.selectedNode?.id);
      this.cdr.markForCheck();
      setTimeout(() => this.renderGraph());
    };
    this.socket.onerror = () => {
      this.socketState = 'ERROR';
      this.pushActivity('STREAM // WEBSOCKET ERROR — RECONNECTING');
      this.cdr.markForCheck();
    };
    this.socket.onclose = () => {
      if (this.destroyed) return;
      this.socketState = 'OFFLINE';
      this.pushActivity('STREAM // MARKET BRAIN DISCONNECTED — RETRYING');
      this.cdr.markForCheck();
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.destroyed || this.reconnectTimer) return;
    const delay = Math.min(10000, 1000 * (2 ** this.reconnectAttempts));
    this.reconnectAttempts = Math.min(this.reconnectAttempts + 1, 4);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connectBrain();
    }, delay);
  }

  private async refreshTelemetry(): Promise<void> {
    try {
      const response = await fetch(`${this.apiBaseUrl()}/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json() as HealthStatus;
      const previousCycle = this.health?.last_cycle_at;
      this.health = health;
      if (this.snapshot.phase !== health.market_phase) this.snapshot = { ...this.snapshot, phase: health.market_phase };
      if (health.last_cycle_at && health.last_cycle_at !== previousCycle) {
        this.pushActivity(`RSS // SCAN COMPLETE ${this.formatTime(health.last_cycle_at)} // ${health.last_cycle_new} NEW // ${health.last_cycle_processed} PROCESSED`);
      }
      if (health.last_cycle_error) this.pushActivity(`PIPELINE // WARNING // ${health.last_cycle_error}`);
      this.cdr.markForCheck();
    } catch {
      this.pushActivity('SYSTEM // BACKEND TELEMETRY UNAVAILABLE');
      this.cdr.markForCheck();
    }
  }

  private async refreshNews(): Promise<void> {
    try {
      const response = await fetch(`${this.apiBaseUrl()}/api/v1/news?limit=8`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const news = await response.json() as NewsEvent[];
      const previousIds = new Set(this.recentNews.map(item => item.id));
      this.recentNews = news;
      for (const item of news.slice(0, 3).reverse()) if (!previousIds.has(item.id)) this.pushActivity(`NEWS // ${item.source.toUpperCase()} // ${item.title}`);
      this.cdr.markForCheck();
    } catch {
      // Health telemetry remains the source of truth when the news endpoint is unavailable.
    }
  }

  private apiBaseUrl(): string { return environment.apiBaseUrl.replace(/\/$/, ''); }
  private pushActivity(message: string): void {
    const stamp = new Date().toLocaleTimeString('en-IN', { hour12: false });
    const line = `${stamp}  ${message}`;
    this.activity = [line, ...this.activity.filter(item => item !== line)].slice(0, 12);
  }
  private formatTime(value: string): string { return new Date(value).toLocaleTimeString('en-IN', { hour12: false, timeZone: 'Asia/Kolkata' }); }

  formatMetadataKey(key: string): string {
    const labels: Record<string, string> = {
      published_at: 'News published (IST)', analyzed_at: 'AI analyzed (IST)', ai_analyzed_at: 'AI analyzed (IST)',
      created_at: 'Trade executed (IST)', as_of: 'P&L as of (IST)', total_pnl: 'Total P&L', realized_pnl: 'Realized P&L',
      unrealized_pnl: 'Unrealized P&L', trade_count: 'Trades', fill_price: 'Fill price', quantity: 'Quantity',
    };
    return labels[key] ?? key;
  }
  formatMetadataValue(key: string, value: string | number | boolean): string | number | boolean {
    if (typeof value === 'string' && (key.endsWith('_at') || key === 'published_at') && value) {
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(date);
    }
    if (typeof value === 'number' && key.includes('pnl')) return value.toFixed(2);
    return value;
  }
  dateMetadataValue(value: string | number | boolean | undefined): string | number | null {
    if (typeof value === 'string' || typeof value === 'number') return value;
    return null;
  }

  private renderGraph(): void {
    const element = this.brainCanvas?.nativeElement;
    if (!element) return;
    this.simulation?.stop();
    const svg = d3.select(element);
    svg.selectAll('*').remove();
    const width = Math.max(element.clientWidth || 1000, 700);
    const height = Math.max(element.clientHeight || 650, 520);
    svg.attr('viewBox', `0 0 ${width} ${height}`);
    const allNodes = this.snapshot.nodes.filter(node => ['NEWS', 'AI', 'STOCK', 'TRADE', 'TOTAL_PNL'].includes(node.kind));
    if (!allNodes.length) return;

    const defs = svg.append('defs');
    const glow = defs.append('filter').attr('id', 'node-glow').attr('x', '-100%').attr('y', '-100%').attr('width', '300%').attr('height', '300%');
    glow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
    const merge = glow.append('feMerge');
    merge.append('feMergeNode').attr('in', 'blur');
    merge.append('feMergeNode').attr('in', 'SourceGraphic');
    defs.append('marker').attr('id', 'arrow').attr('viewBox', '0 -5 10 10').attr('refX', 25).attr('refY', 0).attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto').append('path').attr('d', 'M0,-5L10,0L0,5');

    const laneX: Record<string, number> = { NEWS: width * .10, AI: width * .30, STOCK: width * .50, TRADE: width * .70, TOTAL_PNL: width * .89 };
    const nodes: BrainNode[] = allNodes.map(n => ({ ...n, x: laneX[n.kind] ?? width / 2, y: height / 2 }));
    const nodeIds = new Set(nodes.map(node => node.id));
    const links: BrainEdge[] = this.snapshot.edges.filter(edge => {
      const source = typeof edge.source === 'string' ? edge.source : edge.source.id;
      const target = typeof edge.target === 'string' ? edge.target : edge.target.id;
      return nodeIds.has(source) && nodeIds.has(target);
    }).map(edge => ({ ...edge }));
    const nodeConnections = new Map<string, Set<string>>();
    for (const edge of links) {
      const source = typeof edge.source === 'string' ? edge.source : edge.source.id;
      const target = typeof edge.target === 'string' ? edge.target : edge.target.id;
      if (!nodeConnections.has(source)) nodeConnections.set(source, new Set());
      if (!nodeConnections.has(target)) nodeConnections.set(target, new Set());
      nodeConnections.get(source)?.add(target);
      nodeConnections.get(target)?.add(source);
    }

    const link = svg.append('g').attr('class', 'links').selectAll<SVGLineElement, BrainEdge>('line').data(links).join('line').attr('class', 'brain-link').attr('marker-end', 'url(#arrow)').attr('stroke-dasharray', '2 9');
    const node = svg.append('g').attr('class', 'nodes').selectAll<SVGGElement, BrainNode>('g').data(nodes).join('g').attr('class', d => `brain-node brain-${d.kind.toLowerCase()}`).on('click', (_, d) => this.selectNode(d));
    node.append('circle').attr('class', 'node-aura').attr('r', d => d.kind === 'TOTAL_PNL' ? 52 : d.kind === 'AI' ? 38 : d.kind === 'STOCK' ? 31 : d.kind === 'TRADE' ? 28 : 27);
    node.append('circle').attr('r', d => d.kind === 'TOTAL_PNL' ? 32 : d.kind === 'AI' ? 23 : d.kind === 'STOCK' ? 19 : d.kind === 'TRADE' ? 18 : 17)
      .attr('class', d => `node-${d.kind.toLowerCase()}`)
      .attr('fill', d => this.nodeFill(d))
      .attr('stroke', d => this.nodeStroke(d));
    node.filter(d => d.kind === 'AI').append('circle').attr('class', 'node-core').attr('r', 5);
    node.append('circle').attr('class', 'node-ripple').attr('r', d => d.kind === 'TOTAL_PNL' ? 34 : d.kind === 'AI' ? 25 : 21);
    node.append('text').attr('class', 'node-kind').attr('dy', d => d.kind === 'TOTAL_PNL' ? -45 : -34).text(d => d.kind === 'TOTAL_PNL' ? 'TOTAL PNL' : d.kind);
    node.append('text').attr('class', 'node-label').attr('dy', 5).text(d => d.kind === 'TOTAL_PNL' ? (Number(d.metadata['total_pnl'] ?? 0) === 0 && Number(d.metadata['trade_count'] ?? 0) === 0 ? '' : d.label) : d.label.length > 20 ? `${d.label.slice(0, 20)}…` : d.label);
    node.append('text').attr('class', 'node-time').attr('dy', d => d.kind === 'TOTAL_PNL' ? 49 : 39).text(d => this.nodeAge(d));

    node.on('mouseenter', (_, hovered) => {
      const connected = nodeConnections.get(hovered.id) ?? new Set<string>();
      node.classed('node-dimmed', d => d.id !== hovered.id && !connected.has(d.id));
      link.classed('link-active', edge => {
        const source = typeof edge.source === 'string' ? edge.source : edge.source.id;
        const target = typeof edge.target === 'string' ? edge.target : edge.target.id;
        return source === hovered.id || target === hovered.id;
      });
      node.filter(d => d.id === hovered.id).raise();
      this.pushActivity(`FOCUS // ${hovered.kind} // ${hovered.label}`);
      this.simulation?.alphaTarget(.08).restart();
    }).on('mouseleave', () => {
      node.classed('node-dimmed', false);
      link.classed('link-active', false);
      this.simulation?.alphaTarget(0);
    });

    const dragBehavior = d3.drag<SVGGElement, BrainNode>()
      .on('start', (event, d) => { if (!event.active) this.simulation?.alphaTarget(.25).restart(); d.x = event.x; d.y = event.y; })
      .on('drag', (event, d) => { d.x = event.x; d.y = event.y; })
      .on('end', (event) => { if (!event.active) this.simulation?.alphaTarget(0); });
    node.call(dragBehavior);

    this.simulation = d3.forceSimulation<BrainNode>(nodes)
      .force('link', d3.forceLink<BrainNode, BrainEdge>(links).id(d => d.id).distance(115).strength(.55))
      .force('charge', d3.forceManyBody<BrainNode>().strength(-260))
      .force('x', d3.forceX<BrainNode>(d => laneX[d.kind] ?? width / 2).strength(.86))
      .force('y', d3.forceY<BrainNode>(height / 2).strength(.10))
      .force('collision', d3.forceCollide<BrainNode>(48))
      .on('tick', () => {
        const now = Date.now();
        nodes.forEach((d, index) => {
          const floatX = laneX[d.kind] + Math.sin(now / 2400 + index * 1.7) * 3;
          const floatY = height / 2 + Math.sin(now / 1750 + index * 1.35) * 9;
          const currentX = d.x ?? width / 2;
          const currentY = d.y ?? height / 2;
          const nextX = currentX + (floatX - currentX) * .015;
          const nextY = currentY + (floatY - currentY) * .015;
          d.x = Math.max(45, Math.min(width - 45, nextX));
          d.y = Math.max(65, Math.min(height - 55, nextY));
        });
        link.attr('x1', d => this.coordinate(d.source, 'x')).attr('y1', d => this.coordinate(d.source, 'y')).attr('x2', d => this.coordinate(d.target, 'x')).attr('y2', d => this.coordinate(d.target, 'y'));
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
  }

  private nodeFill(node: BrainNode): string {
    if (node.kind === 'TOTAL_PNL') {
      const pnl = Number(node.metadata['total_pnl'] ?? 0);
      return pnl < 0 ? '#3d1720' : '#14392d';
    }
    if (node.kind === 'TRADE') return '#342914';
    if (node.kind === 'NEWS') return '#10243a';
    if (node.kind === 'AI') return '#291b3a';
    return '#16372d';
  }

  private nodeStroke(node: BrainNode): string {
    if (node.kind === 'TOTAL_PNL') return Number(node.metadata['total_pnl'] ?? 0) < 0 ? '#e46e83' : '#61d89b';
    if (node.kind === 'TRADE') return '#d8a34f';
    if (node.kind === 'NEWS') return '#4f91d9';
    if (node.kind === 'AI') return '#a873df';
    return '#5bc39c';
  }

  private nodeAge(node: BrainNode): string {
    const value = node.metadata['published_at'] ?? node.metadata['analyzed_at'] ?? node.metadata['created_at'] ?? node.metadata['as_of'];
    if (typeof value !== 'string') return '';
    const timestamp = new Date(value).getTime();
    if (Number.isNaN(timestamp)) return '';
    const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
    return minutes < 1 ? 'NOW' : minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h`;
  }
  private coordinate(value: string | BrainNode, axis: 'x' | 'y'): number { return typeof value === 'string' ? 0 : value[axis] ?? 0; }
  stockSignal(): string { return String(this.selectedNode?.metadata['ai_signal'] ?? 'IGNORE'); }
  stockAction(): string { switch (this.stockSignal()) { case 'BUY': return 'CONSIDER BUY'; case 'SELL': return 'CONSIDER SELL / REDUCE'; default: return 'NO TRADE / WAIT'; } }
  stockActionGuidance(): string { switch (this.stockSignal()) { case 'BUY': return 'Positive news impact detected. Wait for price, liquidity and risk-rule confirmation before entering.'; case 'SELL': return 'Negative news impact detected. Consider reducing or avoiding the stock after confirming price action and risk rules.'; default: return 'The AI does not see enough actionable edge from this news. Avoid forcing a trade and wait for stronger evidence.'; } }
  confidencePercent(): number { return Math.round(Number(this.selectedNode?.metadata['ai_confidence'] ?? 0) * 100); }
  entityConfidencePercent(): number { return Math.round(Number(this.selectedNode?.metadata['entity_confidence'] ?? 0) * 100); }

  selectedLineage(): BrainNode[] {
    if (!this.selectedNode) return [];
    const byId = new Map(this.snapshot.nodes.map(node => [node.id, node]));
    const lineage: BrainNode[] = [];
    let current: BrainNode | undefined = this.selectedNode;
    const visited = new Set<string>();
    while (current && !visited.has(current.id)) {
      visited.add(current.id);
      lineage.unshift(current);
      const incoming = this.snapshot.edges.find(edge => {
        const target = typeof edge.target === 'string' ? edge.target : edge.target.id;
        return target === current?.id;
      });
      if (!incoming) break;
      const source = typeof incoming.source === 'string' ? incoming.source : incoming.source.id;
      current = byId.get(source);
    }
    return lineage;
  }

  lineageTimestamp(node: BrainNode): string {
    const keys = node.kind === 'NEWS' ? ['published_at'] : node.kind === 'AI' ? ['analyzed_at'] : node.kind === 'TRADE' ? ['created_at'] : node.kind === 'TOTAL_PNL' ? ['as_of'] : ['news_published_at', 'ai_analyzed_at'];
    for (const key of keys) {
      const value = node.metadata[key];
      if (typeof value === 'string' && value) return this.formatMetadataValue(key, value).toString();
    }
    return '—';
  }

  selectNode(node: BrainNode): void { this.selectedNode = node; this.pushActivity(`SELECT // ${node.kind} // ${node.label || 'TOTAL PNL'}`); this.cdr.markForCheck(); }
  closeInspector(): void { this.selectedNode = undefined; this.cdr.markForCheck(); }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.simulation?.stop();
    this.socket?.close();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.telemetryTimer) clearInterval(this.telemetryTimer);
    if (this.newsTimer) clearInterval(this.newsTimer);
  }
}
