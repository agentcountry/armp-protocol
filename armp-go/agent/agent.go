// Package agent provides the ARMP Agent — real-time communication via Matrix.
//
// Quickstart:
//
//	import "github.com/agentcountry/armp-sdk-go/agent"
//	a := agent.New("AGNT...", "https://armp-group.org", "myagent", "password")
//	defer a.Stop()
//	a.Start()
//	a.SendMessage("@peer:armp-group.org", "Hello from Go!")
package agent

import (
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/agentcountry/armp-sdk-go/constants"
	"github.com/agentcountry/armp-sdk-go/models"
	"github.com/google/uuid"
)

// Agent is an ARMP-compliant AI agent backed by Matrix.
//
// Note: This is a skeleton implementation. Full Matrix integration
// requires mautrix-go for production use. This version demonstrates
// the API surface and data model.
type Agent struct {
	Did        string
	Homeserver string
	Username   string
	password   string

	started  bool
	card     *models.AgentCard
	msgCB    models.MessageCallback
	peers    map[string]*models.AgentCard
	tasks    map[string]*models.Task
	mu       sync.RWMutex
}

// New creates a new ARMP Agent.
func New(did, homeserver, username, password string) *Agent {
	return &Agent{
		Did:        did,
		Homeserver: strings.TrimRight(homeserver, "/"),
		Username:   username,
		password:   password,
		peers:      make(map[string]*models.AgentCard),
		tasks:      make(map[string]*models.Task),
		card: &models.AgentCard{
			Did:      did,
			Name:     username,
			MatrixID: fmt.Sprintf("@%s:%s", username, strings.TrimPrefix(homeserver, "https://")),
			Version:  "0.4.0",
		},
	}
}

// Start connects to the Matrix homeserver and begins syncing.
// In production, this would use mautrix-go.
func (a *Agent) Start() error {
	log.Printf("[ARMP] Agent %s connecting to %s", a.Did, a.Homeserver)

	// TODO: mautrix-go login + sync loop
	// client, _ := mautrix.NewClient(a.Homeserver, "", "")
	// client.Login(&mautrix.ReqLogin{...})
	// client.Sync()

	a.started = true
	log.Printf("[ARMP] Agent %s is online", a.Did)
	return nil
}

// Stop disconnects from the homeserver.
func (a *Agent) Stop() {
	a.started = false
	log.Printf("[ARMP] Agent %s is offline", a.Did)
}

// IsOnline returns whether the agent is connected.
func (a *Agent) IsOnline() bool {
	return a.started
}

// UserID returns the Matrix user ID.
func (a *Agent) UserID() string {
	return fmt.Sprintf("@%s:%s", a.Username, strings.TrimPrefix(a.Homeserver, "https://"))
}

// Card returns the agent's capability card.
func (a *Agent) Card() *models.AgentCard {
	return a.card
}

// ── Messaging ────────────────────────────────────────────

// OnMessage registers a callback for incoming messages.
func (a *Agent) OnMessage(cb models.MessageCallback) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.msgCB = cb
}

// SendMessage sends a text message to a target (room or user).
func (a *Agent) SendMessage(target, body string) string {
	eventID := uuid.New().String()
	log.Printf("→ [%s] %s... (event=%s)", target, body[:min(len(body), 50)], eventID)
	return eventID
}

// ── Presence ─────────────────────────────────────────────

// SetPresence updates the agent's online status.
func (a *Agent) SetPresence(status string) {
	log.Printf("[ARMP] Presence: %s → %s", a.Did, status)
}

// ── Typing / Read Receipts ───────────────────────────────

// Typing sends a typing indicator notification.
func (a *Agent) Typing(roomID string, isTyping bool) {
	if isTyping {
		log.Printf("[ARMP] Typing in %s...", roomID)
	}
}

// MarkRead sends a read receipt for a message.
func (a *Agent) MarkRead(roomID, eventID string) {
	log.Printf("[ARMP] Read receipt: %s in %s", eventID, roomID)
}

// ── Rooms ────────────────────────────────────────────────

// CreateRoom creates a new Matrix room.
func (a *Agent) CreateRoom(name string, members []string, isDirect bool) string {
	roomID := fmt.Sprintf("!%s:%s", uuid.New().String()[:18],
		strings.TrimPrefix(a.Homeserver, "https://"))
	log.Printf("[ARMP] Room created: %s (%s)", name, roomID)
	return roomID
}

// ── Tasks ────────────────────────────────────────────────

// CreateTask creates a new task.
func (a *Agent) CreateTask(assigneeDID string, spec map[string]interface{}) *models.Task {
	task := &models.Task{
		TaskID:      uuid.New().String(),
		SenderDID:   a.Did,
		AssigneeDID: assigneeDID,
		Status:      constants.StatusCreated,
		Spec:        spec,
	}
	a.mu.Lock()
	a.tasks[task.TaskID] = task
	a.mu.Unlock()

	log.Printf("[ARMP] Task %s → %s [CREATED]", task.TaskID, assigneeDID)
	return task
}

// AssignTask moves a task to ASSIGNED.
func (a *Agent) AssignTask(task *models.Task) bool {
	return task.Transition(constants.StatusAssigned, "Task assigned")
}

// StartTask moves a task to IN_PROGRESS.
func (a *Agent) StartTask(task *models.Task) bool {
	return task.Transition(constants.StatusInProgress, "Work started")
}

// CompleteTask marks a task as completed.
func (a *Agent) CompleteTask(task *models.Task, result map[string]interface{}) bool {
	if !task.Transition(constants.StatusCompleted, "Task completed") {
		return false
	}
	task.Result = result
	task.Progress = 1.0
	return true
}

// FailTask marks a task as failed.
func (a *Agent) FailTask(task *models.Task, reason string) bool {
	return task.Transition(constants.StatusFailed, reason)
}

// GetTask retrieves a task by ID.
func (a *Agent) GetTask(taskID string) *models.Task {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.tasks[taskID]
}

// ── Capabilities ─────────────────────────────────────────

// SetCapability declares a capability on this agent.
func (a *Agent) SetCapability(name, description string) {
	a.card.Capabilities = append(a.card.Capabilities, models.Capability{
		Name:        name,
		Description: description,
	})
	log.Printf("[ARMP] Capability: %s — %s", name, description)
}

// Negotiate performs capability negotiation with a peer.
func (a *Agent) Negotiate(peerUserID string) *models.NegotiationResult {
	myCaps := make([]string, len(a.card.Capabilities))
	for i, c := range a.card.Capabilities {
		myCaps[i] = c.Name
	}

	// In production: send ARMP_CAP_REQUEST and wait for ARMP_CAP_RESPONSE
	time.Sleep(500 * time.Millisecond) // Simulated latency

	return &models.NegotiationResult{
		PeerDID:             "",
		PeerCard:            models.AgentCard{},
		MyCapabilities:      myCaps,
		PeerCapabilities:    []string{},
		MutualCapabilities:  []string{},
		MissingCapabilities: []string{},
		Matched:             true,
	}
}

// DiscoverAgents finds agents by capability.
func (a *Agent) DiscoverAgents(capability string) []*models.AgentCard {
	a.mu.RLock()
	defer a.mu.RUnlock()

	var results []*models.AgentCard
	for _, peer := range a.peers {
		if capability == "" {
			results = append(results, peer)
			continue
		}
		for _, c := range peer.Capabilities {
			if strings.Contains(strings.ToLower(c.Name), strings.ToLower(capability)) {
				results = append(results, peer)
				break
			}
		}
	}
	return results
}

// ── Smart Routing ────────────────────────────────────────

// ScoreCapabilityMatch scores how well an agent's capabilities match a task.
func (a *Agent) ScoreCapabilityMatch(taskSpec map[string]interface{}, card *models.AgentCard) float64 {
	// Extract required and preferred capabilities from spec
	required := toStringSlice(taskSpec["capabilities_required"])
	preferred := toStringSlice(taskSpec["capabilities_preferred"])

	if len(required) == 0 && len(preferred) == 0 {
		return 0.5
	}

	agentCaps := make(map[string]bool)
	for _, c := range card.Capabilities {
		agentCaps[strings.ToLower(c.Name)] = true
	}

	// Required check
	for _, r := range required {
		if !agentCaps[strings.ToLower(r)] {
			return 0.0
		}
	}

	requiredScore := 0.6
	if len(required) == 0 {
		requiredScore = 0.6
	}

	preferredScore := 0.4
	if len(preferred) > 0 {
		matches := 0
		for _, p := range preferred {
			if agentCaps[strings.ToLower(p)] {
				matches++
			}
		}
		preferredScore = float64(matches) / float64(len(preferred)) * 0.4
	}

	score := requiredScore + preferredScore
	if score > 1.0 {
		score = 1.0
	}
	return score
}

// RouteTask smart-routes a task to the best-capable agent.
func (a *Agent) RouteTask(taskSpec map[string]interface{}) (*models.AgentCard, float64) {
	candidates := a.DiscoverAgents("")

	var bestCard *models.AgentCard
	bestScore := 0.0

	for _, card := range candidates {
		score := a.ScoreCapabilityMatch(taskSpec, card)
		if score > bestScore {
			bestScore = score
			bestCard = card
		}
	}

	return bestCard, bestScore
}

// ── Helpers ──────────────────────────────────────────────

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func toStringSlice(v interface{}) []string {
	switch val := v.(type) {
	case []string:
		return val
	case []interface{}:
		result := make([]string, len(val))
		for i, item := range val {
			result[i] = fmt.Sprintf("%v", item)
		}
		return result
	}
	return nil
}
