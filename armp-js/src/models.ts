/** Data models for ARMP SDK — matches Python amp_sdk.py data structures. */

import { TaskStatus, VALID_TASK_TRANSITIONS } from "./constants";

export interface Capability {
  name: string;
  description: string;
}

export class AgentCard {
  did: string;
  name: string;
  matrixId: string;
  description: string;
  capabilities: Capability[];
  endpoints: Record<string, string>;
  version: string;

  constructor(params: {
    did: string;
    name: string;
    matrixId: string;
    description?: string;
    capabilities?: Capability[];
    endpoints?: Record<string, string>;
    version?: string;
  }) {
    this.did = params.did;
    this.name = params.name;
    this.matrixId = params.matrixId;
    this.description = params.description || "";
    this.capabilities = params.capabilities || [];
    this.endpoints = params.endpoints || {};
    this.version = params.version || "0.3.0";
  }

  toDict(): Record<string, unknown> {
    return {
      did: this.did,
      name: this.name,
      matrix_id: this.matrixId,
      description: this.description,
      capabilities: this.capabilities,
      endpoints: this.endpoints,
      version: this.version,
    };
  }

  static fromDict(data: Record<string, unknown>): AgentCard {
    return new AgentCard({
      did: (data.did as string) || "",
      name: (data.name as string) || "",
      matrixId: (data.matrix_id as string) || "",
      description: (data.description as string) || "",
      capabilities: (data.capabilities as Capability[]) || [],
      endpoints: (data.endpoints as Record<string, string>) || {},
      version: (data.version as string) || "0.3.0",
    });
  }
}

export class Message {
  eventId: string;
  sender: string;
  body: string;
  roomId: string;
  timestamp: number;
  msgtype: string;
  armpMetadata: Record<string, unknown>;

  constructor(params: {
    eventId: string;
    sender: string;
    body: string;
    roomId: string;
    timestamp: number;
    msgtype?: string;
    armpMetadata?: Record<string, unknown>;
  }) {
    this.eventId = params.eventId;
    this.sender = params.sender;
    this.body = params.body;
    this.roomId = params.roomId;
    this.timestamp = params.timestamp;
    this.msgtype = params.msgtype || "m.text";
    this.armpMetadata = params.armpMetadata || {};
  }
}

export interface TaskHistoryEntry {
  from: TaskStatus;
  to: TaskStatus;
  detail: string;
  timestamp: string;
}

export class Task {
  taskId: string;
  senderDid: string;
  assigneeDid: string;
  status: TaskStatus;
  spec: Record<string, unknown>;
  result: Record<string, unknown> | null;
  progress: number;
  history: TaskHistoryEntry[];

  constructor(params: {
    taskId: string;
    senderDid: string;
    assigneeDid: string;
    status?: TaskStatus;
    spec?: Record<string, unknown>;
    result?: Record<string, unknown> | null;
  }) {
    this.taskId = params.taskId;
    this.senderDid = params.senderDid;
    this.assigneeDid = params.assigneeDid;
    this.status = params.status || "CREATED";
    this.spec = params.spec || {};
    this.result = params.result || null;
    this.progress = 0;
    this.history = [];
  }

  transition(newStatus: TaskStatus, detail: string = ""): boolean {
    const allowed = VALID_TASK_TRANSITIONS[this.status] || [];
    if (!allowed.includes(newStatus)) {
      console.warn(`Invalid task transition: ${this.status} → ${newStatus}`);
      return false;
    }
    const oldStatus = this.status;
    this.status = newStatus;
    this.history.push({
      from: oldStatus,
      to: newStatus,
      detail,
      timestamp: new Date().toISOString(),
    });
    console.info(`Task ${this.taskId}: ${oldStatus} → ${newStatus}`);
    return true;
  }
}

export class NegotiationResult {
  peerDid: string;
  peerCard: AgentCard;
  myCapabilities: string[];
  peerCapabilities: string[];
  mutualCapabilities: string[];
  missingCapabilities: string[];
  matched: boolean;

  constructor(params: {
    peerDid: string;
    peerCard: AgentCard;
    myCapabilities: string[];
    peerCapabilities: string[];
    mutualCapabilities: string[];
    missingCapabilities: string[];
    matched: boolean;
  }) {
    this.peerDid = params.peerDid;
    this.peerCard = params.peerCard;
    this.myCapabilities = params.myCapabilities;
    this.peerCapabilities = params.peerCapabilities;
    this.mutualCapabilities = params.mutualCapabilities;
    this.missingCapabilities = params.missingCapabilities;
    this.matched = params.matched;
  }
}

export type MessageCallback = (msg: Message) => Promise<void>;
