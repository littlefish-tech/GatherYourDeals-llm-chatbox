package utils

import (
	"fmt"
	"os"
	"net/http"
	"encoding/json"
	"strings"
)
// ---------------------------
// STRUCTS
// ---------------------------
type ChatRequest struct {
	Messages []struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"messages"`
	Provider string `json:"provider"`
}

type Usage struct {
    InputTokens  int `json:"input_tokens"`
    OutputTokens int `json:"output_tokens"`
}

type ErrorResponse struct {
    Code    string `json:"code"`
    Message string `json:"message"`
}

type ChatResponse struct {
    Message struct {
        Role    string `json:"role"`
        Content string `json:"content"`
    } `json:"message"`

    StopReason string `json:"stop_reason"`

    Usage Usage `json:"usage"`
}
type HealthResponse struct {
    Status string `json:"status"`
}

func HandleHealth(w http.ResponseWriter, r *http.Request) {
    json.NewEncoder(w).Encode(HealthResponse{
        Status: "ok",
    })
}
// ---------------------------
// MAIN ENTRY
// ---------------------------
func HandleChat(req ChatRequest, authHeader string) (ChatResponse, error) {

    if authHeader == "" {
        return ChatResponse{}, fmt.Errorf("missing Authorization header")
    }

    userQuestion := req.Messages[len(req.Messages)-1].Content

    // ---------------------------
    // FETCH RECEIPTS
    // ---------------------------
    context, err := fetchReceipts(authHeader)
    if err != nil || strings.Contains(context, "invalid") || strings.Contains(context, "Failed") {
        context = "No purchase history available"
    }

    // ---------------------------
    // BUILD PROMPT
    // ---------------------------
    prompt := fmt.Sprintf(`
	User purchase history:
	%s

	User question:
	%s
	`, context, userQuestion)

    provider := req.Provider
    if provider != "" {
        os.Setenv("LLM_PROVIDER", provider)
    }

    // ---------------------------
    // INIT RESPONSE
    // ---------------------------
    response := ChatResponse{}
    response.Message.Role = "assistant"

    // ---------------------------
    // COMPARISON MODE
    // ---------------------------
    if provider == "both" {
        comp, err := CallBothProviders(prompt)
        if err != nil {
            response.StopReason = "error"
            return response, err
        }

        response.Message.Content = BuildComparisonSummary(comp)
        response.StopReason = "end_turn"

        response.Usage = Usage{
            InputTokens: 0,
            OutputTokens: 0,
        }

        return response, nil
    }

    // ---------------------------
    // SINGLE PROVIDER
    // ---------------------------
    result, err := CallLLM(prompt)
	if err != nil {
		fmt.Println("FINAL ERROR:", err)
		response.StopReason = "error"
		return response, err
	}

    response.Message.Content = result.Response
    response.StopReason = result.StopReason //

    response.Usage = Usage{
        InputTokens:  result.LLMInputTokens,
        OutputTokens: result.LLMOutputTokens,
    }

    return response, nil
}

func fetchReceipts(authHeader string) (string, error) {
	url := "https://gatheryourdeals-data-production.up.railway.app/api/v1/receipts"

	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Authorization", authHeader)

	resp, err := (&http.Client{}).Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var data map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&data)
	if err != nil {
		return "", err
	}

	itemsRaw, ok := data["items"]
	if !ok {
		return "Failed to fetch receipts (invalid or expired token)", nil
	}

	items, ok := itemsRaw.([]interface{})
	if !ok {
		return "Invalid data format", nil
	}

	if len(items) == 0 {
		return "No recent purchases found.", nil
	}

	lines := []string{}
	for _, item := range items {
		m := item.(map[string]interface{})

		name := m["product_name"]
		price := m["price"]

		lines = append(lines, fmt.Sprintf("%v - %v", name, price))
	}

	return strings.Join(lines, "\n"), nil
}