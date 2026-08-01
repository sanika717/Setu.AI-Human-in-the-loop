from typing import Any, Dict, List
from ..db.models import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def retrieve_documents(session: AsyncSession, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    stmt = select(Document).order_by(Document.created_at.desc()).limit(top_k)
    results = await session.execute(stmt)
    docs = results.scalars().all()
    return [
        {
            "document_id": doc.id,
            "title": doc.title,
            "source": doc.source,
            "score": 1.0,
            "snippet": "Encrypted content withheld for security",
        }
        for doc in docs
    ]
