from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path
from typing import BinaryIO

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from auto_job_hunting_agent.config import SETTINGS


def _build_embeddings() -> Embeddings:
    prov = SETTINGS.embedding_provider
    if prov == "google":
        gkey = (SETTINGS.google_api_key or os.getenv("GOOGLE_API_KEY") or "").strip()
        if not gkey:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=gkey,
        )
    if prov == "openai":
        okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        if not okey:
            raise RuntimeError(
                "OPENAI_API_KEY is not set but EMBEDDING_PROVIDER=openai. "
                "Switch to EMBEDDING_PROVIDER=google with a free GOOGLE_API_KEY, "
                "or add an OpenAI key."
            )
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=SETTINGS.openai_embedding_model,
            api_key=okey,
        )
    if prov == "local":
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError as e:
            raise RuntimeError(
                "Install local embeddings: pip install sentence-transformers"
            ) from e
        return HuggingFaceEmbeddings(model_name=SETTINGS.local_embedding_model)
    raise RuntimeError(
        f"Unknown EMBEDDING_PROVIDER={prov!r}. Use google, openai, or local (with GOOGLE_API_KEY)."
    )


def _read_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def _read_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()


def load_resume_bytes(data: bytes, filename: str) -> str:
    return _read_pdf(data) if filename.lower().endswith(".pdf") else _read_text(data)


def _section_hint(chunk: str) -> str:
    lower = chunk[:400].lower()
    if re.search(r"\b(experience|employment|work history)\b", lower):
        return "experience"
    if re.search(r"\b(education|university|degree|b\.?tech|m\.?tech|mba)\b", lower):
        return "education"
    if re.search(r"\b(skills|technical skills|tools|stack)\b", lower):
        return "skills"
    if re.search(r"\b(project|portfolio)\b", lower):
        return "projects"
    if re.search(r"\b(summary|profile|objective)\b", lower):
        return "summary"
    return "general"


class ResumeVectorStore:
    """In-memory FAISS index over resume chunks (Google or OpenAI embeddings)."""

    def __init__(self) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=120,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._embeddings: Embeddings | None = None
        self._store: FAISS | None = None
        self._raw_resume: str = ""

    def _get_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            self._embeddings = _build_embeddings()
        return self._embeddings

    @property
    def is_ready(self) -> bool:
        return self._store is not None and bool(self._raw_resume)

    def ingest_text(self, resume_text: str, source_label: str = "resume") -> None:
        self._raw_resume = resume_text
        chunks = self._splitter.split_text(resume_text)
        docs: list[Document] = []
        for i, chunk in enumerate(chunks):
            sid = hashlib.sha256(f"{source_label}:{i}:{chunk[:80]}".encode()).hexdigest()[:16]
            docs.append(Document(
                page_content=chunk,
                metadata={"chunk_id": sid, "section": _section_hint(chunk), "source": source_label},
            ))
        self._store = FAISS.from_documents(docs, self._get_embeddings())

    def ingest_file(self, path: Path) -> None:
        self.ingest_text(load_resume_bytes(path.read_bytes(), path.name), path.name)

    def ingest_upload(self, file_obj: BinaryIO, filename: str) -> None:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        self.ingest_text(load_resume_bytes(file_obj.read(), filename), filename)

    def similarity_search(self, query: str, k: int = 6) -> list[Document]:
        if not self._store:
            raise RuntimeError("Resume not ingested. Call ingest_* first.")
        return self._store.similarity_search(query, k=k)

    @property
    def raw_resume(self) -> str:
        return self._raw_resume
