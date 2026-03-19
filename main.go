package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"compareprice/utils"
)

func main() {
	apiKey := strings.TrimSpace(os.Getenv("OPENROUTER_API_KEY"))
	if apiKey == "" {
		fmt.Println("OPENROUTER_API_KEY is not set.")
		fmt.Println("Export your key first, then run the app again.")
		os.Exit(1)
	}

	// Read user input from the terminal
	reader := bufio.NewReader(os.Stdin)

	for {
		fmt.Print("Enter prompt (or type 'exit'): ")
		prompt, err := reader.ReadString('\n')
		if err != nil {
			fmt.Fprintf(os.Stderr, "failed to read prompt: %v\n", err)
			os.Exit(1)
		}

		prompt = strings.TrimSpace(prompt)
		if prompt == "" {
			fmt.Println("Prompt cannot be empty.")
			continue
		}

		if strings.EqualFold(prompt, "exit") {
			fmt.Println("Goodbye.")
			return
		}

		result, err := utils.CallOpenRouter(prompt)
		if err != nil {
			fmt.Fprintf(os.Stderr, "OpenRouter request failed: %v\n", err)
			continue
		}

		if err := utils.LogLLM(result); err != nil {
			fmt.Fprintf(os.Stderr, "warning: failed to write log: %v\n", err)
		}

		fmt.Println()
		fmt.Println("Response:")
		fmt.Println(result.Response)
		fmt.Println()
	}
}
