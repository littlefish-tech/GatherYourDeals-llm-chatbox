package utils

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

// ---------------------------
// STRUCTS
// ---------------------------
type ChatRequest struct {
	Messages []struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"messages"`
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

	// ---------------------------
	// INIT RESPONSE
	// ---------------------------
	response := ChatResponse{}
	response.Message.Role = "assistant"

	// ---------------------------
	// COMPARISON MODE
	// ---------------------------
	if ActiveProvider() == "both" {
		comp, err := CallBothProviders(prompt)
		if err != nil {
			response.StopReason = "error"
			return response, err
		}

		response.Message.Content = BuildComparisonSummary(comp)
		response.StopReason = "end_turn"

		response.Usage = Usage{
			InputTokens:  0,
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
	maxReceiptItems := getMaxReceiptItems()
	receiptsBaseURL, err := url.Parse(getReceiptsAPIBaseURL())
	if err != nil {
		return "", err
	}
	receiptsURL := receiptsBaseURL.JoinPath("receipts")
	query := receiptsURL.Query()
	query.Set("limit", strconv.Itoa(maxReceiptItems))
	query.Set("offset", "0")
	receiptsURL.RawQuery = query.Encode()

	req, _ := http.NewRequest("GET", receiptsURL.String(), nil)
	req.Header.Set("Authorization", authHeader)

	resp, err := (&http.Client{}).Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var data map[string]interface{}
	err = json.Unmarshal(bodyBytes, &data)
	if err != nil {
		return "", err
	}

	itemsRaw, ok := data["data"]
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

	sort.SliceStable(items, func(i, j int) bool {
		return parsePurchaseDate(items[i]).After(parsePurchaseDate(items[j]))
	})

	lines := []string{}
	for _, item := range items {
		if len(lines) >= maxReceiptItems {
			break
		}

		m := item.(map[string]interface{})

		name := m["productName"]
		price := m["price"]
		storeName := m["storeName"]

		lines = append(lines, fmt.Sprintf("%v - %v - %v", name, price, storeName))
	}

	return strings.Join(lines, "\n"), nil
}

func getReceiptsAPIBaseURL() string {
	rawValue := strings.TrimSpace(os.Getenv("RECEIPTS_API_BASE_URL"))
	if rawValue == "" {
		return "https://gatheryourdeals-data-production.up.railway.app/api/v1"
	}

	return rawValue
}

func getMaxReceiptItems() int {
	rawValue := strings.TrimSpace(os.Getenv("MAX_RECEIPT_ITEMS"))
	if rawValue == "" {
		return 100
	}

	parsed, err := strconv.Atoi(rawValue)
	if err != nil || parsed <= 0 {
		return 100
	}

	return parsed
}

func parsePurchaseDate(item interface{}) time.Time {
	m, ok := item.(map[string]interface{})
	if !ok {
		return time.Time{}
	}

	rawDate, ok := m["purchaseDate"].(string)
	if !ok {
		return time.Time{}
	}

	rawDate = strings.TrimSpace(rawDate)
	if rawDate == "" {
		return time.Time{}
	}

	layouts := []string{
		time.RFC3339,
		"2006-01-02",
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
	}

	for _, layout := range layouts {
		parsed, err := time.Parse(layout, rawDate)
		if err == nil {
			return parsed
		}
	}

	return time.Time{}
}
