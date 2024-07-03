from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from joserfc import jwt
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from webapp.deps import get_db, redis, COOKIE_NAME
from shared.app_config import app_config
from database.models import User

router = APIRouter()