# LLM Chatbox (GatherYourDeals)

A simple chatbot that uses LLM providers (OpenRouter / CLOD) to answer questions based on user purchase data.

---

## How to Run the App

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

### Set environment variables

In the termial run:

```

export OPENROUTER_API_KEY=your_openrouter_key
export CLOD_API_KEY=your_clod_key
```

Select a provider:

OpenRouter:

```
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=...
export OPENROUTER_MODEL='model-id'
```

CLOD:

```
export LLM_PROVIDER=clod
export CLOD_API_KEY=...
export CLOD_MODEL='your-model-id'
```

The application uses MAX_RECEIPT_ITEMS in `utils/llm_service.go`. If the env var is missing, empty, non-numeric, or <= 0, it falls back to 100.

To set it in your terminal before running the service:

```
export MAX_RECEIPT_ITEMS=100
```

### Run the backend service

```
go run main.go
```

You should see:

```
Server running on http://localhost:8000
```

### Send a request (using curl)

In another termial, run:

## Single provider:

```
curl -X POST http://localhost:8000/chat \
 -H "Content-Type: application/json" \
 -H "Authorization: Bearer test_token" \
 -d '{
"messages": [
{"role": "user", "content": "What did I buy recently?"}
]
}'
```

## Compare both providers:

```
-d '{
  "messages": [
    {"role": "user", "content": "What did I buy recently?"}
  ],
  "provider": "both"
}'
```
