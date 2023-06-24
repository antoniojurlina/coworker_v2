from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4

from coworker.modules.coworker import Coworker

coworker = Coworker()

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for user input
class UserInput(BaseModel):
    user_input: str

# Conversations dictionary
conversations = {}

# Route for main page
@app.get("/")
async def read_main():
    # Generate a unique conversation ID
    conversation_id = str(uuid4())

    # Instantiate a new Coworker instance for the conversation
    conversations[conversation_id] = {
        "coworker": Coworker(),
        "messages": [],
        "data": []
    }

    return {"conversation_id": conversation_id}

# Route for processing user input and returning results
@app.post("/answer_request/{conversation_id}")
async def handle_request(conversation_id: str, item: UserInput):
    user_input = item.user_input
    # Check if the conversation ID is valid
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get the Coworker instance for the conversation
    coworker = conversations[conversation_id]["coworker"]

    # Process the user's input
    query, data, answer_summary = await coworker.answer_request(request=user_input)

    if data is not None:
        # Convert DataFrame to JSON if it's not None
        data = data.to_dict(orient="records")
        # data = data.to_json(orient="split")

    # Save the user's message and the assistant's response in the conversation history
    conversations[conversation_id]["messages"].extend([
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": answer_summary}
    ])
    
    # Return the results
    return {
        "query": query,
        "data": data,
        "answer_summary": answer_summary,
        "conversation_id": conversation_id,
        "body": conversations[conversation_id]["messages"]
    }