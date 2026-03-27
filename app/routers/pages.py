from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from ..config import TEMPLATE_DIR
from ..database import get_db
from ..security import get_current_user

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter()

@router.get('/', response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
    except Exception:
        return RedirectResponse('/login', status_code=302)
    return templates.TemplateResponse('index.html', {'request': request, 'title': 'WeCom Ops Console', 'user': user})
