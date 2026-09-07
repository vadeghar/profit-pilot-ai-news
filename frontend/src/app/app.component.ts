import { CommonModule } from '@angular/common';
import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import * as d3 from 'd3';

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
  private socket?: WebSocket;
  private simulation?: d3.Simulation<BrainNode, any>;
  private telemetryTimer?: ReturnType<typeof setInterval>;
  private newsTimer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.connectBrain();
    void this.refreshTelemetry();
    void this.refreshNews();
    this.telemetryTimer = setInterval(() => void this.refreshTelemetry(), 5000);
    this.newsTimer = setInterval(() => void this.refreshNews(), 10000);
  }

  ngAfterViewInit(): void { this.renderGraph(); }

  private connectBrain(): void {
    this.socket = new WebSocket('ws://localhost:8000/ws/market-brain');
    this.socket.onopen = () => {
      this.socketState = 'LIVE';
      this.pushActivity('STREAM // MARKET BRAIN WEBSOCKET CONNECTED');
    };
    this.socket.onmessage = (event: MessageEvent<string>) => {
      this.snapshot = JSON.parse(event.data) as BrainSnapshot;
      if (this.selectedNode) this.selectedNode = this.snapshot.nodes.find(n => n.id === this.selectedNode?.id);
      this.renderGraph();
    };
    this.socket.onerror = () => {
      this.socketState = 'ERROR';
      this.pushActivity('STREAM // WEBSOCKET ERROR — RETRY REQUIRED');
    };
    this.socket.onclose = () => {
      this.socketState = 'OFFLINE';
      this.pushActivity('STREAM // MARKET BRAIN DISCONNECTED');
    };
  }

  private async refreshTelemetry(): Promise<void> {
    try {
      const response = await fetch('http://localhost:8000/health');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json() as HealthStatus;
      const previousCycle = this.health?.last_cycle_at;
      this.health = health;
      if (this.snapshot.phase !== health.market_phase) {
        this.snapshot = { ...this.snapshot, phase: health.market_phase };
      }
      if (health.last_cycle_at && health.last_cycle_at !== previousCycle) {
        const cycleTime = this.formatTime(health.last_cycle_at);
        this.pushActivity(`RSS // SCAN COMPLETE ${cycleTime} // ${health.last_cycle_new} NEW // ${health.last_cycle_processed} PROCESSED`);
      }
      if (health.last_cycle_error) {
        this.pushActivity(`PIPELINE // WARNING // ${health.last_cycle_error}`);
      }
    } catch {
      this.socketState = 'OFFLINE';
      this.pushActivity('SYSTEM // BACKEND TELEMETRY UNAVAILABLE');
    }
  }

  private async refreshNews(): Promise<void> {
    try {
      const response = await fetch('http://localhost:8000/api/v1/news?limit=8');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const news = await response.json() as NewsEvent[];
      const previousIds = new Set(this.recentNews.map(item => item.id));
      this.recentNews = news;
      for (const item of news.slice(0, 3).reverse()) {
        if (!previousIds.has(item.id)) {
          this.pushActivity(`NEWS // ${item.source.toUpperCase()} // ${item.title}`);
        }
      }
    } catch {
      // Health telemetry remains the source of truth when the news endpoint is unavailable.
    }
  }

  private pushActivity(message: string): void {
    const stamp = new Date().toLocaleTimeString('en-IN', { hour12: false });
    const line = `${stamp}  ${message}`;
    this.activity = [line, ...this.activity.filter(item => item !== line)].slice(0, 12);
  }

  private formatTime(value: string): string {
    return new Date(value).toLocaleTimeString('en-IN', { hour12: false });
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
    if (!this.snapshot.nodes.length) return;

    const defs = svg.append('defs');
    defs.append('marker').attr('id', 'arrow').attr('viewBox', '0 -5 10 10').attr('refX', 24).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto').append('path').attr('d', 'M0,-5L10,0L0,5');

    const laneX: Record<string, number> = { NEWS: width * .10, AI: width * .30, STOCK: width * .50, PAPER_TRADE: width * .70, POSITION: width * .90 };
    const nodes: BrainNode[] = this.snapshot.nodes.map(n => ({ ...n, x: laneX[n.kind] ?? width / 2, y: height / 2 }));
    const links: BrainEdge[] = this.snapshot.edges.map(e => ({ ...e }));

    const link = svg.append('g').attr('class', 'links')
      .selectAll<SVGLineElement, BrainEdge>('line').data(links).join('line')
      .attr('class', 'brain-link').attr('marker-end', 'url(#arrow)');

    const node = svg.append('g').attr('class', 'nodes')
      .selectAll<SVGGElement, BrainNode>('g').data(nodes).join('g')
      .attr('class', 'brain-node').on('click', (_, d) => this.selectNode(d))
      .call(
        d3.drag<SVGGElement, BrainNode>()
          .on('start', (event, d) => {
            if (!event.active) this.simulation?.alphaTarget(.25).restart();
            d.x = event.x; d.y = event.y;
          })
          .on('drag', (event, d) => { d.x = event.x; d.y = event.y; })
          .on('end', (event) => { if (!event.active) this.simulation?.alphaTarget(0); }),
      );

    node.append('circle').attr('r', d => d.kind === 'AI' ? 25 : 20).attr('class', d => `node-${d.kind.toLowerCase()}`);
    node.append('text').attr('class', 'node-kind').attr('dy', -30).text(d => d.kind);
    node.append('text').attr('class', 'node-label').attr('dy', 4).text(d => d.label.length > 24 ? `${d.label.slice(0, 24)}…` : d.label);

    this.simulation = d3.forceSimulation<BrainNode>(nodes)
      .force('link', d3.forceLink<BrainNode, BrainEdge>(links).id(d => d.id).distance(120).strength(.65))
      .force('charge', d3.forceManyBody<BrainNode>().strength(-260))
      .force('x', d3.forceX<BrainNode>(d => laneX[d.kind] ?? width / 2).strength(.8))
      .force('y', d3.forceY<BrainNode>(height / 2).strength(.08))
      .force('collision', d3.forceCollide<BrainNode>(34))
      .on('tick', () => {
        nodes.forEach(d => {
          d.x = Math.max(35, Math.min(width - 35, d.x ?? width / 2));
          d.y = Math.max(45, Math.min(height - 35, d.y ?? height / 2));
        });
        link.attr('x1', d => this.coordinate(d.source, 'x')).attr('y1', d => this.coordinate(d.source, 'y'))
          .attr('x2', d => this.coordinate(d.target, 'x')).attr('y2', d => this.coordinate(d.target, 'y'));
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
  }

  private coordinate(value: string | BrainNode, axis: 'x' | 'y'): number {
    if (typeof value === 'string') return 0;
    return value[axis] ?? 0;
  }

  selectNode(node: BrainNode): void { this.selectedNode = node; }
  closeInspector(): void { this.selectedNode = undefined; }

  ngOnDestroy(): void {
    this.simulation?.stop();
    this.socket?.close();
    if (this.telemetryTimer) clearInterval(this.telemetryTimer);
    if (this.newsTimer) clearInterval(this.newsTimer);
  }
}
