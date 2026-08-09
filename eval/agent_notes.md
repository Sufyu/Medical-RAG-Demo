# Agent Log: Conversation Memory
 
**Tool:** Devin + SWE-1.6 Slow
**Feature:** Conversation memory
**Date:** 8/8/2026
 
## Round 1 -- Initial generation
 
### Prompt (verbatim)
> I have a FastAPI app deployed on AWS Lambda (stateless between invocations). I want 
> to add a POST /conversation endpoint that supports multi-turn chat: it takes 
> {conversation_id, question}, retrieves the last 5 turns of history for that 
> conversation_id from DynamoDB, injects them into the prompt sent to Claude, gets an 
> answer, appends the new Q+A to DynamoDB, and returns {conversation_id, answer, 
> history}. Use boto3. Assume the table is called conversation-history with partition 
> key conversation_id (string) and sort key timestamp (number). Handle the case where 
> conversation_id doesn't exist yet (start fresh). Show me the endpoint code and the 
> Terraform for the DynamoDB table.

### What the agent produced
diff --git a/backend/app/main.py b/backend/app/main.py
index b5f92bd..303d48b 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -1,13 +1,23 @@
 # Main FastAPI application entry point - will be populated with API endpoints
 from fastapi import FastAPI
-from app.models import QueryRequest, QueryResponse
+from app.models import QueryRequest, QueryResponse, ConversationRequest, ConversationResponse, ConversationTurn
 # from app.retrieval import retrieve
 from app.retrieval_lambda import retrieve
 from app.retrieval_lambda import answer
 from mangum import Mangum
+import boto3
+import anthropic
+import time
+import os
+from typing import List
 
 app = FastAPI()
 
+# Initialize AWS clients
+dynamodb = boto3.resource('dynamodb')
+conversation_table = dynamodb.Table('conversation-history')
+_llm = anthropic.Anthropic()
+
 #@app.get("/")
 #def read_root():
 #    return {"message": "Hello world"}
@@ -26,5 +36,85 @@ async def handle_query(request: QueryRequest):
 def health() -> dict:
     return {"status": "ok"}
 
+
+@app.post("/conversation", response_model=ConversationResponse)
+async def handle_conversation(request: ConversationRequest):
+    """
+    Multi-turn conversation endpoint with DynamoDB persistence.
+    
+    Retrieves last 5 turns of conversation history, injects into prompt,
+    generates answer using Claude, stores new turn, and returns updated history.
+    """
+    # Retrieve last 5 turns from DynamoDB
+    try:
+        response = conversation_table.query(
+            KeyConditionExpression='conversation_id = :cid',
+            ExpressionAttributeValues={':cid': request.conversation_id},
+            ScanIndexForward=False,  # Descending by timestamp (newest first)
+            Limit=5
+        )
+        history_items = response.get('Items', [])
+    except Exception as e:
+        # Table might not exist or other error - start fresh
+        history_items = []
+    
+    # Convert to list of ConversationTurn (reverse to get chronological order)
+    history: List[ConversationTurn] = [
+        ConversationTurn(question=item['question'], answer=item['answer'])
+        for item in reversed(history_items)
+    ]
+    
+    # Build conversation history string for prompt
+    history_str = ""
+    if history:
+        history_str = "\n\n".join(
+            f"Q: {turn.question}\nA: {turn.answer}" for turn in history
+        )
+        history_str = f"\n\nPrevious conversation:\n{history_str}\n\n"
+    
+    # Retrieve relevant chunks for context
+    chunks = retrieve(request.question, top_k=4)
+    context = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
+    
+    # Build prompt with history and context
+    prompt = f"""Answer the question using only the context below. If the context is insufficient, say so.{history_str}
+Context:
+{context}
+
+Question: {request.question}"""
+    
+    # Generate answer with Claude
+    resp = _llm.messages.create(
+        model="claude-haiku-4-5-20251001",
+        max_tokens=500,
+        messages=[{"role": "user", "content": prompt}]
+    )
+    answer_text = resp.content[0].text
+    
+    # Store new turn in DynamoDB
+    timestamp = int(time.time() * 1000)
+    try:
+        conversation_table.put_item(
+            Item={
+                'conversation_id': request.conversation_id,
+                'timestamp': timestamp,
+                'question': request.question,
+                'answer': answer_text
+            }
+        )
+    except Exception as e:
+        # Log error but don't fail the request
+        print(f"Failed to store conversation: {e}")
+    
+    # Return response with updated history
+    updated_history = history + [ConversationTurn(question=request.question, answer=answer_text)]
+    
+    return ConversationResponse(
+        conversation_id=request.conversation_id,
+        answer=answer_text,
+        history=updated_history
+    )
+
+
 # Lambda handler
 handler = Mangum(app, lifespan="off")
\ No newline at end of file
diff --git a/backend/app/models.py b/backend/app/models.py
index 4597946..d0b2504 100644
--- a/backend/app/models.py
+++ b/backend/app/models.py
@@ -1,5 +1,5 @@
 from pydantic import BaseModel, Field
-from typing import List
+from typing import List, Optional
 
 
 class QueryRequest(BaseModel):
@@ -14,6 +14,38 @@ class QueryRequest(BaseModel):
     top_k: int = Field(default=4, ge=1, le=10)
 
 
+class ConversationTurn(BaseModel):
+    """A single conversation turn with question and answer."""
+    question: str
+    answer: str
+
+
+class ConversationRequest(BaseModel):
+    """
+    Request model for multi-turn conversation.
+    
+    Attributes:
+        conversation_id: Unique identifier for the conversation
+        question: The user's question for this turn
+    """
+    conversation_id: str = Field(min_length=1, max_length=100)
+    question: str = Field(min_length=3, max_length=500)
+
+
+class ConversationResponse(BaseModel):
+    """
+    Response model for conversation endpoint.
+    
+    Attributes:
+        conversation_id: The conversation identifier
+        answer: The LLM-generated answer
+        history: List of all conversation turns
+    """
+    conversation_id: str
+    answer: str
+    history: List[ConversationTurn]
+
+
 class RetrievedChunk(BaseModel):
     """
     Represents a single retrieved document chunk from the knowledge base.
diff --git a/infra/main.tf b/infra/main.tf
index d4f4575..4bb8cca 100644
--- a/infra/main.tf
+++ b/infra/main.tf
@@ -84,6 +84,54 @@ resource "aws_iam_role_policy_attachment" "basic" {
   policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
 }
 
+resource "aws_iam_role_policy" "dynamodb_conversation" {
+  name = "dynamodb-conversation-access"
+  role = aws_iam_role.lambda.id
+
+  policy = jsonencode({
+    Version = "2012-10-17"
+    Statement = [
+      {
+        Effect = "Allow"
+        Action = [
+          "dynamodb:Query",
+          "dynamodb:PutItem",
+          "dynamodb:GetItem",
+          "dynamodb:Scan"
+        ]
+        Resource = aws_dynamodb_table.conversation_history.arn
+      }
+    ]
+  })
+}
+
+# DynamoDB table for conversation history
+resource "aws_dynamodb_table" "conversation_history" {
+  name           = "conversation-history"
+  billing_mode   = "PAY_PER_REQUEST"
+  hash_key       = "conversation_id"
+  range_key      = "timestamp"
+
+  attribute {
+    name = "conversation_id"
+    type = "S"
+  }
+
+  attribute {
+    name = "timestamp"
+    type = "N"
+  }
+
+  ttl {
+    attribute_name = "expires_at"
+    enabled        = false
+  }
+
+  tags = {
+    project = var.project
+  }
+}
+
 
 resource "aws_lambda_function" "app" {
   function_name = var.project
@@ -98,7 +146,9 @@ resource "aws_lambda_function" "app" {
 
   depends_on = [
     aws_ecr_repository_policy.lambda_pull,
-    aws_iam_role_policy_attachment.basic
+    aws_iam_role_policy_attachment.basic,
+    aws_iam_role_policy.dynamodb_conversation,
+    aws_dynamodb_table.conversation_history
   ]
 }

 ### What I flagged on review
1. No TTL/expiry set on DynamoDB conversation items — history would 
   accumulate indefinitely with no automatic cleanup.
2. No handling for a `conversation_id` that doesn't exist yet

### Manual fixes
diff --git a/backend/app/main.py b/backend/app/main.py
index 303d48b..f09b35e 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -9,6 +9,7 @@ import boto3
 import anthropic
 import time
 import os
+import uuid
 from typing import List
 
 app = FastAPI()
@@ -46,16 +47,19 @@ async def handle_conversation(request: ConversationRequest):
     generates answer using Claude, stores new turn, and returns updated history.
     """
     # Retrieve last 5 turns from DynamoDB
-    try:
-        response = conversation_table.query(
-            KeyConditionExpression='conversation_id = :cid',
-            ExpressionAttributeValues={':cid': request.conversation_id},
-            ScanIndexForward=False,  # Descending by timestamp (newest first)
-            Limit=5
-        )
-        history_items = response.get('Items', [])
-    except Exception as e:
-        # Table might not exist or other error - start fresh
+    if request.conversation_id:
+        try:
+            response = conversation_table.query(
+                KeyConditionExpression='conversation_id = :cid',
+                ExpressionAttributeValues={':cid': request.conversation_id},
+                ScanIndexForward=False,  # Descending by timestamp (newest first)
+                Limit=5
+            )
+            history_items = response.get('Items', [])
+        except Exception as e:
+            # Table might not exist or other error - start fresh
+            history_items = []
+    else:
         history_items = []
 
     # Convert to list of ConversationTurn (reverse to get chronological order)
@@ -93,13 +97,20 @@ Question: {request.question}"""
 
     # Store new turn in DynamoDB
     timestamp = int(time.time() * 1000)
+    expires_at = timestamp + (2 * 24 * 60 * 60 * 1000)  # 2 days
+    if(request.conversation_id):
+        put_conversation_id = request.conversation_id
+    else:
+        put_conversation_id = str(uuid.uuid4())
+
     try:
         conversation_table.put_item(
             Item={
-                'conversation_id': request.conversation_id,
+                'conversation_id': put_conversation_id,
                 'timestamp': timestamp,
                 'question': request.question,
-                'answer': answer_text
+                'answer': answer_text,
+                'expires_at': expires_at
             }
         )
     except Exception as e:
@@ -110,7 +121,7 @@ Question: {request.question}"""
     updated_history = history + [ConversationTurn(question=request.question, answer=answer_text)]
 
     return ConversationResponse(
-        conversation_id=request.conversation_id,
+        conversation_id=put_conversation_id,
         answer=answer_text,
         history=updated_history
     )
diff --git a/backend/app/models.py b/backend/app/models.py
index d0b2504..1ed356b 100644
--- a/backend/app/models.py
+++ b/backend/app/models.py
@@ -28,7 +28,7 @@ class ConversationRequest(BaseModel):
         conversation_id: Unique identifier for the conversation
         question: The user's question for this turn
     """
-    conversation_id: str = Field(min_length=1, max_length=100)
+    conversation_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
     question: str = Field(min_length=3, max_length=500)
 
 
diff --git a/infra/main.tf b/infra/main.tf
index 4bb8cca..5f949bf 100644
--- a/infra/main.tf
+++ b/infra/main.tf
@@ -124,7 +124,7 @@ resource "aws_dynamodb_table" "conversation_history" {
 
   ttl {
     attribute_name = "expires_at"
-    enabled        = false
+    enabled        = true
   }
 
 ## Round 2 -- Test gap caught by AI review

 ### What was flagged for review
 The expires_at timestamp assumed a milliseconds-based epoch, but DynamoDB TTL expects seconds.

 ### Manual Fixes
 diff --git a/backend/app/main.py b/backend/app/main.py
index f09b35e..11bd391 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -97,7 +97,7 @@ Question: {request.question}"""

     # Store new turn in DynamoDB
     timestamp = int(time.time() * 1000)
-    expires_at = timestamp + (2 * 24 * 60 * 60 * 1000)  # 2 days
+    expires_at = timestamp + (2 * 24 * 60 * 60)  # 2 days
     if(request.conversation_id):
         put_conversation_id = request.conversation_id
     else: