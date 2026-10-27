# Classroom AI

A local chat and question-generation interface for the RAG project.

## Run

From the repository root, start the web app with the project's virtual environment:

```powershell
.\rag_project\Scripts\python.exe app.py
```

Alternatively, run it directly with Uvicorn:

```powershell
.\rag_project\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the UI,
provides `/api/chat`, `/api/generate`, and `/api/health`, and exposes interactive
API documentation at `/docs`. The app uses the existing Ollama model `qwen2.5:3b`
and the `db/chroma_db` vector store created by
`ingestion_pipeline.py`. Ensure Ollama is running and the model is available. If
the vector store has not been created yet, add PDF learning materials to `Docs`
and run `ingestion_pipeline.py` before generating questions.

The sidebar supports separate chat and class-project histories. Project classes
cover Primary 1-6, JSS 1-3, and SS 1-3. History is saved in the browser's local
storage. The class selection is retained as project context; the current vector
store is shared and does not filter learning materials by class.
