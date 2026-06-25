/** ARMP event type constants. */

export const ARMP_ACCOUNT_DATA_DID = "m.agent.did";
export const ARMP_MSG_TYPE = "m.agent.message";
export const ARMP_TASK_TYPE = "m.agent.task";
export const ARMP_CAP_REQUEST = "m.agent.capability_request";
export const ARMP_CAP_RESPONSE = "m.agent.capability_response";

export const TASK_STATUSES = [
  "CREATED",
  "ASSIGNED",
  "IN_PROGRESS",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const VALID_TASK_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  CREATED: ["ASSIGNED", "CANCELLED"],
  ASSIGNED: ["IN_PROGRESS", "CANCELLED"],
  IN_PROGRESS: ["COMPLETED", "FAILED", "CANCELLED"],
  COMPLETED: [],
  FAILED: ["ASSIGNED"], // retry
  CANCELLED: [],
};
