package agent

// DetectionResult holds the outcome of probing a single agent on the current system.
type DetectionResult struct {
	Agent     AgentID
	Found     bool
	ConfigDir string
	Binary    string
}
