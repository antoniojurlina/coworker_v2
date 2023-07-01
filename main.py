from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

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
    message_history: List[Dict]

# Route for getting a SQL query and data back
@app.post("/process_query_and_data")
async def process_query_and_data(item: UserInput):
    # Process the user's input
    query, data = await coworker.process_query_and_data(message_history=item.message_history)

    # Return the results
    return {
        "query": query,
        "data": data,
    }

# Route for generating a summary of what had been done
@app.post("/generate_summary")
async def generate_summary(item: UserInput):
    # Generate summary
    summary = await coworker.generate_summary(message_history=item.message_history)

    # Return the results
    return {
        "summary": summary,
    }

# Route for getting some general market data from user input
@app.post("/get_info_from_text")
async def get_info_from_text(item: UserInput):
    # Process the user's input
    data = await coworker.get_info_from_text(message_history=item.message_history)

    # Return the results
    return {
        "data": data,
    }