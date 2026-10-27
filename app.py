import json
import logging
import gc
import re
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
VECTOR_STORE_DIR = ROOT / "db" / "chroma_db"
MODEL_NAME = "qwen2.5:3b"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Classroom AI", version="1.0.0")


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    className: str = Field(min_length=1, max_length=40)


class AssistantResponse(BaseModel):
    reply: str


@lru_cache(maxsize=1)
def get_chat_model():
    from langchain_ollama import ChatOllama

    return ChatOllama(model=MODEL_NAME, temperature=0)


@lru_cache(maxsize=1)
def get_vector_store():
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    if not VECTOR_STORE_DIR.exists():
        raise RuntimeError(
            "The knowledge base was not found. Run ingestion_pipeline.py first."
        )

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )


def chat_reply(history, prompt):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [
        SystemMessage(
            content=(
                "You are a helpful educational assistant. Answer clearly and "
                "accurately. If you are unsure, say so."
            )
        )
    ]
    for message in history[-12:]:
        content = message["content"][:20_000]
        if message["role"] == "user":
            messages.append(HumanMessage(content=content))
        elif message["role"] == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=prompt))
    return str(get_chat_model().invoke(messages).content)


def generate_questions(class_name, prompt):
    from langchain_core.messages import HumanMessage, SystemMessage

    store = get_vector_store()
    if store._collection.count() == 0:
        raise RuntimeError(
            "The knowledge base is empty. Add learning materials to Docs and "
            "run ingestion_pipeline.py first."
        )

    documents = store.as_retriever(search_kwargs={"k": 5}).invoke(prompt)
    if not documents:
        raise RuntimeError("No relevant learning materials were found for that request.")

    context = "\n\n".join(document.page_content for document in documents)
    del store
    get_vector_store.cache_clear()
    gc.collect()

    count_match = re.search(
        r"\b(\d{1,2})\s+(?:[\w-]+\s+){0,2}questions?\b",
        prompt,
        re.IGNORECASE,
    )
    requested_count = int(count_match.group(1)) if count_match else None
    count_instruction = (
        f"Generate exactly {requested_count} questions."
        if requested_count is not None
        else "Generate the number of questions requested by the user."
    )
    messages = [
        SystemMessage(
            content=(
                "You are a CBT question generation assistant. Generate objective "
                "multiple-choice questions based only on the provided context.\n\n"
                "Return ONLY valid JSON in this format:\n"
                '{"questions":[{"question":"Question text","options":'
                '{"A":"Option A","B":"Option B","C":"Option C","D":"Option D"},'
                '"correct_answer":"A"}]}\n\n'
                "Rules:\n"
                f"- {count_instruction}\n"
                "- Each question must have exactly four options (A, B, C, D).\n"
                "- Each question must have exactly one correct answer.\n"
                "- The correct_answer must contain only A, B, C, or D.\n"
                "- Base all questions and answers strictly on the provided context.\n"
                "- Do not include explanations, markdown, or additional text.\n"
                "- Ensure the output is valid JSON."
            )
        ),
        HumanMessage(
            content=(
                f"Selected Nigerian class: {class_name}\n"
                f"Teacher's request: {prompt}\n\n"
                f"{count_instruction}\n\n"
                "Use only the retrieved learning-material excerpts below. The "
                "selected class is project context; the current knowledge base "
                "does not filter documents by class.\n\n"
                f"Learning-material excerpts:\n{context}"
            )
        ),
    ]
    answer = str(get_chat_model().invoke(messages).content)

    def is_valid_response(content):
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            return False

        questions = result.get("questions") if isinstance(result, dict) else None
        if not isinstance(questions, list) or not questions:
            return False
        if requested_count is not None and len(questions) != requested_count:
            return False
        return all(
            isinstance(question, dict)
            and isinstance(question.get("question"), str)
            and isinstance(question.get("options"), dict)
            and all(letter in question["options"] for letter in "ABCD")
            and isinstance(question.get("correct_answer"), str)
            and question["correct_answer"] in "ABCD"
            for question in questions
        )

    if not is_valid_response(answer):
        requested = f" exactly {requested_count}" if requested_count is not None else ""
        raise RuntimeError(
            f"The model did not return{requested} valid questions. Please try again."
        )
    return answer


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, error):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request. Check the message, history, and class fields."},
    )


@app.exception_handler(HTTPException)
async def handle_http_error(request, error):
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.detail},
        headers=error.headers,
    )


@app.exception_handler(Exception)
async def handle_server_error(request, error):
    logging.error(
        "Unhandled request error",
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        status_code=503,
        content={"error": "The request could not be completed. Check the server logs."},
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/chat", response_model=AssistantResponse)
def chat_endpoint(payload: ChatRequest):
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Enter a message to continue.")

    history = [message.model_dump() for message in payload.history]
    return {"reply": chat_reply(history, prompt)}


@app.post("/api/generate", response_model=AssistantResponse)
def generate_endpoint(payload: GenerateRequest):
    prompt = payload.prompt.strip()
    class_name = payload.className.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Enter a message to continue.")
    if not class_name:
        raise HTTPException(status_code=400, detail="Choose a class for this project.")

    return {"reply": generate_questions(class_name, prompt)}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
