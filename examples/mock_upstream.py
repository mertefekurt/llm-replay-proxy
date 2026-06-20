from fastapi import FastAPI
from uvicorn import run

app = FastAPI()


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict[str, object]) -> dict[str, object]:
    model = payload.get("model", "demo-model")
    return {
        "id": "chatcmpl-local-demo",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The recorded answer came from the local mock upstream.",
                },
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    run(app, host="127.0.0.1", port=9001)
