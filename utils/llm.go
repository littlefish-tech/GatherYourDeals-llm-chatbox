package utils

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const openRouterURL = "https://openrouter.ai/api/v1/chat/completions"

type LLMLogEntry struct {
	Timestamp        string `json:"timestamp"`
	Provider         string `json:"provider"`
	Model            string `json:"model"`
	Prompt           string `json:"prompt"`
	Response         string `json:"response"`
	PromptTokens     int    `json:"prompt_tokens,omitempty"`
	CompletionTokens int    `json:"completion_tokens,omitempty"`
	TotalTokens      int    `json:"total_tokens,omitempty"`
	LatencyMs        int64  `json:"latency_ms"`
}

type openRouterRequest struct {
	Model    string              `json:"model"`
	Messages []map[string]string `json:"messages"`
}

type openRouterResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func CallOpenRouter(prompt string) (*LLMLogEntry, error) {
	apiKey := strings.TrimSpace(os.Getenv("OPENROUTER_API_KEY"))
	if apiKey == "" {
		return nil, fmt.Errorf("OPENROUTER_API_KEY is not set")
	}

	requestBody := openRouterRequest{
		Model: "openrouter/free",
		Messages: []map[string]string{
			{"role": "user", "content": prompt},
		},
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, openRouterURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("HTTP-Referer", "https://github.com/")
	req.Header.Set("X-Title", "compareprice")

	start := time.Now()

	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	var parsed openRouterResponse
	if err := json.Unmarshal(bodyBytes, &parsed); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	if resp.StatusCode >= http.StatusBadRequest {
		if parsed.Error != nil && parsed.Error.Message != "" {
			return nil, fmt.Errorf("openrouter error (%d): %s", resp.StatusCode, parsed.Error.Message)
		}
		return nil, fmt.Errorf("openrouter error (%d): %s", resp.StatusCode, strings.TrimSpace(string(bodyBytes)))
	}

	if len(parsed.Choices) == 0 {
		return nil, fmt.Errorf("openrouter response did not include any choices")
	}

	return &LLMLogEntry{
		Timestamp:        time.Now().Format(time.RFC3339),
		Provider:         "openrouter",
		Model:            requestBody.Model,
		Prompt:           prompt,
		Response:         parsed.Choices[0].Message.Content,
		PromptTokens:     parsed.Usage.PromptTokens,
		CompletionTokens: parsed.Usage.CompletionTokens,
		TotalTokens:      parsed.Usage.TotalTokens,
		LatencyMs:        time.Since(start).Milliseconds(),
	}, nil
}
