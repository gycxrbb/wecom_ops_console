from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import authenticate
from ..services.crm_admin_auth import CrmAdminAuthUnavailable

router = APIRouter()

@router.post('/login')
def do_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = authenticate(db, username, password)
    except CrmAdminAuthUnavailable:
        raise HTTPException(status_code=503, detail="CRM 用户库暂时不可用，请稍后重试")
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    request.session['user_id'] = user.id
    return {"code": 0, "message": "success"}

@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    return {"code": 0, "message": "success"}
