from __future__ import annotations

from typing import Any

from langchain_core.documents import Document


def news_to_documents(items: list[dict[str, Any]]) -> list[Document]:
    docs = []
    for item in items:
        docs.append(
            Document(
                page_content=f"{item.get('title') or ''}\n{item.get('summary') or ''}".strip(),
                metadata={
                    "ticker": item.get("ticker"),
                    "date": item.get("published_at"),
                    "source": item.get("publisher"),
                    "url": item.get("url"),
                    "rule_label": item.get("rule_label"),
                },
            )
        )
    return docs
