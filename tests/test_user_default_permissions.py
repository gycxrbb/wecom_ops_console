"""New-account defaults and administrator revocation across local/CRM entry points."""
import asyncio
import json

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app import models, security
from app.routers.api import upsert_user
from app.routers.api_permissions import update_member_permissions
from app.services.crm_admin_auth import sync_crm_admin_to_local


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    models.User.__table__.create(engine)
    models.AuditLog.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def request(body, user_id):
    async def receive():
        return {'type': 'http.request', 'body': json.dumps(body).encode()}

    return Request({'type': 'http', 'headers': [], 'session': {'user_id': user_id}}, receive)


def admin(db):
    user = models.User(username='admin-test', password_hash='unused', role='admin')
    db.add(user)
    db.commit()
    return user


def test_local_create_defaults_to_own_and_edit_preserves_revocation(db):
    operator = admin(db)
    body = {'username': 'new-local', 'password': 'Test-password-123', 'role': 'coach'}
    result = asyncio.run(upsert_user(request(body, operator.id), db))
    user = db.get(models.User, result['id'])
    assert json.loads(user.permissions_json) == {'crm_profile': 'own'}
    security.require_permission(user, 'crm_profile')

    asyncio.run(update_member_permissions(
        user.id, request({'permissions': {'crm_profile': False}}, operator.id), db,
    ))
    asyncio.run(upsert_user(request({'id': user.id, 'username': user.username}, operator.id), db))
    assert json.loads(user.permissions_json) == {'crm_profile': False}
    with pytest.raises(HTTPException) as exc:
        security.require_permission(user, 'crm_profile')
    assert exc.value.status_code == 403


@pytest.mark.parametrize('permission', ['own', 'all', False])
def test_crm_sync_and_jwt_preserve_admin_choice(db, monkeypatch, permission):
    operator = admin(db)
    crm_admin = {'id': 123, 'username': 'new-crm', 'real_name': 'CRM Coach'}
    user = sync_crm_admin_to_local(db, crm_admin)
    assert json.loads(user.permissions_json) == {'crm_profile': 'own'}
    asyncio.run(update_member_permissions(
        user.id, request({'permissions': {'crm_profile': permission}}, operator.id), db,
    ))
    sync_crm_admin_to_local(db, {**crm_admin, 'real_name': 'Updated Coach'})
    monkeypatch.setattr(security.settings, 'crm_jwt_secret_key', 'test-only-secret-key-at-least-32-bytes')
    token = jwt.encode({'id': 123}, security.settings.crm_jwt_secret_key, algorithm='HS256')
    authenticated = security._try_crm_token_fallback(token, db)
    assert authenticated.id == user.id
    assert json.loads(authenticated.permissions_json) == {'crm_profile': permission}


@pytest.mark.parametrize('stored', ['{}', '{"crm_profile":false}', '{"crm_profile":"all"}'])
def test_existing_explicit_permissions_are_not_replaced(db, stored):
    user = models.User(username='existing', password_hash='unused', permissions_json=stored)
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.permissions_json == stored
