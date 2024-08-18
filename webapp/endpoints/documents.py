import os
import shutil

from fastapi import APIRouter, Depends, Request, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from database.models import Document, Comment
from webapp.deps import templates
from database import get_db
from webapp.schemas import BulkDeleteRequest

router = APIRouter()


# todo  переименование и архивирование

def get_directory_size(directory: str) -> int:
    """Рекурсивно считает размер всех файлов в указанной директории."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

def get_disk_space_info(directory: str = "documents"):
    base_directory = os.path.abspath(directory)
    _, _, free = shutil.disk_usage(base_directory)

    used = get_directory_size(base_directory)
    total = free + used
    return {
        'total': total,
        'used': used,
        'free': free
    }


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
        .order_by(Document.time_created.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    documents = result.unique().scalars().all()

    count_query = select(func.count(Document.id))
    total = (await db.execute(count_query)).scalar()

    disk_space_info = get_disk_space_info()

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": documents,
        "page": page,
        "page_size": page_size,
        "total": total,
        "disk_space_info": disk_space_info
    })


async def delete_file_and_mark_deleted(document: Document, db: AsyncSession):
    file_path = f"documents/{document.uuid}"
    if os.path.exists(file_path):
        os.remove(file_path)
    document.deleted = True
    await db.commit()


@router.get("/delete/{uuid}", response_class=HTMLResponse)
async def delete_document(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).filter(Document.uuid == uuid))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден")

    await delete_file_and_mark_deleted(document, db)

    return HTMLResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bulk-delete", response_class=HTMLResponse)
async def bulk_delete_documents(request: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    uuids = request.uuids
    result = await db.execute(select(Document).filter(Document.uuid.in_(uuids)))
    documents = result.scalars().all()

    for document in documents:
        await delete_file_and_mark_deleted(document, db)

    return HTMLResponse(status_code=status.HTTP_204_NO_CONTENT)


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
