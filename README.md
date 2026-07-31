# Medical-RAG-Demo
Production RAG service: FastAPI + AWS Lambda + Terraform + pgvector + RAGAS

## AWS Endpoint

**API URL:** `https://2oc1tgm493.execute-api.us-east-1.amazonaws.com/query`

## Example Query

```bash
curl -X POST https://2oc1tgm493.execute-api.us-east-1.amazonaws.com/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the three classic symptoms of diabetes known as the \"three Ps\"?",
    "top_k": 4
  }'
```

**Example Response:**
```json
{
  "question": "What are the three classic symptoms of diabetes known as the \"three Ps\"?",
  "answer": "According to the context, the three classic symptoms of diabetes known as the \"three Ps\" are:\n\n1. **Polydipsia** (excessive thirst)\n2. **Polyuria** (excessive urination)\n3. **Polyphagia** (excessive hunger)\n\nThese are typically accompanied by weight loss and blurred vision.",
  "chunks": [
    {
      "text": "...",
      "source": "..."
    }
  ],
  "latency_ms": 123.45
}
```

## Parameters

- `question` (string): The medical question to answer
- `top_k` (integer): Number of relevant context chunks to retrieve

## Evaluation Results

| Metric            | Score | Notes                                              |
|-------------------|-------|----------------------------------------------------|
| Faithfulness      | 1.00  | RAGAS: answer is grounded in retrieved chunks      |
| Context precision | 0.87  | Avg fraction of retrieved chunks that are relevant |

