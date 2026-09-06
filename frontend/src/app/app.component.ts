import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';

interface BrainNode { id: string; kind: string; label: string; }
interface BrainSnapshot { phase: string; nodes: BrainNode[]; edges: { source: string; target: string; relation: string }[]; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit, OnDestroy {
  snapshot: BrainSnapshot = { phase: 'PRE_MARKET', nodes: [], edges: [] };
  private socket?: WebSocket;

  ngOnInit(): void {
    this.socket = new WebSocket('ws://localhost:8000/ws/market-brain');
    this.socket.onmessage = (event: MessageEvent<string>) => {
      this.snapshot = JSON.parse(event.data) as BrainSnapshot;
    };
  }

  ngOnDestroy(): void {
    this.socket?.close();
  }
}
