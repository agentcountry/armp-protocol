/**
 * ARMP Agent — Matrix-backed real-time communication agent.
 *
 * Quickstart:
 *   import { Agent } from "armp-sdk";
 *   const agent = new Agent({ did: "...", homeserver: "https://armp-group.org", username: "myagent", password: "..." });
 *   await agent.start();
 *   await agent.sendMessage("@peer:armp-group.org", "Hello!");
 *   await agent.stop();
 */

import * as sdk from "matrix-js-sdk";
import { v4 as uuidv4 } from "uuid";
import {
  ARMP_CAP_REQUEST,
  ARMP_CAP_RESPONSE,
  ARMP_TASK_TYPE,
  VALID_TASK_TRANSITIONS,
} from "./constants";
import {
  AgentCard,
  Capability,
  Message,
  MessageCallback,
  NegotiationResult,
  Task,
} from "./models";

export interface AgentOptions {
  did: string;
  homeserver: string;
  username: string;
  password?: string;
  accessToken?: string;
}

export class Agent {
  readonly did: string;
  readonly homeserver: string;
  readonly username: string;

  private client: sdk.MatrixClient;
  private started: boolean = false;
  private card: AgentCard | null = null;
  private messageCallback: MessageCallback | null = null;
  private peers: Map<string, AgentCard> = new Map();
  private activeTasks: Map<string, Task> = new Map();
  private peerUserId: string | null = null;

  constructor(options: AgentOptions) {
    this.did = options.did;
    this.homeserver = options.homeserver.replace(/\/$/, "");
    this.username = options.username;

    this.client = sdk.createClient({
      baseUrl: this.homeserver,
      accessToken: options.accessToken,
      userId: options.accessToken ? `@${options.username}:${new URL(this.homeserver).host}` : undefined,
    });
  }

  // ── Lifecycle ────────────────────────────────────────

  async start(): Promise<void> {
    if (!this.client.getAccessToken() && !this.client.getAccessToken()) {
      const resp = await this.client.login("m.login.password", {
        user: this.username,
        password: "TODO-fix-init",
      });
      // matrix-js-sdk login flows differ; the constructor handles accessToken
    }

    // Re-login if needed
    const loginResp = await this.client.loginWithPassword(this.username, (this as any)._password || "");
    this.peerUserId = `@${this.username}:${new URL(this.homeserver).host}`;

    this.started = true;
    this.client.startClient({ initialSyncLimit: 10 });

    // Set presence
    this.client.setPresence("online");

    // Listen for events
    this.client.on(sdk.RoomEvent.Timeline, this._onTimelineEvent.bind(this));

    console.info(`Agent ${this.did} is online (${this.client.getUserId()})`);
  }

  /** Note: matrix-js-sdk needs password passed through. Override init. */
  async startWithPassword(password: string): Promise<void> {
    const loginResp = await this.client.loginWithPassword(this.username, password);
    this.peerUserId = loginResp.userId;

    this.started = true;
    this.client.startClient({ initialSyncLimit: 10 });
    this.client.setPresence("online");
    this.client.on("Room.timeline", this._onTimelineEvent.bind(this));

    console.info(`Agent ${this.did} is online (${this.client.getUserId()})`);
  }

  async stop(): Promise<void> {
    this.started = false;
    this.client.setPresence("offline");
    this.client.stopClient();
    console.info(`Agent ${this.did} is offline`);
  }

  get userId(): string {
    return this.client.getUserId() || "";
  }

  get isOnline(): boolean {
    return this.started;
  }

  // ── Event handling ──────────────────────────────────

  private _onTimelineEvent(
    event: sdk.MatrixEvent,
    room: sdk.Room | undefined
  ): void {
    if (!room) return;
    if (event.getSender() === this.client.getUserId()) return;

    const eventType = event.getType();
    const content = event.getContent();
    const agentMeta = content["m.agent"] || {};

    if (eventType === ARMP_CAP_REQUEST) {
      this._handleCapRequest(room.roomId, content, agentMeta);
      return;
    }
    if (eventType === ARMP_CAP_RESPONSE) {
      this._handleCapResponse(agentMeta);
      return;
    }
    if (eventType === ARMP_TASK_TYPE) {
      const taskId = agentMeta.task_id || "";
      const status = agentMeta.status || "";
      console.info(`Task event: ${taskId} status=${status}`);
    }

    const body = content.body;
    if (!body) return;

    const msg = new Message({
      eventId: event.getId() || "",
      sender: event.getSender() || "",
      body,
      roomId: room.roomId,
      timestamp: event.getTs(),
      msgtype: content.msgtype || "m.text",
      armpMetadata: agentMeta,
    });

    // Read receipt
    this.client.sendReadReceipt(event as any);

    if (this.messageCallback) {
      this.messageCallback(msg);
    }
  }

  private _handleCapRequest(
    roomId: string,
    _content: Record<string, unknown>,
    agentMeta: Record<string, unknown>
  ): void {
    if (!this.card) return;
    this.client.sendEvent(roomId, ARMP_CAP_RESPONSE, {
      body: `Capability card for ${this.did}`,
      "m.agent": {
        request_id: agentMeta.request_id,
        agent_card: this.card.toDict(),
      },
    });
  }

  private _handleCapResponse(agentMeta: Record<string, unknown>): void {
    const cardData = agentMeta.agent_card as Record<string, unknown> | undefined;
    if (cardData?.did) {
      const peerCard = AgentCard.fromDict(cardData);
      this.peers.set(peerCard.did, peerCard);
      console.info(
        `Stored card for ${peerCard.did}: ${peerCard.capabilities.map(c => c.name)}`
      );
    }
  }

  // ── Messaging ────────────────────────────────────────

  async onMessage(callback: MessageCallback): Promise<void> {
    this.messageCallback = callback;
  }

  async sendMessage(
    target: string,
    body: string,
    msgtype: string = "m.text",
    armpMeta: Record<string, unknown> = {}
  ): Promise<string> {
    const roomId = target.startsWith("!") ? target : await this._ensureDm(target);

    this.client.sendTyping(roomId, true, 15000);

    const content: Record<string, unknown> = {
      body,
      msgtype,
    };
    if (Object.keys(armpMeta).length > 0) {
      content["m.agent"] = armpMeta;
    }

    const resp = await this.client.sendMessage(roomId, content);

    this.client.sendTyping(roomId, false, 0);

    console.info(`→ [${target}] ${body.slice(0, 50)}...`);
    return resp.event_id || "";
  }

  // ── Rooms ────────────────────────────────────────────

  async createRoom(
    name: string,
    members: string[] = [],
    isDirect: boolean = false,
    topic: string = ""
  ): Promise<string> {
    const resp = await this.client.createRoom({
      name,
      topic,
      visibility: isDirect ? "private" : "private",
      invite: members,
      preset: isDirect ? "trusted_private_chat" : "private_chat",
    });
    console.info(`Room created: ${name} (${resp.room_id})`);
    return resp.room_id;
  }

  async joinRoom(roomId: string): Promise<void> {
    await this.client.joinRoom(roomId);
  }

  async leaveRoom(roomId: string): Promise<void> {
    await this.client.leave(roomId);
  }

  async invite(roomId: string, userId: string): Promise<void> {
    await this.client.invite(roomId, userId);
  }

  private async _ensureDm(userId: string): Promise<string> {
    const rooms = this.client.getRooms();
    for (const room of rooms) {
      const members = room.getJoinedMembers();
      if (
        members.length === 2 &&
        members.some((m) => m.userId === userId)
      ) {
        return room.roomId;
      }
    }
    return this.createRoom(
      `DM: ${this.username} ↔ ${userId}`,
      [userId],
      true
    );
  }

  // ── Presence ─────────────────────────────────────────

  setPresence(status: "online" | "offline" | "unavailable"): void {
    this.client.setPresence(status);
  }

  // ── Typing / Read receipts ───────────────────────────

  async typing(roomId: string, isTyping: boolean, timeout: number = 15000): Promise<void> {
    this.client.sendTyping(roomId, isTyping, timeout);
  }

  async markRead(roomId: string, eventId: string): Promise<void> {
    this.client.sendReadReceipt({ roomId, eventId } as any);
  }

  // ── Tasks ────────────────────────────────────────────

  async createTask(
    assigneeDid: string,
    spec: Record<string, unknown>,
    assigneeUserId: string = ""
  ): Promise<Task> {
    const task = new Task({
      taskId: uuidv4(),
      senderDid: this.did,
      assigneeDid,
      spec,
      status: "CREATED",
    });

    this.activeTasks.set(task.taskId, task);

    if (assigneeUserId) {
      const roomId = await this._ensureDm(assigneeUserId);
      await this.client.sendEvent(roomId, ARMP_TASK_TYPE, {
        body: (spec.description as string) || "New task",
        "m.agent": {
          task_id: task.taskId,
          status: "CREATED",
          sender_did: this.did,
          assignee_did: assigneeDid,
          spec,
        },
      });
    }

    console.info(`Task ${task.taskId} → ${assigneeDid} [CREATED]`);
    return task;
  }

  async assignTask(task: Task, assigneeUserId: string): Promise<boolean> {
    if (!task.transition("ASSIGNED", `Assigned to ${assigneeUserId}`)) return false;
    const roomId = await this._ensureDm(assigneeUserId);
    await this.client.sendEvent(roomId, ARMP_TASK_TYPE, {
      body: `Task assigned: ${task.spec.description || task.taskId}`,
      "m.agent": {
        task_id: task.taskId,
        status: "ASSIGNED",
        sender_did: this.did,
        assignee_did: task.assigneeDid,
      },
    });
    return true;
  }

  async startTask(task: Task, roomId: string): Promise<boolean> {
    if (!task.transition("IN_PROGRESS", "Work started")) return false;
    await this.client.sendEvent(roomId, ARMP_TASK_TYPE, {
      body: `Task in progress: ${task.spec.description || task.taskId}`,
      "m.agent": {
        task_id: task.taskId,
        status: "IN_PROGRESS",
        sender_did: this.did,
        assignee_did: task.assigneeDid,
      },
    });
    return true;
  }

  async completeTask(task: Task, roomId: string, result: Record<string, unknown> = {}): Promise<boolean> {
    if (!task.transition("COMPLETED", "Task completed")) return false;
    task.result = result;
    task.progress = 1.0;
    await this.client.sendEvent(roomId, ARMP_TASK_TYPE, {
      body: `Task completed: ${task.spec.description || task.taskId}`,
      "m.agent": {
        task_id: task.taskId,
        status: "COMPLETED",
        sender_did: this.did,
        assignee_did: task.assigneeDid,
        result,
      },
    });
    return true;
  }

  getTask(taskId: string): Task | undefined {
    return this.activeTasks.get(taskId);
  }

  // ── Capabilities ─────────────────────────────────────

  setCapability(name: string, description: string = ""): void {
    if (!this.card) {
      this.card = new AgentCard({
        did: this.did,
        name: this.username,
        matrixId: this.client.getUserId() || "",
      });
    }
    this.card.capabilities.push({ name, description });
  }

  async negotiate(peerUserId: string): Promise<NegotiationResult> {
    if (!this.card) throw new Error("No AgentCard — call setCapability() first");

    const roomId = await this._ensureDm(peerUserId);
    const requestId = uuidv4();

    await this.client.sendEvent(roomId, ARMP_CAP_REQUEST, {
      body: `Capability request from ${this.did}`,
      "m.agent": {
        request_id: requestId,
        agent_card: this.card.toDict(),
      },
    });

    // Wait for response (poll up to 10s)
    let peerCard: AgentCard | null = null;
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 500));
      const cards = Array.from(this.peers.values());
      if (cards.length > 0) {
        peerCard = cards[0];
        break;
      }
    }

    if (!peerCard) throw new Error("Peer did not respond in 10 seconds");

    const myCaps = new Set(this.card.capabilities.map((c) => c.name));
    const peerCaps = new Set(peerCard.capabilities.map((c) => c.name));
    const mutual = [...myCaps].filter((c) => peerCaps.has(c));
    const missing = [...peerCaps].filter((c) => !myCaps.has(c));

    return new NegotiationResult({
      peerDid: peerCard.did,
      peerCard,
      myCapabilities: [...myCaps],
      peerCapabilities: [...peerCaps],
      mutualCapabilities: mutual,
      missingCapabilities: missing,
      matched: mutual.length > 0 || true,
    });
  }

  async discoverAgents(capability: string = ""): Promise<AgentCard[]> {
    const results: AgentCard[] = [];

    for (const peer of this.peers.values()) {
      if (
        !capability ||
        peer.capabilities.some((c) =>
          c.name.toLowerCase().includes(capability.toLowerCase())
        )
      ) {
        results.push(peer);
      }
    }

    // TODO: matrix-js-sdk room directory + state event scanning

    console.info(`Discovered ${results.length} agents matching '${capability}'`);
    return results;
  }

  // ── Smart Routing ────────────────────────────────────

  private _scoreCapabilityMatch(taskSpec: Record<string, unknown>, agentCard: AgentCard): number {
    const required = (taskSpec.capabilities_required as string[]) || [];
    const preferred = (taskSpec.capabilities_preferred as string[]) || [];

    if (required.length === 0 && preferred.length === 0) return 0.5;

    const agentCaps = new Set(agentCard.capabilities.map((c) => c.name.toLowerCase()));
    const requiredLower = new Set(required.map((r) => r.toLowerCase()));
    const preferredLower = new Set(preferred.map((p) => p.toLowerCase()));

    if (requiredLower.size > 0 && ![...requiredLower].every((r) => agentCaps.has(r))) {
      return 0.0;
    }

    const requiredScore = requiredLower.size > 0 ? 1.0 * 0.6 : 0.6;
    let preferredScore = 0.0;
    if (preferredLower.size > 0) {
      const matches = [...preferredLower].filter((p) => agentCaps.has(p));
      preferredScore = (matches.length / preferredLower.size) * 0.4;
    } else {
      preferredScore = 0.4;
    }

    return Math.min(1.0, requiredScore + preferredScore);
  }

  async routeTask(
    taskSpec: Record<string, unknown>,
    capability: string = ""
  ): Promise<{ bestCard: AgentCard | null; bestUserId: string | null; score: number }> {
    const candidates = await this.discoverAgents(capability);

    if (candidates.length === 0) {
      return { bestCard: null, bestUserId: null, score: 0.0 };
    }

    let bestCard: AgentCard | null = null;
    let bestScore = 0.0;

    for (const card of candidates) {
      const score = this._scoreCapabilityMatch(taskSpec, card);
      if (score > bestScore) {
        bestScore = score;
        bestCard = card;
      }
    }

    if (bestCard && bestScore > 0.0) {
      console.info(`Routed to ${bestCard.name} (score=${bestScore.toFixed(2)})`);
      return { bestCard, bestUserId: bestCard.matrixId, score: bestScore };
    }

    return { bestCard: null, bestUserId: null, score: 0.0 };
  }
}
