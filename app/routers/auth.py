from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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
        # Check if requested from API (Axios/Vue) or Browser
        if request.headers.get("accept", "").startswith("application/json") or request.headers.get("sec-fetch-mode") == "cors":
            raise HTTPException(status_code=400, detail="用户名或密码错误")
        return templates.TemplateResponse('login.html', {'request': request, 'title': '登录', 'error': '用户名或密码错误'}, status_code=400)
    
    request.session['user_id'] = user.id
    
    if request.headers.get("accept", "").startswith("application/json") or request.headers.get("sec-fetch-mode") == "cors":
        return {"code": 0, "message": "success"}
    return RedirectResponse('/', status_code=302)

@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    if request.headers.get("accept", "").startswith("application/json") or request.headers.get("sec-fetch-mode") == "cors":
        return {"code": 0, "message": "success"}
    return RedirectResponse('/login', status_code=302)
