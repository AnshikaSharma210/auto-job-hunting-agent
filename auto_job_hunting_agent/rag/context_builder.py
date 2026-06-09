from __future__ import annotations

from collections import defaultdict

from langchain_core.documents import Document


def build_structured_resume_context(docs: list[Document]) -> str:
    """Group retrieved chunks by section hint for clearer LLM context."""
    buckets: dict[str, list[str]] = defaultdict(list)
    order: list[str] = []
    for d in docs:
        section = (d.metadata or {}).get("section") or "general"
        if section not in buckets:
            order.append(section)
        buckets[section].append(d.page_content.strip())

    blocks: list[str] = []
    for section in order:
        joined = "\n---\n".join(buckets[section])
        blocks.append(f"### Resume — {section.upper()}\n{joined}")
    return "\n\n".join(blocks).strip()
