# AI 附件前端直传七牛云 + 即时预览方案

## 背景

当前 AI 对话上传附件流程：`浏览器 → 后端 → 七牛云`，1.3MB 图片上传耗时 14.7 秒（其中七牛云上传占 14.5 秒）。用户体验严重割裂。

目标：实现 **前端直传七牛云 + 本地预览即时显示**，用户粘贴/选择文件后立即看到预览，后台异步上传，体感"0 延迟"。

## 现有基础设施

素材模块已实现完整的前端直传流程，可直接复用：

| 组件 | 位置 | 状态 |
|------|------|------|
| 七牛 Token 生成 | `app/services/storage/qiniu.py` `prepare_client_upload()` | ✅ 已实现 |
| Token 获取接口 | `POST /v1/assets/prepare-upload` | ✅ 已实现（素材模块） |
| 前端直传逻辑 | `frontend/src/views/Assets/composables/useAssets.ts` `uploadAsset()` | ✅ 已实现 |
| 服务器中转降级 | `POST /v1/assets` (multipart) | ✅ 已实现 |

七牛 Token 格式：`access_key:signature:encoded_policy`，scope 限制到 `bucket:object_key`，1 小时有效期。

## 架构设计

```
┌──────────────────────────────────────────────────────────────────┐
│  用户粘贴/选择文件                                                 │
│       ↓                                                          │
│  ① 前端 Canvas 压缩 (1.3MB → ~200KB, quality 0.8)               │
│       ↓                                                          │
│  ② 本地 blob URL 即时预览 (用户看到图片，0 延迟)                    │
│       ↓                                                          │
│  ③ 后端获取上传凭证                                               │
│     POST /v1/crm-customers/{id}/ai/prepare-upload                │
│     → { mode: "qiniu", token, upload_url, object_key, url }      │
│       ↓                                                          │
│  ┌── mode === "qiniu" ──┐   ┌── mode === "server" ──┐           │
│  │ ④a 前端直传七牛云      │   │ ④b 服务器中转上传      │           │
│  │ fetch(upload_url,     │   │ POST .../upload-       │           │
│  │   FormData(token,key, │   │   attachment           │           │
│  │   file))              │   │ (现有逻辑)             │           │
│  └───────────────────────┘   └───────────────────────┘           │
│       ↓                             ↓                            │
│  ⑤ 确认上传完成                                                   │
│     POST /v1/crm-customers/{id}/ai/confirm-upload                │
│     → 后端写 DB 记录 (attachment_id, storage_key, url)            │
│       ↓                                                          │
│  ⑥ 前端更新 attachment_id (替换临时 ID)                            │
└──────────────────────────────────────────────────────────────────┘
```

## 改动清单

### 1. 后端：新增两个 AI 附件上传接口

**文件：`app/crm_profile/router.py`**

#### `POST /{customer_id}/ai/prepare-upload`

获取上传凭证，复用 `storage_facade.prepare_client_upload()`。

```python
@router.post("/{customer_id}/ai/prepare-upload")
async def ai_prepare_upload(
    customer_id: int,
    body: AiPrepareUploadRequest,  # { filename, mime_type }
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')

    result = storage_facade.prepare_client_upload(body.filename, body.mime_type)
    if result:
        return { "mode": "qiniu", **result }
    return { "mode": "server" }
```

#### `POST /{customer_id}/ai/confirm-upload`

前端直传完成后，后端写 DB 记录。**保留现有的 `POST .../upload-attachment` 作为服务器中转降级路径。**

```python
@router.post("/{customer_id}/ai/confirm-upload")
async def ai_confirm_upload(
    customer_id: int,
    body: AiConfirmUploadRequest,  # { object_key, public_url, filename, mime_type, file_size }
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    require_permission(user, 'crm_profile')

    attachment = CrmAiAttachment(
        attachment_id=uuid.uuid4().hex[:32],
        crm_customer_id=customer_id,
        uploaded_by=user.id,
        original_filename=body.filename,
        mime_type=body.mime_type,
        file_size=body.file_size,
        storage_provider='qiniu',
        storage_key=body.object_key,
        storage_public_url=body.public_url,
        page_count=1,
        processing_status="pending",
    )
    with SessionLocal() as db2:
        db2.add(attachment)
        db2.commit()
        db2.refresh(attachment)
        db2.expunge(attachment)

    # 触发后台 Vision 分析
    _start_background_analysis(attachment)
    return { ... }
```

**文件：`app/crm_profile/schemas/api.py`**

新增请求 schema：

```python
class AiPrepareUploadRequest(BaseModel):
    filename: str
    mime_type: str

class AiConfirmUploadRequest(BaseModel):
    object_key: str
    public_url: str
    filename: str
    mime_type: str
    file_size: int
```

### 2. 后端：保留现有中转接口不变

`POST /{customer_id}/ai/upload-attachment` 保持原样，作为直传失败时的降级路径。移除调试日志后恢复干净。

### 3. 前端：composable 新增直传逻辑

**文件：`frontend/.../composables/useAiCoach.ts`**

新增 `uploadAttachmentDirect()` 方法：

```typescript
const uploadAttachmentDirect = async (
  customerId: number,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<AiAttachment> => {
  // 1. 获取上传凭证
  const cred: any = await request.post(
    `/v1/crm-customers/${customerId}/ai/prepare-upload`,
    { filename: file.name, mime_type: file.type },
  )

  // 2. 直传模式
  if (cred.mode === 'qiniu') {
    const form = new FormData()
    form.append('token', cred.token)
    form.append('key', cred.object_key)
    form.append('file', file)

    const resp = await fetch(cred.upload_url, {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(120_000),
    })
    if (!resp.ok) throw new Error('直传七牛云失败')

    // 3. 确认上传
    const att: any = await request.post(
      `/v1/crm-customers/${customerId}/ai/confirm-upload`,
      {
        object_key: cred.object_key,
        public_url: cred.public_url,
        filename: file.name,
        mime_type: file.type,
        file_size: file.size,
      },
    )
    return att
  }

  // 3. 降级：服务器中转
  return uploadAttachment(customerId, file, onProgress)
}
```

### 4. 前端：组件上传流程改为"即时预览 + 异步直传"

**文件：`frontend/.../components/AiCoachPanel.vue`**

`addAndUploadFile` 改为：

```typescript
const addAndUploadFile = async (file: File) => {
  // ... 校验 ...

  const isImage = file.type.startsWith('image/')
  const compressedFile = isImage ? await compressImage(file) : file

  // ① 即时预览：用原始文件的 blob URL（高清预览）
  const localUrl = isImage ? URL.createObjectURL(file) : undefined
  const tempId = 'temp_' + Date.now()

  // ② 加入待发列表（用户可以立即看到、立即发送）
  pendingAttachments.value.push({
    attachment_id: tempId,
    filename: file.name,
    mime_type: file.type,
    file_size: file.size,
    url: localUrl,
    uploading: true,
    progress: 0,
  })

  // ③ 后台直传（不阻塞 UI）
  uploadingCount.value++
  try {
    const att = await uploadAttachmentDirect(props.customerId, compressedFile, (pct) => {
      const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
      if (idx >= 0) pendingAttachments.value[idx].progress = pct
    })
    // 上传完成，替换临时 ID
    const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
    if (idx >= 0) {
      att.url = localUrl || att.url
      att.uploading = false
      att.progress = 100
      pendingAttachments.value[idx] = att
    }
  } catch (err: any) {
    // 移除失败条目
    const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
    if (idx >= 0) pendingAttachments.value.splice(idx, 1)
    if (localUrl) URL.revokeObjectURL(localUrl)
    ElMessage.error(err?.message || '附件上传失败')
  } finally {
    uploadingCount.value--
  }
}
```

### 5. 发送逻辑适配

发送消息时，如果附件仍在上传中（`uploading: true`），使用临时 ID。但需要后端 `confirm-upload` 返回后前端已替换为真实 ID，所以绝大部分情况下发送时 ID 已是真实的。

极端情况（用户上传还没完成就点发送）：保持现有行为，弹出"附件上传中，请稍候"。

## 降级策略

```
前端尝试直传
  ├─ prepare-upload 返回 mode=qiniu → 直传七牛云
  │    ├─ 直传成功 → confirm-upload → 完成
  │    └─ 直传失败 → 自动降级到 POST .../upload-attachment（服务器中转）
  └─ prepare-upload 返回 mode=server → 直接走服务器中转
       （七牛未配置 / 配置错误时自动走此路径）
```

降级是透明的，用户无感知。

## 性能预期

| 场景 | 当前 | 优化后 |
|------|------|--------|
| 即时预览 | 无（等上传完成才显示） | **0 延迟**（blob URL） |
| 1.3MB 图片上传 | ~15s（后端中转七牛） | ~2-3s（前端压缩后直传 ~200KB） |
| 上传过程 UI | 圆环进度条转圈 | 即时预览 + 小进度角标 |
| Vision 分析 | 发消息时串行分析 | 上传后后台预分析，发送时大概率命中缓存 |

## 验证清单

1. 七牛已配置：上传图片 → 即时预览 → 进度角标 → 消失 → 发送消息 → AI 识别内容
2. 七牛未配置（`.env` 设 `asset_storage_provider=local`）：自动降级到服务器中转，流程正常
3. 直传失败（断网/Token 过期）：自动降级到服务器中转
4. 粘贴截图 → 即时预览 → 上传完成
5. 上传中点击发送 → 提示"附件上传中"
6. 上传完成后发送 → attachment_id 已替换为真实 ID
7. 后台 Vision 预分析 → 发送消息时命中缓存
