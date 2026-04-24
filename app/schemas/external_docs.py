from __future__ import annotations
from pydantic import BaseModel


# ── Resolve Link ──

class ResolveLinkRequest(BaseModel):
    url: str


class ResolveLinkResponse(BaseModel):
    ok: bool
    platform: str = 'unknown'
    doc_type: str = 'unknown'
    source_doc_token: str = ''
    canonical_url: str = ''
    open_url: str = ''
    title_hint: str = ''
    needs_manual_title: bool = True
    warnings: list[str] = []


# ── Resource ──

class ResourceCreate(BaseModel):
    title: str
    canonical_url: str
    open_url: str
    source_platform: str = 'feishu'
    source_doc_token: str | None = None
    doc_type: str = 'unknown'
    summary: str = ''
    owner_user_id: int | None = None
    maintainer_user_id: int | None = None


class ResourceUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    verification_status: str | None = None
    owner_user_id: int | None = None
    maintainer_user_id: int | None = None


class ResourceResponse(BaseModel):
    id: int
    title: str
    canonical_url: str
    open_url: str
    source_platform: str
    doc_type: str
    status: str
    verification_status: str
    summary: str
    last_opened_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


# ── Binding ──

class BindingCreate(BaseModel):
    resource_id: int
    workspace_id: int | None = None
    primary_stage_term_id: int | None = None
    deliverable_term_id: int | None = None
    relation_role: str = 'support'
    is_primary: bool = False
    remark: str = ''


class BindingUpdate(BaseModel):
    relation_role: str | None = None
    is_primary: bool | None = None
    primary_stage_term_id: int | None = None
    deliverable_term_id: int | None = None
    status: str | None = None
    remark: str | None = None


class BindingResponse(BaseModel):
    id: int
    resource_id: int
    workspace_id: int | None
    primary_stage_term_id: int | None
    deliverable_term_id: int | None
    relation_role: str
    is_primary: bool
    status: str
    remark: str


# ── Quick Add (transactional) ──

class QuickAddResource(BaseModel):
    title: str
    canonical_url: str
    open_url: str
    source_platform: str = 'feishu'
    source_doc_token: str | None = None
    doc_type: str = 'unknown'
    summary: str = ''
    owner_user_id: int | None = None
    maintainer_user_id: int | None = None


class QuickAddBinding(BaseModel):
    workspace_id: int | None = None
    primary_stage_term_id: int | None = None
    deliverable_term_id: int | None = None
    relation_role: str = 'support'
    is_primary: bool = False
    remark: str = ''


class QuickAddRequest(BaseModel):
    resource: QuickAddResource
    binding: QuickAddBinding
    open_after_save: bool = False


# ── Workspace ──

class WorkspaceCreate(BaseModel):
    name: str
    workspace_type: str = 'project'
    biz_line: str | None = None
    client_name: str | None = None
    owner_user_id: int | None = None
    description: str = ''
    start_date: str | None = None
    end_date: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    workspace_type: str | None = None
    status: str | None = None
    owner_user_id: int | None = None
    current_stage_term_id: int | None = None
    description: str | None = None


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    workspace_type: str
    status: str
    owner_user_id: int | None
    current_stage_term_id: int | None
    description: str
    created_at: str | None = None
    updated_at: str | None = None


# ── Term ──

class TermResponse(BaseModel):
    id: int
    dimension: str
    code: str
    label: str
    scope_type: str
    sort_order: int
    is_active: bool


# ── Open ──

class OpenRequest(BaseModel):
    workspace_id: int | None = None
    client_type: str = 'web'


class OpenResponse(BaseModel):
    open_url: str
    opened_at: str
