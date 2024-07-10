from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from webapp.deps import get_db, templates
from shared.app_config import app_config
from webapp.schemas import *
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from database.models import User
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

router = APIRouter()

FIELDS = {
    'objects': {
        'name': "Объекты",
        'name1': "Объект",
        'model': Object,
        'pydantic_model': ObjectCreate,
        'fields': [
            {'name': 'name', 'label': 'Название'},
            {'name': 'organization_id', 'label': 'Организация'},
            {'name': 'description', 'label': 'Описание'},
            {'name': 'address', 'label': 'Адрес'},
            {'name': 'area_sq_meters', 'label': 'Площадь (кв.м)'},
            {'name': 'num_apartments', 'label': 'Кол-во квартир'}
        ],
    },
    'organizations': {
        'name': "Организации",
        'name1': "Организацию",
        'model': Organization,
        'pydantic_model': OrganizationCreate,
        'fields': [
            {'name': 'name', 'label': 'Название'},
            {'name': 'description', 'label': 'Описание'},
            {'name': 'address', 'label': 'Адрес'},
        ],
    },
    'task_types': {
        'name': "Типы задач",
        'name1': "Тип задач",
        'model': TaskType,
        'pydantic_model': TaskTypeCreate,
        'fields': [
            {'name': 'name', 'label': 'Название'},
            {'name': 'active', 'label': 'Активен'},
        ],
    },
}


def generate_static():
    static = [("references_tabs.html", {'fields': FIELDS}, "references_tabs.html")]

    for key, value in FIELDS.items():
        static.append(("references_thead.html", {'table_fields': value['fields']}, f"references_thead_{key}.html"))

    return static


def get_admin_user(request: Request):
    user = request.state.user
    if not user.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return user


@router.get("")
async def references(request: Request, db: AsyncSession = Depends(get_db)):
    objects = (await db.execute(select(Object))).scalars().all()
    organizations = (await db.execute(select(Organization))).scalars().all()
    task_types = (await db.execute(select(TaskType))).scalars().all()

    data = {
        'objects': objects,
        'organizations': organizations,
        'task_types': task_types,
    }

    context = {
        'request': request,
        'app_config': app_config,
        'data': data,
        'fields': FIELDS
    }
    return templates.TemplateResponse("references.html", context)


async def save_resource(db: AsyncSession, model_class, data, resource_id=None):
    if resource_id:
        db_obj = await db.get(model_class, resource_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail=f"Запись id:{resource_id} не найдена")
        for key, value in data.dict().items():
            setattr(db_obj, key, value)
    else:
        db_obj = model_class(**data.dict())
        db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


@router.post("/{model}/", response_class=HTMLResponse)
@router.post("/{model}/{item_id}", response_class=HTMLResponse)
async def save_item(request: Request, model: str, item_id: int = None,
                    db: AsyncSession = Depends(get_db)):
    pydantic_model = FIELDS[model]['pydantic_model']
    form_data = await request.form()
    print("========form_data", form_data)
    form_dict = {k: v for k, v in form_data.items()}
    print("========form_dict", form_dict)

    for key, value in form_dict.items():
        if value.lower() == 'true':
            form_dict[key] = True
        elif value.lower() == 'false':
            form_dict[key] = False

    try:
        form = pydantic_model(**form_dict)
    except ValidationError as e:
        return templates.TemplateResponse("references_form.html", {
            'request': request,
            'title': f'Создать {FIELDS[model]["name1"]}' if item_id is None else f'Редактировать {FIELDS[model]["name"]}',
            'url': f'/references/{model}/' if item_id is None else f'/references/{model}/{item_id}',
            'fields': FIELDS[model]['fields'],
            'item': form_dict,
            'errors': e.errors()
        })

    print("========form", form.dict())

    model_class = FIELDS[model]['model']
    if item_id:
        item = await db.get(model_class, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        for k, v in form.dict().items():
            setattr(item, k, v)
    else:
        item = model_class(**form.dict())
        db.add(item)

    await db.commit()
    await db.refresh(item)
    return RedirectResponse(url=f'/references#tab_{model}', status_code=303)


@router.get("/{model}/create", response_class=HTMLResponse)
async def create_page(request: Request, model: str, db: AsyncSession = Depends(get_db)):
    context = {
        'request': request,
        'title': f'Создать {FIELDS[model]["name1"]}',
        'url': f'/references/{model}/',
        'fields': FIELDS[model]['fields'],
        'item': {},
    }

    if model == 'objects':
        organizations = (await db.execute(select(Organization))).scalars().all()
        context['data'] = {'organizations': organizations}

    return templates.TemplateResponse("references_form.html", context)


@router.get("/{model}/edit/{item_id}", response_class=HTMLResponse)
async def edit_page(request: Request, model: str, item_id: int, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_admin_user)):
    model_class = FIELDS[model]['model']
    item = await db.get(model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    context = {
        'request': request,
        'title': f'Редактировать {FIELDS[model]["name"]}',
        'url': f'/references/{model}/{item_id}',
        'fields': FIELDS[model]['fields'],
        'item': item,
    }

    if model == 'objects':
        organizations = (await db.execute(select(Organization))).scalars().all()
        context['data'] = {'organizations': organizations}

    return templates.TemplateResponse("references_form.html", context)


@router.post("/{model}/{action}/{item_id}", response_class=HTMLResponse)
@router.get("/{model}/{action}/{item_id}", response_class=HTMLResponse)
async def toggle_active_status(request: Request, model: str, action: str, item_id: int,
                               db: AsyncSession = Depends(get_db)):
    model_class = FIELDS[model]['model']
    item = await db.get(model_class, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if action == "delete":
        item.active = False
    elif action == "restore":
        item.active = True
    else:
        raise HTTPException(status_code=400, detail="Неверное действие")
    await db.commit()
    next_url = request.query_params.get("next", f"/references#{model}")
    return RedirectResponse(url=next_url, status_code=303)
