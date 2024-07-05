from fastapi import APIRouter, Request, Depends
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from webapp.deps import get_db, redis, BASE_DIR, templates
from webapp.utils.RedisStore import COOKIE_AUTH
from shared.app_config import app_config

router = APIRouter()


@router.get("")
async def tasks(request: Request):
    template_context = {'request': request, 'app_config': app_config}
    return templates.TemplateResponse('tasks.html', template_context)
