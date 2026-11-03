/** One WebSocket per conversation: ask / cancel / heartbeat / last_event_id resume. */

import type { ServerEvent } from "./types";

const STORAGE_SESSION = "axiom-research.session_id";
const STORAGE_LAST_EVENT = "axiom-research.last_event_id";
const HEARTBEAT_MS = 25_000;

export type WsHandlers = {
  onEvent: (event: ServerEvent) => void;
  onStatus: (status: "connecting" | "open" | "closed" | "error") => void;
};

function defaultWsUrl(): string {
  return (
    process.env.NEXT_PUBLIC_WS_URL?.trim() ||
    "ws://127.0.0.1:8200/ws/session"
  );
}

export function loadPersistedSession(): {
  sessionId: string | null;
  lastEventId: string | null;
} {
  if (typeof window === "undefined") {
    return { sessionId: null, lastEventId: null };
  }
  return {
    sessionId: sessionStorage.getItem(STORAGE_SESSION),
    lastEventId: sessionStorage.getItem(STORAGE_LAST_EVENT),
  };
}

export function persistSession(sessionId: string, lastEventId: string | null) {
  sessionStorage.setItem(STORAGE_SESSION, sessionId);
  if (lastEventId) {
    sessionStorage.setItem(STORAGE_LAST_EVENT, lastEventId);
  }
}

export class SessionSocket {
  private ws: WebSocket | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;
  sessionId: string | null = null;
  lastEventId: string | null = null;
  private handlers: WsHandlers;

  constructor(handlers: WsHandlers) {
    this.handlers = handlers;
    const persisted = loadPersistedSession();
    this.sessionId = persisted.sessionId;
    this.lastEventId = persisted.lastEventId;
  }

  connect(baseUrl: string = defaultWsUrl()) {
    this.intentionalClose = false;
    this.handlers.onStatus("connecting");
    const url = new URL(baseUrl);
    if (this.sessionId) {
      url.searchParams.set("session_id", this.sessionId);
    }
    const ws = new WebSocket(url.toString());
    this.ws = ws;

    ws.onopen = () => {
      this.handlers.onStatus("open");
      this.startHeartbeat();
      // Resume missed events without restarting a live run.
      this.sendHeartbeat();
    };

    ws.onmessage = (msg) => {
      let data: ServerEvent;
      try {
        data = JSON.parse(String(msg.data)) as ServerEvent;
      } catch {
        return;
      }
      if (data.session_id) {
        this.sessionId = data.session_id;
      }
      if (data.event_id && data.type !== "heartbeat") {
        this.lastEventId = data.event_id;
      } else if (data.type === "heartbeat" && data.last_event_id) {
        // Server may echo last_event_id; keep ours if newer path unknown.
        if (!this.lastEventId) {
          this.lastEventId = data.last_event_id;
        }
      }
      if (this.sessionId) {
        persistSession(this.sessionId, this.lastEventId);
      }
      this.handlers.onEvent(data);
    };

    ws.onerror = () => {
      this.handlers.onStatus("error");
    };

    ws.onclose = () => {
      this.stopHeartbeat();
      this.handlers.onStatus("closed");
      this.ws = null;
      if (!this.intentionalClose) {
        window.setTimeout(() => this.connect(baseUrl), 1500);
      }
    };
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => this.sendHeartbeat(), HEARTBEAT_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private sendHeartbeat() {
    this.send({
      type: "heartbeat",
      last_event_id: this.lastEventId,
    });
  }

  ask(question: string) {
    this.send({
      type: "ask",
      question,
      last_event_id: this.lastEventId,
    });
  }

  cancel(runId: string | null = null) {
    this.send({
      type: "cancel",
      run_id: runId,
    });
  }

  private send(payload: Record<string, unknown>) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(payload));
  }

  close() {
    this.intentionalClose = true;
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
  }
}
