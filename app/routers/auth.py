from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import authenticate
from ..config import TEMPLATE_DIR
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter()

@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get('user_id'):
        return RedirectResponse('/', status_code=302)
    return templates.TemplateResponse('login.html', {'request': request, 'title': '登录'})

@router.post('/login')
def do_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate(db, username, password)
    if not user:
        return templates.TemplateResponse('login.html', {'request': request, 'title': '登录', 'error': '用户名或密码错误'}, status_code=400)
    request.session['user_id'] = user.id
    return RedirectResponse('/', status_code=302)

@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=302)
