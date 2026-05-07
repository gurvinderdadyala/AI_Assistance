from pathlib import Path
import hashlib
import logging
import shutil

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.answer_cache import AnswerCache
from app.models import ChatHistoryItem, Source
from app.settings import Settings

logger = logging.getLogger(__name__)


ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an IT helpdesk knowledge assistant. Answer only from the provided context. "
            "If the answer is not in the context, say that the IT knowledge base does not contain "
            "that information and suggest contacting the IT helpdesk. Keep answers concise and practical.\n\n"
            "Context:\n{context}",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)


class ITKnowledgeBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._vector_store: Chroma | None = None
        self._llm: BaseChatModel | None = None
        self._embeddings: Embeddings | None = None
        self._cache = AnswerCache(
            db_path=self.settings.answer_cache_db_path,
            ttl_seconds=self.settings.answer_cache_ttl_seconds,
        )

    @property
    def configured(self) -> bool:
        provider = self.settings.normalized_llm_provider
        if provider == "openai":
            return bool(self.settings.openai_api_key.strip())
        return provider in {"lmstudio", "ollama"}

    @property
    def indexed(self) -> bool:
        return self._vector_store is not None

    def initialize(self) -> None:
        self._ensure_configured()
        if self.settings.chroma_path.exists():
            shutil.rmtree(self.settings.chroma_path)
        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._embeddings = self._create_embeddings()
        self._llm = self._create_llm()
        documents = self._load_documents()
        chunks = self._split_documents(documents)
        self._vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self._embeddings,
            persist_directory=str(self.settings.chroma_path),
            collection_name="it_knowledge",
        )

    def rebuild_index(self) -> int:
        self.initialize()
        self._cache.clear()
        return len(self._load_documents())

    async def answer(self, question: str, history: list[ChatHistoryItem]) -> tuple[str, list[Source], bool]:
        cache_key = self._cache_key(question)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Answer cache hit for key %s", cache_key[:12])
            answer, sources = cached
            return answer, sources, True
        logger.info("Answer cache miss for key %s", cache_key[:12])

        self._ensure_ready()
        assert self._vector_store is not None
        assert self._llm is not None

        docs_with_scores = await self._vector_store.asimilarity_search_with_relevance_scores(question, k=4)
        docs = [doc for doc, score in docs_with_scores if score >= 0.25]
        sources = self._sources_from_documents(docs)

        if not docs:
            answer = "I could not find that in the IT knowledge base. Please contact the IT helpdesk for more help."
            self._cache.set(cache_key, question, answer, [])
            return answer, [], False

        context = "\n\n".join(
            f"Source: {doc.metadata.get('title', 'Unknown')}\n{doc.page_content}" for doc in docs
        )
        messages = self._history_to_messages(history)
        chain = ANSWER_PROMPT | self._llm
        response = await chain.ainvoke(
            {
                "context": context,
                "history": messages,
                "question": question,
            }
        )
        answer = str(response.content)
        self._cache.set(cache_key, question, answer, sources)
        return answer, sources, False

    def _ensure_configured(self) -> None:
        if not self.configured:
            if self.settings.normalized_llm_provider == "openai":
                raise RuntimeError(
                    "OPENAI_API_KEY is not configured. Copy backend/.env.example to backend/.env and set OPENAI_API_KEY."
                )
            raise RuntimeError(
                "LLM_PROVIDER must be one of: openai, lmstudio, ollama."
            )

    def _create_llm(self) -> BaseChatModel:
        provider = self.settings.normalized_llm_provider
        if provider == "openai":
            return ChatOpenAI(
                model=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                temperature=0.2,
            )
        if provider == "lmstudio":
            return ChatOpenAI(
                model=self.settings.lmstudio_model,
                api_key=self.settings.lmstudio_api_key,
                base_url=self.settings.resolved_lmstudio_chat_base_url,
                temperature=0.2,
            )
        if provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
            except ImportError as exc:
                raise RuntimeError(
                    "Ollama support requires langchain-ollama. Run pip install -r requirements.txt."
                ) from exc
            return ChatOllama(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                temperature=0.2,
            )
        raise RuntimeError("LLM_PROVIDER must be one of: openai, lmstudio, ollama.")

    def _create_embeddings(self) -> Embeddings:
        provider = self.settings.normalized_llm_provider
        if provider == "openai":
            return OpenAIEmbeddings(
                model=self.settings.openai_embedding_model,
                api_key=self.settings.openai_api_key,
            )
        if provider == "lmstudio":
            return OpenAIEmbeddings(
                model=self.settings.lmstudio_embedding_model,
                api_key=self.settings.lmstudio_api_key,
                base_url=self.settings.resolved_lmstudio_embedding_base_url,
                check_embedding_ctx_length=False,
            )
        if provider == "ollama":
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError as exc:
                raise RuntimeError(
                    "Ollama support requires langchain-ollama. Run pip install -r requirements.txt."
                ) from exc
            return OllamaEmbeddings(
                model=self.settings.ollama_embedding_model,
                base_url=self.settings.ollama_base_url,
            )
        raise RuntimeError("LLM_PROVIDER must be one of: openai, lmstudio, ollama.")

    def _ensure_ready(self) -> None:
        if self._vector_store is None or self._llm is None:
            self.initialize()

    def _load_documents(self) -> list[Document]:
        knowledge_path = self.settings.knowledge_path
        if not knowledge_path.exists():
            raise RuntimeError(f"Knowledge directory does not exist: {knowledge_path}")

        documents: list[Document] = []
        for path in sorted(knowledge_path.glob("*")):
            if path.suffix.lower() == ".md":
                documents.extend(self._load_markdown(path))
            elif path.suffix.lower() == ".pdf":
                documents.extend(self._load_pdf(path))
        if not documents:
            raise RuntimeError(f"No markdown or PDF documents found in {knowledge_path}")
        return documents

    def _load_markdown(self, path: Path) -> list[Document]:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        return [
            Document(
                page_content=content,
                metadata=self._metadata_for_path(path),
            )
        ]

    def _load_pdf(self, path: Path) -> list[Document]:
        reader = PdfReader(str(path))
        documents: list[Document] = []
        for page_index, page in enumerate(reader.pages, start=1):
            content = (page.extract_text() or "").strip()
            if not content:
                continue
            metadata = self._metadata_for_path(path)
            metadata["page"] = page_index
            documents.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )
        return documents

    @staticmethod
    def _split_documents(documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
        return splitter.split_documents(documents)

    @staticmethod
    def _history_to_messages(history: list[ChatHistoryItem]) -> list[HumanMessage | AIMessage]:
        messages: list[HumanMessage | AIMessage] = []
        for item in history[-8:]:
            if item.role == "user":
                messages.append(HumanMessage(content=item.content))
            else:
                messages.append(AIMessage(content=item.content))
        return messages

    @staticmethod
    def _title_from_path(path: Path) -> str:
        return path.stem.replace("-", " ").replace("_", " ").title()

    def _metadata_for_path(self, path: Path) -> dict[str, str]:
        return {
            "title": self._title_from_path(path),
            "path": str(path.relative_to(self.settings.backend_root)),
            "type": path.suffix.lower().lstrip("."),
        }

    def _cache_key(self, question: str) -> str:
        normalized_question = " ".join(question.strip().lower().split())
        raw_key = "|".join(
            [
                normalized_question,
                self.settings.normalized_llm_provider,
                self._active_chat_model_name(),
                self._active_embedding_model_name(),
                self._knowledge_fingerprint(),
            ]
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _active_chat_model_name(self) -> str:
        provider = self.settings.normalized_llm_provider
        if provider == "openai":
            return self.settings.openai_model
        if provider == "lmstudio":
            return self.settings.lmstudio_model
        if provider == "ollama":
            return self.settings.ollama_model
        return provider

    def _active_embedding_model_name(self) -> str:
        provider = self.settings.normalized_llm_provider
        if provider == "openai":
            return self.settings.openai_embedding_model
        if provider == "lmstudio":
            return self.settings.lmstudio_embedding_model
        if provider == "ollama":
            return self.settings.ollama_embedding_model
        return provider

    def _knowledge_fingerprint(self) -> str:
        hasher = hashlib.sha256()
        for path in sorted(self.settings.knowledge_path.glob("*")):
            if path.suffix.lower() not in {".md", ".pdf"}:
                continue
            stat = path.stat()
            hasher.update(str(path.relative_to(self.settings.backend_root)).encode("utf-8"))
            hasher.update(str(stat.st_size).encode("utf-8"))
            hasher.update(str(stat.st_mtime_ns).encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def _sources_from_documents(documents: list[Document]) -> list[Source]:
        seen: set[str] = set()
        sources: list[Source] = []
        for doc in documents:
            path = str(doc.metadata.get("path", ""))
            if not path or path in seen:
                continue
            seen.add(path)
            sources.append(
                Source(
                    title=str(doc.metadata.get("title", "Unknown source")),
                    path=path,
                )
            )
        return sources
