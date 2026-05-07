from pathlib import Path
import shutil

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.models import ChatHistoryItem, Source
from app.settings import Settings


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
        self._llm: ChatOpenAI | None = None
        self._embeddings: OpenAIEmbeddings | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.openai_api_key.strip())

    @property
    def indexed(self) -> bool:
        return self._vector_store is not None

    def initialize(self) -> None:
        self._ensure_configured()
        if self.settings.chroma_path.exists():
            shutil.rmtree(self.settings.chroma_path)
        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
        self._embeddings = OpenAIEmbeddings(
            model=self.settings.openai_embedding_model,
            api_key=self.settings.openai_api_key,
        )
        self._llm = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            temperature=0.2,
        )
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
        return len(self._load_documents())

    async def answer(self, question: str, history: list[ChatHistoryItem]) -> tuple[str, list[Source]]:
        self._ensure_ready()
        assert self._vector_store is not None
        assert self._llm is not None

        docs_with_scores = await self._vector_store.asimilarity_search_with_relevance_scores(question, k=4)
        docs = [doc for doc, score in docs_with_scores if score >= 0.25]
        sources = self._sources_from_documents(docs)

        if not docs:
            return (
                "I could not find that in the IT knowledge base. Please contact the IT helpdesk for more help.",
                [],
            )

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
        return response.content, sources

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Copy backend/.env.example to backend/.env and set OPENAI_API_KEY."
            )

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
