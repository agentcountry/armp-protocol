// Package models defines ARMP SDK data structures.
package models

import (
	"time"

	"github.com/agentcountry/armp-sdk-go/constants"
)

// Capability represents an agent's capability.
type Capability struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

// AgentCard is an agent's public identity and capability card.
type AgentCard struct {
	Did          string            `json:"did"`
	Name         string            `json:"name"`
	MatrixID     string            `json:"matrix_id"`
	Description  string            `json:"description"`
	Capabilities []Capability      `json:"capabilities"`
	Endpoints    map[string]string `json:"endpoints"`
	Version      string            `json:"version"`
}

// ToDict exports the card as a map.
func (c *AgentCard) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"did":          c.Did,
		"name":         c.Name,
		"matrix_id":    c.MatrixID,
		"description":  c.Description,
		"capabilities": c.Capabilities,
		"endpoints":    c.Endpoints,
		"version":      c.Version,
	}
}

// Message is an ARMP message received from another agent.
type Message struct {
	EventID       string                 `json:"event_id"`
	Sender        string                 `json:"sender"`
	Body          string                 `json:"body"`
	RoomID        string                 `json:"room_id"`
	Timestamp     int64                  `json:"timestamp"`
	Msgtype       string                 `json:"msgtype"`
	ArmpMetadata  map[string]interface{} `json:"armp_metadata"`
}

// TaskHistoryEntry records a state transition.
type TaskHistoryEntry struct {
	From      constants.TaskStatus `json:"from"`
	To        constants.TaskStatus `json:"to"`
	Detail    string               `json:"detail"`
	Timestamp string               `json:"timestamp"`
}

// Task is a unit of work with full lifecycle tracking.
type Task struct {
	TaskID      string                 `json:"task_id"`
	SenderDID   string                 `json:"sender_did"`
	AssigneeDID string                 `json:"assignee_did"`
	Status      constants.TaskStatus   `json:"status"`
	Spec        map[string]interface{} `json:"spec"`
	Result      map[string]interface{} `json:"result"`
	Progress    float64                `json:"progress"`
	History     []TaskHistoryEntry     `json:"history"`
}

// Transition validates and performs a state transition.
func (t *Task) Transition(newStatus constants.TaskStatus, detail string) bool {
	allowed := constants.ValidTaskTransitions[t.Status]
	for _, s := range allowed {
		if s == newStatus {
			t.History = append(t.History, TaskHistoryEntry{
				From:      t.Status,
				To:        newStatus,
				Detail:    detail,
				Timestamp: time.Now().UTC().Format(time.RFC3339),
			})
			t.Status = newStatus
			return true
		}
	}
	return false
}

// NegotiationResult is the outcome of a capability negotiation.
type NegotiationResult struct {
	PeerDID              string     `json:"peer_did"`
	PeerCard             AgentCard  `json:"peer_card"`
	MyCapabilities       []string   `json:"my_capabilities"`
	PeerCapabilities     []string   `json:"peer_capabilities"`
	MutualCapabilities   []string   `json:"mutual_capabilities"`
	MissingCapabilities  []string   `json:"missing_capabilities"`
	Matched              bool       `json:"matched"`
}

// MessageCallback is a callback for incoming messages.
type MessageCallback func(msg *Message)
