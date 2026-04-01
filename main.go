package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"compareprice/utils"
)

func main() {
	provider := utils.ActiveProvider()
	apiKeyEnvs := []string{"OPENROUTER_API_KEY"}
	if provider == "clod" {
		apiKeyEnvs = []string{"CLOD_API_KEY"}
	}
	if provider == "both" {
		apiKeyEnvs = []string{"OPENROUTER_API_KEY", "CLOD_API_KEY"}
	}

	// The selected provider API key is required before we can make a request.
	for _, apiKeyEnv := range apiKeyEnvs {
		apiKey := strings.TrimSpace(os.Getenv(apiKeyEnv))
		if apiKey == "" {
			fmt.Printf("%s is not set.\n", apiKeyEnv)
			fmt.Println("Export your key first, then run the app again.")
			os.Exit(1)
		}
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

		if provider == "both" {
			comparison, err := utils.CallBothProviders(prompt)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Both-provider comparison failed: %v\n", err)
				continue
			}

			for _, result := range []*utils.LLMLogEntry{comparison.CLOD, comparison.OpenRouter} {
				if err := utils.LogLLM(result); err != nil {
					fmt.Fprintf(os.Stderr, "warning: failed to write log: %v\n", err)
				}
			}

			fmt.Println()
			fmt.Println("CLOD Response:")
			fmt.Println(comparison.CLOD.Response)
			fmt.Println()
			fmt.Println("OpenRouter Response:")
			fmt.Println(comparison.OpenRouter.Response)
			fmt.Println()
			fmt.Println("Comparison:")
			fmt.Println(utils.BuildComparisonSummary(comparison))
			fmt.Println()
			continue
		}

		// Send the user's prompt to the configured provider and model.
		result, err := utils.CallLLM(prompt)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s request failed: %v\n", strings.Title(provider), err)
			continue
		}

		// Save each successful interaction for later usage and reporting analysis.
		if err := utils.LogLLM(result); err != nil {
			fmt.Fprintf(os.Stderr, "warning: failed to write log: %v\n", err)
		}

		fmt.Println()
		fmt.Println("Response:")
		fmt.Println(result.Response)
		fmt.Println()
	}
}
