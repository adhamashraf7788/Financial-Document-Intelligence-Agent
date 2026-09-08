from fastapi import FastAPI
from dotenv import load_dotenv
from langfuse import observe, get_client
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

langfuse = get_client()

app = FastAPI()

@observe()
def process_request(payload: str) -> str:
    return f"processed: {payload}"

@app.get("/ping")
def ping():
    result = process_request("hello")
    return {"status": "ok", "result": result}