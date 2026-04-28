from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..security import authenticate
from ..services.crm_admin_auth import CrmAdminAuthUnavailable
from ..services import login_rate_limiter as rate_limiter

router = APIRouter()

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else ''

@router.post('/login')
def do_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    from ..security import decrypt_rsa_password

    client_ip = _get_client_ip(request)

    # 暴力破解防护
    allowed, retry_after = rate_limiter.check(client_ip, username or '')
    if not allowed:
        raise HTTPException(status_code=429, detail=f'登录失败次数过多，请 {retry_after} 秒后重试')

    password = decrypt_rsa_password(password)

    try:
        user = authenticate(db, username, password)
    except CrmAdminAuthUnavailable:
        raise HTTPException(status_code=503, detail="CRM 用户库暂时不可用，请稍后重试")
    if not user:
        rate_limiter.record_failure(client_ip, username or '')
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    rate_limiter.reset(client_ip, username or '')
    request.session['user_id'] = user.id
    return {"code": 0, "message": "success"}

@router.post('/logout')
def logout(request: Request):
    request.session.clear()
    return {"code": 0, "message": "success"}
