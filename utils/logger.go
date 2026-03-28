package utils

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

var logMu sync.Mutex

func LogLLM(entry *LLMLogEntry) error {
	// Guard concurrent writes in case the project grows beyond a single CLI loop later.
	logMu.Lock()
	defer logMu.Unlock()

	if err := os.MkdirAll("logs", 0755); err != nil {
		return err
	}

	logPath := filepath.Clean("logs/llm_logs.json")

	entries, err := readLogEntries(logPath)
	if err != nil {
		return err
	}

	entries = append(entries, *entry)

	payload, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return err
	}

	if err := os.WriteFile(logPath, append(payload, '\n'), 0644); err != nil {
		return err
	}

	return nil
}

func readLogEntries(path string) ([]LLMLogEntry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []LLMLogEntry{}, nil
		}
		return nil, err
	}

	if len(data) == 0 {
		return []LLMLogEntry{}, nil
	}

	var entries []LLMLogEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return nil, err
	}

	return entries, nil
}
