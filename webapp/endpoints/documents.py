import os

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from database.models import Document, Comment
from webapp.deps import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def list_documents(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(30, ge=1),
        db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size

    query = (
        select(Document)
        .options(
            joinedload(Document.author),
            joinedload(Document.comment).joinedload(Comment.task)
        )
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    documents = result.scalars().all()

    count_query = select(func.count(Document.id))
    total = (await db.execute(count_query)).scalar()

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": documents,
        "page": page,
        "page_size": page_size,
        "total": total
    })


@router.get("/{uuid}", response_class=FileResponse)
async def get_document(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).filter(Document.uuid == uuid))
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")

    file_path = f"documents/{uuid}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(file_path, media_type=document.type, filename=document.title)
