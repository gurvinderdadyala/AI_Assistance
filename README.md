IT AI Assistance Knowledge Bot

A single-repo sample IT support assistant built with React, FastAPI, LangChain, Chroma, and OpenAI. The assistant answers questions from local Markdown or PDF knowledge-base documents and returns the sources it used.

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
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

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
