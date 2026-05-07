IT AI Assistance Knowledge Bot

A single-repo sample IT support assistant built with React, FastAPI, LangChain, Chroma, and OpenAI-compatible models. The assistant answers questions from local Markdown or PDF knowledge-base documents and returns the sources it used.

## Project Structure

```text
backend/
  app/
    main.py
    models.py
    rag_service.py
    settings.py
  data/it_knowledge/
  requirements.txt
  .env.example
frontend/
  src/
  package.json
```

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Model Provider Options

Choose the provider in `backend/.env` with `LLM_PROVIDER`.

OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

LM Studio:

```env
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=lm-studio
LMSTUDIO_MODEL=your-loaded-chat-model
LMSTUDIO_EMBEDDING_MODEL=your-loaded-embedding-model
```

Start LM Studio's local server and load a chat model. For document search, also load or expose an embedding model through the OpenAI-compatible embeddings endpoint.

Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

Install and pull the models first:

```powershell
ollama pull llama3.1
ollama pull nomic-embed-text
```

After changing providers or embedding models, restart the backend and rebuild the index with `POST /api/reindex`.

Start the API:

```powershell
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

## Frontend Setup

```powershell
npm install
npm run frontend:dev
```

If you prefer working inside the frontend folder:

```powershell
cd frontend
npm install
npm run dev
```

The React app runs at `http://localhost:5173`.

If npm reports a certificate verification error on this machine, run this once in the terminal before `npm install`:

```powershell
$env:NODE_OPTIONS='--use-system-ca'
```

## API

- `GET /api/health` returns service status.
- `POST /api/chat` answers an IT question using the knowledge base.
- `POST /api/reindex` rebuilds the Chroma index from local documents.

## Knowledge Base Documents

Add `.md` or `.pdf` files to `backend/data/it_knowledge/`.

After adding, editing, or deleting files, rebuild the index:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/reindex
```

PDF support works best with text-based PDFs. Scanned image-only PDFs need OCR before they can be searched.

Example chat request:

```json
{
  "message": "How do I reset my password?",
  "history": []
}
```

## Sample Questions

- How do I reset my password?
- How do I connect to VPN?
- Why am I not receiving MFA prompts?
- How do I set up my new laptop?
- How do I fix a printer that will not print?
