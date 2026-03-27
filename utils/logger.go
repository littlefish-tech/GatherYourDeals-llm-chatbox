package utils

import (
	"encoding/json"
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

	// JSONL keeps one record per line, which is easy to append and analyze later.
	file, err := os.OpenFile(filepath.Clean("logs/llm_logs.jsonl"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer file.Close()

	return json.NewEncoder(file).Encode(entry)
}
