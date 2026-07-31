import json, requests, datetime, os
from ragas import evaluate
from ragas.metrics import Faithfulness, ContextPrecision
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import embedding_factory
from langchain_anthropic import ChatAnthropic
from datasets import Dataset

BASE = "https://2oc1tgm493.execute-api.us-east-1.amazonaws.com/query"

# Configure Anthropic for RAGAS evaluation
anthropic_client = ChatAnthropic(model="claude-haiku-4-5-20251001", api_key=os.environ.get("ANTHROPIC_API_KEY"))
llm = LangchainLLMWrapper(anthropic_client)

# Configure HuggingFace embeddings using factory
embeddings = embedding_factory("huggingface", model="sentence-transformers/all-MiniLM-L6-v2")

rows = []
with open("questions.jsonl") as f:
    for line in f:
        q = json.loads(line)
        r = requests.post(BASE, json={"question": q["question"], "top_k": 4})
        rows.append({
            "question": q["question"],
            "answer": r.json()["answer"],
            "contexts": [c["text"] for c in r.json()["chunks"]],
            "ground_truth": q["ground_truth"]
        })

ds = Dataset.from_list(rows)

result = evaluate(ds, metrics=[Faithfulness(), ContextPrecision()], llm=llm, embeddings=embeddings)
stamp = datetime.date.today().isoformat()
with open(f"results-{stamp}.json", "w") as f:
    json.dump(result.to_pandas().to_dict(orient="records"), f, indent=2, default=str)

