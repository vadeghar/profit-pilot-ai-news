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

@Component({
  selector: 'app-root', standalone: true, imports: [CommonModule],
  templateUrl: './app.component.html', styleUrl: './app.component.css',
})
export class AppComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('brainCanvas') brainCanvas?: ElementRef<SVGSVGElement>;
  snapshot: BrainSnapshot = { phase: 'PRE_MARKET', nodes: [], edges: [] };
  selectedNode?: BrainNode;
  private socket?: WebSocket;
  private simulation?: d3.Simulation<BrainNode, any>;

  ngOnInit(): void {
    this.socket = new WebSocket('ws://localhost:8000/ws/market-brain');
    this.socket.onmessage = (event: MessageEvent<string>) => {
      this.snapshot = JSON.parse(event.data) as BrainSnapshot;
      if (this.selectedNode) this.selectedNode = this.snapshot.nodes.find(n => n.id === this.selectedNode?.id);
      this.renderGraph();
    };
  }

  ngAfterViewInit(): void { this.renderGraph(); }

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

    // Keep the D3 datum explicitly typed as BrainNode. The previous map() expression
    // narrowed x/y to required numbers, which produced a different datum type from
    // BrainNode and made d3.drag() / forceSimulation() incompatible with the selection.
    const nodes: BrainNode[] = this.snapshot.nodes.map(n => ({
      ...n,
      x: laneX[n.kind] ?? width / 2,
      y: height / 2,
    }));
    const links: BrainEdge[] = this.snapshot.edges.map(e => ({ ...e }));

    const link = svg.append('g').attr('class', 'links')
      .selectAll<SVGLineElement, BrainEdge>('line')
      .data(links)
      .join('line')
      .attr('class', 'brain-link')
      .attr('marker-end', 'url(#arrow)');

    const node = svg.append('g').attr('class', 'nodes')
      .selectAll<SVGGElement, BrainNode>('g')
      .data(nodes)
      .join('g')
      .attr('class', 'brain-node')
      .on('click', (_, d) => this.selectNode(d))
      .call(
        d3.drag<SVGGElement, BrainNode>()
          .on('start', (event, d) => {
            if (!event.active) this.simulation?.alphaTarget(.25).restart();
            d.x = event.x;
            d.y = event.y;
          })
          .on('drag', (event, d) => {
            d.x = event.x;
            d.y = event.y;
          })
          .on('end', (event) => {
            if (!event.active) this.simulation?.alphaTarget(0);
          }),
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
        link
          .attr('x1', d => this.coordinate(d.source, 'x'))
          .attr('y1', d => this.coordinate(d.source, 'y'))
          .attr('x2', d => this.coordinate(d.target, 'x'))
          .attr('y2', d => this.coordinate(d.target, 'y'));
        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
  }

  private coordinate(value: string | BrainNode, axis: 'x' | 'y'): number {
    if (typeof value === 'string') return 0;
    return value[axis] ?? 0;
  }

  selectNode(node: BrainNode): void { this.selectedNode = node; }
  closeInspector(): void { this.selectedNode = undefined; }

  ngOnDestroy(): void { this.simulation?.stop(); this.socket?.close(); }
}
