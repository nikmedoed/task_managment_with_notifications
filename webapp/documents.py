from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from uuid import UUID
import os
import shutil
import uuid

app = FastAPI()

DOCUMENTS_DIR = "documents/"


def save_document(file_content, file_extension):
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.{file_extension}")

    with open(file_path, "wb") as f:
        f.write(file_content)

    return doc_id


def get_document(doc_id, file_extension):
    file_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.{file_extension}")
    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        return f.read()


def delete_document(doc_id, file_extension):
    file_path = os.path.join(DOCUMENTS_DIR, f"{doc_id}.{file_extension}")
    if os.path.exists(file_path):
        os.remove(file_path)


@app.post("/upload/")
async def upload_document(file: UploadFile):
    file_extension = file.filename.split(".")[-1]
    file_content = await file.read()

    doc_id = save_document(file_content, file_extension)

    # Сохранение метаданных в базе данных
    # Пример:
    # db.add(Document(id=doc_id, title=file.filename, type=file.content_type))
    # db.commit()

    return {"id": doc_id}


@app.get("/download/{doc_id}")
async def download_document(doc_id: UUID, file_extension: str):
    file_content = get_document(doc_id, file_extension)
    if file_content is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(file_content, filename=f"{doc_id}.{file_extension}")


@app.delete("/delete/{doc_id}")
async def delete_document(doc_id: UUID, file_extension: str):
    delete_document(doc_id, file_extension)
    # Удаление метаданных из базы данных
    # Пример:
    # db.delete(Document.id == doc_id)
    # db.commit()
    return {"detail": "Document deleted"}
