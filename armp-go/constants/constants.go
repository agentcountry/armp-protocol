// Package constants defines ARMP protocol event types and task statuses.
package constants

// Event type constants
const (
	ARMPAccountDataDID = "m.agent.did"
	ARMPMsgType        = "m.agent.message"
	ARMPTaskType       = "m.agent.task"
	ARMPCapRequest     = "m.agent.capability_request"
	ARMPCapResponse    = "m.agent.capability_response"
)

// TaskStatus represents the lifecycle of an ARMP task.
type TaskStatus string

const (
	StatusCreated    TaskStatus = "CREATED"
	StatusAssigned   TaskStatus = "ASSIGNED"
	StatusInProgress TaskStatus = "IN_PROGRESS"
	StatusCompleted  TaskStatus = "COMPLETED"
	StatusFailed     TaskStatus = "FAILED"
	StatusCancelled  TaskStatus = "CANCELLED"
)

// ValidTaskTransitions defines allowed state transitions.
var ValidTaskTransitions = map[TaskStatus][]TaskStatus{
	StatusCreated:    {StatusAssigned, StatusCancelled},
	StatusAssigned:   {StatusInProgress, StatusCancelled},
	StatusInProgress: {StatusCompleted, StatusFailed, StatusCancelled},
	StatusCompleted:  {},
	StatusFailed:     {StatusAssigned}, // retry
	StatusCancelled:  {},
}
