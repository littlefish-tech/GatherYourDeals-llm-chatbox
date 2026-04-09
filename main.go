package main

import (
	"encoding/json"
	"fmt"
	"net/http"

	"compareprice/utils"
)

func chatHandler(w http.ResponseWriter, r *http.Request) {

	// METHOD CHECK
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(utils.ErrorResponse{
			Code:    "invalid_request",
			Message: "Only POST method is allowed",
		})
		return
	}

	var req utils.ChatRequest

	// ---------------------------
	// PARSE REQUEST
	// ---------------------------
	err := json.NewDecoder(r.Body).Decode(&req)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(utils.ErrorResponse{
			Code:    "invalid_request",
			Message: "Invalid request body",
		})
		return
	}

	authHeader := r.Header.Get("Authorization")

	// ---------------------------
	// CALL SERVICE
	// ---------------------------
	result, err := utils.HandleChat(req, authHeader)
	if err != nil {

		// AUTH ERROR
		if authHeader == "" {
			w.WriteHeader(http.StatusUnauthorized)
			json.NewEncoder(w).Encode(utils.ErrorResponse{
				Code:    "unauthorized",
				Message: "Missing or invalid Authorization header",
			})
			return
		}

		// GENERIC ERROR
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(utils.ErrorResponse{
			Code:    "internal_error",
			Message: "Unexpected error occurred",
		})
		return
	}

	// ---------------------------
	// SUCCESS RESPONSE
	// ---------------------------
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {

	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	json.NewEncoder(w).Encode(utils.HealthResponse{
		Status: "ok",
	})
}

func main() {
	http.HandleFunc("/chat", chatHandler)
	http.HandleFunc("/health", healthHandler)

	fmt.Println("Server running on http://0.0.0.0:8000")
	http.ListenAndServe(":8000", nil)
}