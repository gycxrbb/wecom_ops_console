# 素材库-RAG 接入规划与入库方案

> 文档日期: 2026-04-27  
> 适用范围: 素材库图片、视频、表情包、文件与健康教练 AI 助手 RAG 的衔接  
> 关联文档: `docs/RAG集成到wecom项目手册.md`、`docs/RAG语料准备与标注工作计划.md`、`docs/AI对话RAG检索逻辑调研与改进报告.md`  
> 当前阶段: 话术管理-RAG 已完成第一阶段初测，下一阶段准备打通素材库-RAG。

---

## 1. 先给结论

素材库-RAG 不建议做“所有素材全量自动入 RAG”。

更稳的模式是：

```text
素材库 materials 继续作为图片/视频/文件资产 truth
  ↓
运营/教练主管从素材库中选择可用于 AI 推荐的素材
  ↓
为素材补齐文字语义、适用场景、可发状态、安全等级
  ↓
确保素材有可交付地址 public_url 或可解析的素材 ID
  ↓
写入 RAG 索引层 rag_resources / rag_chunks / Qdrant
  ↓
AI 对话召回素材语义
  ↓
前端展示推荐素材卡片，供教练预览、下载、转发或进入发送中心
```

核心判断：

1. **素材库是 official asset truth**  
   `materials / asset_folders / material_storage_records` 负责文件本体、存储地址、预览、下载、文件夹、启停状态。

2. **RAG 是 support index，不替代素材库**  
   `rag_resources / rag_chunks / Qdrant` 只保存用于检索的语义文本、标签、索引和召回审计。

3. **不是所有素材都应该进入 RAG**  
   表情包、临时活动图、过期海报、无审核来源图、重复图片、没有业务语义的文件，不适合直接进入 RAG。

4. **图片/视频要能被检索，必须先变成文字语义**  
   图片需要 `alt_text` 和使用说明；视频需要摘要，最好有转写文本。只有 URL、文件名、普通 tags 不够。

5. **素材要能推送到前端，必须有交付地址**  
   RAG 命中的是语义索引；前端展示、预览、下载、发送中心需要的是 `materials.id` 和 `materials.public_url/url`。公网地址必须落在素材库资产层，不能只写在 CSV 或 RAG payload 里。

6. **第一阶段先做精选 P0 小样本**  
   建议先做 30-50 个图片素材、10-20 个视频素材，覆盖晒餐、餐评、外食、控糖科普、晚间零食、平台期、打卡唤回等高频场景。

---

## 2. 为什么不能全量素材自动入 RAG

素材库最初的定位是“教练日常管理用户时常用素材的存储地”。这个定位没有问题，但它和 RAG 的要求不同。

素材库里的文件通常有几类：

| 类型 | 是否适合入 RAG | 原因 |
| --- | --- | --- |
| 标准科普图 | 适合 | 有稳定知识价值，可被 AI 推荐 |
| 餐盘示例图 | 适合 | 和餐评、晒餐、外食场景强相关 |
| 控糖/减重方法视频 | 适合 | 可作为解释和转发素材 |
| 教练常用表情包 | 有选择 | 适合情绪陪伴，但不适合进入 prompt 作为知识依据 |
| 临时活动海报 | 通常不适合 | 时效性强，过期后会污染召回 |
| 群运营截图 | 通常不适合 | 可能含隐私、二维码、活动上下文 |
| 未授权网络图片 | 不适合 | 版权状态不清 |
| 文件名不清楚的历史素材 | 暂不适合 | 没有语义，检索会弱且容易误召回 |
| 医疗敏感图表 | 谨慎 | 需要主管/专业审核，不能直接对客户推荐 |

如果全量入 RAG，会出现这些问题：

1. AI 会推荐过期素材。
2. AI 会把内部参考图误推荐给客户。
3. 用户问饮食问题时，召回表情包或活动海报。
4. 图片没有语义，向量检索只看文件名和 tags，召回质量很弱。
5. 版权不清或含隐私的素材被前端展示。
6. 未来审计时无法解释“为什么推荐这张图”。

所以，素材库-RAG 应采用 **选择性入库 + 审核状态 + 语义补全**。

---

## 3. 当前代码真值

### 3.1 素材库现状

当前素材库 official 表：

```text
materials
asset_folders
material_storage_records
```

模型文件：

```text
app/models.py
```

`materials` 当前核心字段：

| 字段 | 作用 |
| --- | --- |
| `id` | 素材 ID |
| `name` | 文件名/展示名 |
| `material_type` | 当前主要是 `image` 或 `file` |
| `storage_path` | 本地路径 |
| `url / public_url` | 外部访问 URL |
| `storage_provider` | local/qiniu |
| `storage_key` | 对象存储 key |
| `storage_status` | ready/deleted/source_missing 等 |
| `mime_type` | 文件 MIME |
| `file_size` | 文件大小 |
| `file_hash` | 文件 hash |
| `tags` | JSON 文本，当前是轻量标签 |
| `folder_id` | 素材文件夹 |
| `enabled` | 是否启用 |
| `deleted_at` | 软删除 |

当前接口：

- 上传: `POST /api/v1/assets`
- 下载: `GET /api/v1/assets/{asset_id}/download`
- 图片预览: `GET /api/v1/assets/{asset_id}/preview`
- 重命名: `PATCH /api/v1/assets/{asset_id}/rename`
- 改 tags: `PATCH /api/v1/assets/{asset_id}/tags`
- 移动文件夹: `PATCH /api/v1/assets/{asset_id}/move`
- 删除: `DELETE /api/v1/assets/{asset_id}`

### 3.2 公网地址当前真值

素材要被 RAG 推荐到前端，至少要满足两层地址口径：

| 层级 | 字段 | 用途 |
| --- | --- | --- |
| 素材库资产层 | `materials.id` | 前端、发送中心、审计回查的稳定素材 ID |
| 素材库资产层 | `materials.public_url` | 客户可访问或可转发的公网地址，优先用于图片/视频发送 |
| 素材库资产层 | `materials.url` | 兼容旧字段，可作为 fallback |
| 素材库资产层 | `materials.storage_provider/storage_key` | 解析真实存储位置，例如 local/qiniu |
| 素材库资产层 | `materials.storage_status` | 必须为 `ready` 才能推荐 |
| RAG 返回层 | `recommended_assets.public_url` | 前端发送、复制、进入发送中心时使用 |
| RAG 返回层 | `recommended_assets.preview_url/download_url` | 前端预览或下载时使用 |

当前 `app/rag/retriever.py` 的 `_build_recommended_assets()` 已经会读取：

```text
preview_url = mat.public_url or mat.url
download_url = mat.public_url or mat.url
public_url = mat.public_url
```

所以开发时必须注意：

1. **最终可交付地址要落在 `materials.public_url`。**
2. CSV 中的 `material_url` 只能作为导入辅助字段，不能替代素材库真值。
3. 如果素材还在本地存储且没有公网地址，可以用于后台预览，但不应标记为 `customer_sendable=yes`。
4. 七牛或其他对象存储上传成功后，应同步写入 `public_url/storage_provider/storage_key/storage_status`。
5. 发送中心和客户侧转发优先使用 `public_url`，不要依赖需要登录态的 `/api/v1/assets/{id}/preview`。
6. 如果第一阶段只能本地预览，可以先把 `visibility` 设为 `coach_internal`，待公网地址补齐后再升级为 `customer_sendable`。

### 3.3 RAG 素材索引现状

当前已有素材索引函数：

```text
app/rag/resource_indexer.py
index_materials()
```

当前逻辑：

```text
读取 enabled=1 且 deleted_at is null 的 materials
  -> 用 name + tags + material_type 构造 semantic_text
  -> semantic_quality = weak
  -> 写 rag_resources(source_type='material')
  -> 写 rag_chunks
  -> 写 Qdrant point
```

当前问题：

1. 会尝试索引所有启用素材，没有“RAG 可用素材”的选择状态。
2. 语义文本只有文件名、tags、类型，图片/视频真实内容不可知。
3. Qdrant payload 目前缺少素材业务标签，例如 `customer_goal / intervention_scene / question_type / delivery_channel`。
4. `content_kind` 只粗略区分 `image` 或 `file`，视频没有正式口径。
5. `visibility` 默认 `coach_internal`，无法区分可发客户素材。
6. `semantic_quality=weak` 说明这只是候选弱接入，不应作为正式素材推荐质量。

因此，当前代码算“素材库-RAG 技术通道已经有雏形”，但还不是正式业务闭环。

---

## 4. 推荐整体模式

### 4.1 三层分工

#### 第一层：素材库资产层

职责：

- 保存图片/视频/文件本体。
- 管理上传、下载、预览、删除、存储迁移。
- 记录文件 hash、存储 provider、storage_key、public_url、storage_status、enabled、folder。
- 为前端素材卡、发送中心和审计回查提供稳定 `materials.id`。

对应表：

```text
materials
asset_folders
material_storage_records
```

这是 official asset truth。

资产层强规则：

1. `public_url` 是客户可访问素材的正式交付地址。
2. `storage_status != ready` 的素材不能进入正式推荐。
3. `public_url` 为空的素材不能标记为 `customer_sendable=yes`。
4. RAG 索引层可以保存 `source_id=materials.id`，但不要复制和维护另一份文件 URL truth。

#### 第二层：素材语义治理层

职责：

- 说明素材讲什么。
- 说明什么时候用。
- 说明能不能发客户。
- 说明适用场景和禁忌。
- 说明是否已审核。

第一阶段可以先通过 CSV 导入到 RAG 索引层，不急着大改素材库表。

后续如果素材库 UI 要支持长期治理，可以新增素材语义表或给 `materials` 补字段。

#### 第三层：RAG 索引层

职责：

- 把已审核素材变成 `rag_resources`。
- 把语义文本切片成 `rag_chunks`。
- 把向量和 payload 写入 Qdrant。
- AI 对话只读取 RAG 索引，不直接扫描素材库。

对应表：

```text
rag_resources
rag_resource_tags
rag_chunks
rag_retrieval_logs
```

这是 support index，不是素材本体 truth。

### 4.2 状态流转

建议建立一套素材 RAG 状态：

```text
素材已上传
  -> candidate 候选
  -> metadata_ready 已补语义
  -> approved 已审核
  -> indexed 已入 RAG
  -> active 可召回
  -> disabled 停用
  -> archived 归档
```

第一阶段可以压缩成 CSV 字段：

```text
status = candidate | approved | disabled
rag_enabled = yes | no
customer_sendable = yes | no
```

入 RAG 的最低条件：

1. `rag_enabled = yes`
2. `status = approved`
3. `storage_status = ready`
4. `enabled = 1`
5. 有 `title`
6. 有 `summary`
7. 图片有 `alt_text`
8. 视频有 `summary`，最好有 `transcript`
9. 有 `visibility`
10. 有 `safety_level`
11. 如果 `customer_sendable = yes`，必须有 `public_url`

地址状态建议：

| 场景 | 是否可入 RAG | 是否可推送前端 | 是否可发客户 |
| --- | --- | --- | --- |
| `storage_status=ready` 且有 `public_url` | 是 | 是 | 取决于 `customer_sendable` |
| `storage_status=ready` 但无 `public_url` | 可作为内部候选 | 可后台预览 | 否 |
| `storage_status=source_missing/deleted` | 否 | 否 | 否 |
| CSV 只有 `material_url` 但未落 `materials` | 不建议直接入 active | 不稳定 | 否 |

---

## 5. 哪些素材进入 RAG

### 5.1 P0 推荐入库素材

第一阶段建议只选这些：

| 场景 | 图片素材 | 视频素材 | 说明 |
| --- | --- | --- | --- |
| 晒餐提醒 | 标准晒餐示例、拍照角度示例 | 晒餐流程短视频 | 帮教练提醒用户怎么拍、怎么提交 |
| 餐评反馈 | 餐盘结构图、主食/蛋白/蔬菜比例图 | 餐盘搭配讲解 | 配合餐评话术使用 |
| 外食外卖 | 外卖点餐示例、便利店选择图 | 外食选择指南 | 和已打通的话术 RAG 强相关 |
| 晚间零食 | 替代食物图、低负担加餐图 | 晚间嘴馋处理 | 用于破阻力和安抚 |
| 控糖科普 | 升糖速度图、餐后血糖曲线图 | 控糖原理讲解 | 需注意安全等级 |
| 平台期 | 体重波动图、平台期解释图 | 平台期心态视频 | 适合情绪支持 |
| 打卡唤回 | 打卡示例、激励图 | 打卡流程短视频 | 可和唤回话术配套 |

### 5.2 P0 暂不入库素材

1. 纯表情包，除非明确用于情绪陪伴且已标注使用场景。
2. 过期活动图、过期海报。
3. 含二维码、微信群名、客户头像、聊天记录的截图。
4. 未确认版权的网络图片。
5. 文件名无法识别且没有摘要的历史素材。
6. 医疗诊断、用药、检查单解释类素材。
7. 只给内部培训看的高风险资料。

### 5.3 表情包怎么处理

表情包不建议第一批进入“知识型 RAG prompt 注入”。

更合适的模式：

```text
表情包作为素材推荐 attachment
  -> 只在 emotional_support / low_motivation / no_checkin 等场景触发
  -> 不进入 AI 回答依据
  -> 不注入 prompt 作为知识
  -> 前端作为可选发送素材展示
```

原因：

- 表情包不是知识依据。
- 向量语义通常很弱。
- 容易在不该出现的专业问答里被误召回。

如果要做，必须有：

- `content_kind = meme`
- `intervention_scene = emotional_support`
- `visibility = customer_sendable`
- `safety_level = general`
- `usage_note = 用于轻松鼓励，不用于医疗/饮食建议`

---

## 6. 图片/视频如何变成可检索语义

### 6.1 图片语义文本

图片入 RAG 不能只靠 URL。

建议生成 `semantic_text`：

```text
标题: 外卖点餐优选示例图
摘要: 这张图展示外卖场景下如何优先选择轻食、清蒸肉类、卤蛋、蔬菜和半份主食，适合出差和外卖用户点餐前参考。
图片说明: 图片包含三类外卖组合示例：轻食沙拉加鸡胸肉、便利店饭团加水煮蛋和小番茄、中式快餐半份米饭加清蒸鱼和青菜。重点强调少油少盐、酱料分开、主食减半。
使用场景: 用户出差、点外卖、无法自己做饭时，教练可以搭配点餐指导话术发送。
适用人群: 减重、控糖、外食频繁用户。
禁忌提醒: 不替代个性化营养处方，肾病、孕期等特殊人群需谨慎。
标签: weight_loss, glucose_control, dining_out, meal_review, nutrition_education
```

最低必填：

- `title`
- `summary`
- `alt_text`
- `usage_note`
- `customer_goal`
- `intervention_scene`
- `visibility`
- `safety_level`

### 6.2 视频语义文本

视频建议生成：

```text
标题: 外食点餐 3 步法短视频
摘要: 1 分 30 秒短视频，讲解外食时如何按蛋白质、蔬菜、主食三步选择，适合出差、外卖和聚餐前提醒。
视频转写: ...
分段要点:
1. 先选蛋白质，优先蒸煮炖。
2. 再补蔬菜，避免重油勾芡。
3. 主食半份或换成粗粮。
使用场景: 用户出差、聚餐、外卖不知道怎么选时。
适用人群: 减重、控糖、外食频繁用户。
```

最低必填：

- `title`
- `summary`
- `usage_note`
- `duration_seconds`
- `customer_goal`
- `intervention_scene`
- `visibility`
- `safety_level`

建议必填：

- `transcript`
- `cover_url`
- `key_frames_note`

视频没有转写也可以先入库，但应标记：

```text
semantic_quality = weak | medium
```

不应和有完整转写的视频同等优先级。

---

## 7. CSV 标注模板

你现在的 `docs/shujubiaozhu/test.csv` 已适合话术类数据。素材类可以沿用同一套字段，但需要扩展图片/视频专属字段。

### 7.1 推荐素材 CSV 字段

```csv
source_id,source_type,source_location,owner,title,material_ref,file_name,file_type,mime_type,storage_provider,storage_status,material_url,public_url,cover_url,clean_content,summary,alt_text,transcript,usage_note,status,rag_enabled,customer_sendable,customer_goal,intervention_scene,content_kind,visibility,safety_level,question_type,tone,delivery_channel,copyright_status,reviewer,review_note
```

字段说明：

| 字段 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `source_id` | 是 | `rag_material_001` | CSV 内部编号 |
| `source_type` | 是 | `material` | 固定为 material |
| `source_location` | 是 | `素材库/饮食/外食` | 原始来源或文件夹 |
| `owner` | 是 | `内容运营` | 内容责任人 |
| `title` | 是 | `外卖点餐优选示例图` | 业务标题，不要只写文件名 |
| `material_ref` | 建议 | `materials.id=123` | 已上传素材库时填素材 ID |
| `file_name` | 是 | `waimai-guide-001.png` | 原始文件名 |
| `file_type` | 是 | `image` / `video` / `meme` / `file` | 素材类型 |
| `mime_type` | 建议 | `image/png` | 文件 MIME |
| `storage_provider` | 建议 | `qiniu` / `local` | 素材当前存储 provider |
| `storage_status` | 是 | `ready` | 必须 ready 才能推荐 |
| `material_url` | 否 | 原始来源 URL | 迁移/导入辅助字段，不作为最终 truth |
| `public_url` | 可发客户必填 | 七牛 CDN URL | 前端发送和客户访问使用，最终应落到 `materials.public_url` |
| `cover_url` | 视频建议 | 视频封面 URL | 方便前端展示 |
| `clean_content` | 是 | 语义正文 | 可由 summary + alt_text/transcript + usage_note 拼接 |
| `summary` | 是 | 50-200 字 | 素材讲什么 |
| `alt_text` | 图片必填 | 图片内容说明 | 图片的可检索语义核心 |
| `transcript` | 视频建议 | 视频转写 | 视频的可检索语义核心 |
| `usage_note` | 是 | 什么时候给客户用 | 推荐理由和使用边界 |
| `status` | 是 | `candidate` / `approved` / `disabled` | 审核状态 |
| `rag_enabled` | 是 | `yes` / `no` | 是否进入 RAG |
| `customer_sendable` | 是 | `yes` / `no` | 是否可发客户 |
| `customer_goal` | 是 | `weight_loss|glucose_control` | 多值用 `|` |
| `intervention_scene` | 是 | `meal_review|qa_support` | 多值用 `|` |
| `content_kind` | 是 | `image` / `video` / `meme` / `file` | RAG 内容类型 |
| `visibility` | 是 | `coach_internal` / `customer_sendable` | 可见范围 |
| `safety_level` | 是 | `general` / `nutrition_education` / `medical_sensitive` | 安全等级 |
| `question_type` | 建议 | `dining_out` | 问题类型 |
| `tone` | 建议 | `专业温和` | 推荐使用语气 |
| `delivery_channel` | 建议 | `private_chat|group_chat` | 推荐发送渠道 |
| `copyright_status` | 是 | `self_owned` / `authorized` / `unknown` | 版权状态 |
| `reviewer` | approved 必填 | `主管` | 审核人 |
| `review_note` | 建议 | `可直接发客户` | 审核备注 |

### 7.2 示例：图片素材

```csv
source_id,source_type,source_location,owner,title,material_ref,file_name,file_type,mime_type,storage_provider,storage_status,material_url,public_url,cover_url,clean_content,summary,alt_text,transcript,usage_note,status,rag_enabled,customer_sendable,customer_goal,intervention_scene,content_kind,visibility,safety_level,question_type,tone,delivery_channel,copyright_status,reviewer,review_note
rag_material_001,material,素材库/饮食/外食,内容运营,外卖点餐优选示例图,materials.id=123,waimai-guide-001.png,image,image/png,qiniu,ready,,https://cdn.example.com/materials/waimai-guide-001.png,,外卖场景点餐示例图，展示轻食、便利店和中式快餐三种组合，强调少油少盐、酱料分开、主食半份。,用于出差和外卖用户点餐前参考，帮助客户快速选择更稳的餐食组合。,图片包含轻食鸡胸肉沙拉、便利店饭团加水煮蛋和小番茄、中式快餐半份米饭加清蒸鱼和青菜三类示例。,,客户说出差、外卖不知道怎么选时，教练可搭配外食点餐话术发送。,approved,yes,yes,weight_loss|glucose_control,meal_review|qa_support,image,customer_sendable,nutrition_education,dining_out,实用落地,private_chat|group_chat,self_owned,主管,可直接发客户
```

### 7.3 示例：视频素材

```csv
rag_material_002,material,素材库/饮食/视频,内容运营,外食点餐三步法短视频,materials.id=124,dining-out-3steps.mp4,video,video/mp4,qiniu,ready,,https://cdn.example.com/materials/dining-out-3steps.mp4,https://cdn.example.com/materials/dining-out-3steps-cover.jpg,外食点餐三步法：先选蛋白质，再补蔬菜，最后控制主食。适合出差、聚餐、外卖前提醒。,1分30秒短视频，讲解外食时如何按蛋白质、蔬菜、主食三步选择。,,视频开头说明外食不是不能吃，关键是选择顺序；第一步优先蒸煮炖蛋白质；第二步补充非油炸蔬菜；第三步主食半份或换粗粮；最后提醒酱料分开少油少盐。,客户外食频繁或聚餐前，教练可发送该视频做预防性提醒。,approved,yes,yes,weight_loss|glucose_control,qa_support|habit_education,video,customer_sendable,nutrition_education,dining_out,专业温和,private_chat,self_owned,主管,可直接发客户
```

---

## 8. 入库方案

### 8.1 第一阶段：CSV 驱动的半自动入库

适合当前阶段。

流程：

```text
运营整理素材 CSV
  -> 人工上传文件到素材库
  -> CSV 中填 material_ref，并确认 public_url/storage_status
  -> 导入脚本校验字段
  -> 匹配 materials 记录
  -> 必要时把 CSV public_url 回写到 materials.public_url
  -> 写入 rag_resources
  -> 写入 rag_chunks
  -> 写入 Qdrant
  -> 在 AI 对话中返回 recommended_assets
```

优点：

- 不需要先大改素材库 UI。
- 可以快速验证图片/视频 RAG 是否有业务价值。
- 运营可用 Excel/飞书表格先跑起来。

缺点：

- CSV 和素材库之间要靠 `material_ref / file_name / file_hash` 匹配。
- 后续维护不如 UI 直观。

地址处理规则：

1. 推荐路径是先上传到素材库，再用 `material_ref=materials.id=...` 关联。
2. 如果 CSV 有 `public_url`，但 `materials.public_url` 为空，导入脚本可以回写 `materials.public_url`，并记录操作日志。
3. 如果 CSV 只有 `material_url`，导入脚本只能把它当作来源线索；除非它确认是稳定 CDN 公网地址，否则不能直接写成 `public_url`。
4. 如果 `customer_sendable=yes` 但没有 `public_url`，导入应报错或降级为 `coach_internal`，不能静默通过。
5. 如果 `storage_status != ready`，即使语义字段完整，也只能跳过 active 索引。

### 8.2 第二阶段：素材库 UI 增加 RAG 标注面板

在素材详情页新增：

1. 是否进入 RAG。
2. 业务标题。
3. 摘要。
4. 图片说明/视频转写。
5. 使用说明。
6. 适用场景。
7. 适用目标。
8. 安全等级。
9. 可发客户状态。
10. 审核状态。
11. 重新索引按钮。

这样素材库会从“文件仓库”升级为“可运营的素材知识资产库”。

### 8.3 第三阶段：AI 辅助标注

后续可以让 AI 帮忙生成候选：

- 图片 alt_text。
- 视频摘要。
- 标签候选。
- 使用说明候选。
- 风险提示候选。

但 AI 输出只能是 candidate，不可直接 active。

必须有人工审核：

```text
AI 生成候选
  -> 运营编辑
  -> 教练主管审核
  -> approved
  -> indexed
```

---

## 9. 推荐开发拆分

### Phase 1: 先把素材 RAG 规则定住

目标：

- 明确不是全量素材入 RAG。
- 明确入库最低字段。
- 明确图片/视频 CSV 模板。
- 明确 RAG 索引只接 `approved + rag_enabled=yes + storage_status=ready`。

产物：

- 本文档。
- 一份素材 CSV 样例。
- P0 素材候选清单。

### Phase 2: 导入脚本

建议新增：

```text
scripts/import_materials_rag_csv.py
```

职责：

1. 读取素材 CSV。
2. 校验必填字段。
3. 解析多值标签。
4. 匹配素材库 `materials`：
   - 优先 `material_ref=materials.id=123`
   - 其次 `file_hash`
   - 再其次 `file_name + file_size`
   - 最后才用 `material_url`
5. 对 `status != approved` 或 `rag_enabled != yes` 的行跳过。
6. 对 `copyright_status=unknown` 的行跳过或标记 disabled。
7. 校验 `materials.storage_status == ready`。
8. 如果 `customer_sendable=yes`，校验或回写 `materials.public_url`。
9. 构造 `semantic_text`。
10. 写 `rag_resources(source_type='material')`。
11. 写 `rag_chunks` 和 Qdrant。
12. 输出 created/updated/skipped/errors。

导入脚本必须输出跳过原因：

| 跳过原因 | 说明 |
| --- | --- |
| `not_approved` | 未审核通过 |
| `rag_disabled` | `rag_enabled != yes` |
| `material_not_found` | 找不到素材库记录 |
| `storage_not_ready` | 素材存储状态不可用 |
| `missing_public_url` | 可发客户素材缺少公网地址 |
| `missing_alt_text` | 图片缺少说明 |
| `missing_summary` | 缺少摘要 |
| `copyright_unknown` | 版权状态不清 |

### Phase 3: 改造 `index_materials()`

当前 `index_materials()` 全量索引 enabled 素材且 `semantic_quality=weak`。

建议改成：

```text
默认只索引 rag_resources 中已 approved 的素材语义
或只索引 materials 中明确 rag_enabled 的素材
```

第一阶段如果还没有新字段，可以先保留旧函数但不作为正式入口，把正式素材索引放到 CSV 导入脚本里。

### Phase 4: 检索策略支持素材

当前检索过滤：

```python
filters = {"content_kind": ["script", "text", "knowledge_card"]}
```

素材接入后要调整：

```text
知识/话术上下文:
  script, text, knowledge_card

推荐素材:
  image, video, meme, file
```

建议不要把图片/视频全文直接大量注入 prompt。

更稳的做法：

1. 话术/知识卡用于 prompt support context。
2. 素材命中用于 `recommended_assets`。
3. 图片/视频只把摘要和使用说明给模型参考，不把附件本体当作回答依据。

### Phase 5: 前端展示与发送中心

前端展示应区分：

1. AI 正式回复。
2. 参考话术。
3. 推荐素材。

素材卡片应展示：

- 缩略图/封面。
- 标题。
- 简短推荐理由。
- 安全/可发状态。
- 预览。
- 下载。
- 发送到发送中心。

发送中心规则：

- `customer_sendable=yes` 才允许一键发送。
- `coach_internal` 只允许内部查看，不允许发送客户。
- `medical_sensitive` 不允许一键发送，必须人工确认或禁用。

推荐素材返回结构建议：

```json
{
  "material_id": 123,
  "title": "外卖点餐优选示例图",
  "material_type": "image",
  "preview_url": "https://cdn.example.com/materials/waimai-guide-001.png",
  "download_url": "https://cdn.example.com/materials/waimai-guide-001.png",
  "public_url": "https://cdn.example.com/materials/waimai-guide-001.png",
  "cover_url": null,
  "reason": "客户正在咨询出差外卖点餐，可搭配该图说明优选组合",
  "visibility": "customer_sendable",
  "safety_level": "nutrition_education",
  "customer_sendable": true,
  "source_type": "material",
  "resource_id": 88
}
```

开发口径：

1. `public_url` 为空时，前端只能展示内部预览/下载，不允许进入客户发送动作。
2. `preview_url` 可以是 CDN 地址，也可以是后端预览地址；`public_url` 必须是客户可访问地址。
3. 发送中心创建素材消息时优先使用 `material_id` 回查素材库，再读取最新 `public_url/storage_status`，不要只相信前端传回的 URL。
4. 素材推荐卡片要展示“可发客户/内部参考/需审核”状态，避免教练误发。

---

## 10. `semantic_text` 生成规则

### 10.1 推荐拼接模板

对素材生成语义文本时，建议按下面顺序拼：

```text
标题: {title}
摘要: {summary}
内容说明: {alt_text 或 transcript}
使用场景: {usage_note}
适用目标: {customer_goal}
干预场景: {intervention_scene}
问题类型: {question_type}
适用渠道: {delivery_channel}
安全等级: {safety_level}
可见范围: {visibility}
审核备注: {review_note}
```

### 10.2 质量等级

建议保留 `semantic_quality`：

| 质量 | 判定 |
| --- | --- |
| `ok` | 有 title、summary、alt_text/transcript、usage_note、标签、审核 |
| `medium` | 有 title、summary、usage_note、标签，但图片说明/视频转写不完整 |
| `weak` | 只有文件名或普通 tags |

检索推荐时：

- P0 推荐只展示 `ok / medium`。
- `weak` 可以入索引用于调试，但不进入正式推荐。

---

## 11. 与话术管理-RAG的关系

话术管理-RAG 和素材库-RAG 不应混成一类。

### 11.1 话术管理-RAG

用途：

- 给 AI 回答提供表达参考。
- 给教练可复制话术。
- 可以进入 prompt support context。

典型 source：

```text
source_type = speech_template
content_kind = script
```

### 11.2 素材库-RAG

用途：

- 给教练推荐可发送附件。
- 给 AI 回答提供“可配套素材”的建议。
- 不应默认作为大段知识注入 prompt。

典型 source：

```text
source_type = material
content_kind = image | video | meme | file
```

### 11.3 同一场景下如何组合

用户问：

```text
客户要出差，推荐一下餐食
```

理想结果：

```text
AI 正式回复:
  结合客户情况，给教练一段出差点餐建议。

参考话术:
  出差外食外卖场景点餐指导话术。

推荐素材:
  外卖点餐优选示例图。
  外食点餐三步法短视频。
```

这三者要分开展示、分开复制、分开发送。

---

## 12. 验收标准

### 12.1 入库验收

P0 素材 CSV 导入后，应满足：

1. approved + rag_enabled=yes 的素材进入 RAG。
2. disabled/candidate/rag_enabled=no 的素材不进入 active 索引。
3. 没有 alt_text 的图片不进入正式推荐。
4. 没有 summary 的视频不进入正式推荐。
5. copyright_status=unknown 的素材不进入 customer_sendable。
6. `customer_sendable=yes` 的素材必须有 `materials.public_url`。
7. `storage_status != ready` 的素材不能进入 active 索引。
8. CSV 中 `public_url` 如被采用，必须回写或校验到 `materials.public_url`，不能只存在 CSV。
9. Qdrant payload 包含：
   - `resource_id`
   - `source_type=material`
   - `source_id`
   - `content_kind`
   - `status`
   - `visibility`
   - `safety_level`
   - `customer_goal`
   - `intervention_scene`
   - `question_type`
   - `semantic_quality`

### 12.2 检索验收

准备 20 个评估问题：

| 问题 | 期望命中 |
| --- | --- |
| 客户要出差怎么点外卖 | 外卖点餐图、外食三步法视频 |
| 客户晚上嘴馋想吃甜的 | 晚间零食替代图 |
| 客户不知道怎么拍晒餐 | 晒餐拍照示例图 |
| 客户餐后血糖波动大 | 控糖科普图，注意安全等级 |
| 客户三天没打卡怎么提醒 | 打卡示例或轻激励素材 |

验收口径：

- Top3 至少命中 1 个正确素材。
- 不推荐过期活动图。
- 不推荐 coach_internal 给一键发送。
- 不推荐 medical_sensitive 作为可直接发客户素材。
- 表情包只在情绪支持类问题中出现。

### 12.3 前端验收

AI 对话里素材推荐应满足：

1. 素材卡片和 AI 正文分开。
2. 图片可预览。
3. 视频有封面或至少显示标题和摘要。
4. 可发客户素材可以进入发送中心。
5. 内部素材不能一键发送。
6. 推荐理由可读，不只是“与当前问题相关”。
7. `public_url` 为空的素材不展示“一键发送”。
8. 前端发送前通过 `material_id` 回查或复用后端确认结果，避免发送过期 URL。
9. 后端返回的 `recommended_assets.public_url` 与素材库 `materials.public_url` 保持一致。

---

## 13. P0 业务准备清单

建议业务侧先准备：

| 类型 | 数量 | 要求 |
| --- | ---: | --- |
| 图片 | 30-50 | 有 title、summary、alt_text、usage_note |
| 视频 | 10-20 | 有 title、summary、usage_note，优先有 transcript |
| 表情包 | 5-10 | 只选情绪支持场景，避免泛滥 |
| 评估问题 | 20-30 | 每个问题写期望命中素材 |

优先场景：

1. 外食外卖。
2. 晒餐拍照。
3. 餐盘搭配。
4. 晚间零食。
5. 控糖基础科普。
6. 平台期解释。
7. 打卡唤回。

---

## 14. 当前阶段判断

从负责人视角看：

### 已经能做什么

1. 话术管理-RAG 第一阶段已经初步打通。
2. RAG 表和 Qdrant 索引层已经存在。
3. 当前代码已有 `index_materials()`，说明素材技术通路有雏形。
4. AI 对话已经能返回 `recommended_assets` 结构。

### 半能做什么

1. 素材能弱索引，但语义质量不足。
2. 素材能作为推荐资产返回，但推荐理由和过滤规则还弱。
3. 素材库有 tags，但不是受控 RAG 标签。
4. 图片/视频能存储，但缺少 RAG 可检索说明。

### 还不能做什么

1. 不能全量素材可靠接入 RAG。
2. 不能自动判断哪些素材可发客户。
3. 不能只靠文件名判断图片/视频语义。
4. 不能保证表情包不污染专业问答。
5. 不能把素材召回当作 official 知识依据。

### 当前 blocker

素材缺少结构化语义字段和审核状态。

### 下一步最值得做

先做一份素材 CSV P0 样本，并开发 `import_materials_rag_csv.py`，只让 approved + rag_enabled=yes + semantic_quality 达标的素材进入 RAG active 索引。

开发前置决策：

1. P0 是否统一要求可发客户素材先上传到七牛并写入 `materials.public_url`。建议是。
2. 如果素材没有公网地址，是否只允许作为 `coach_internal` 内部推荐。建议是。
3. `material_url` 是否允许直接成为 `public_url`。建议只允许白名单 CDN 域名，不能把临时链接写成正式公网地址。
4. 发送中心是否只接受 `material_id`，由后端回查 URL。建议是，避免前端传入过期或被篡改的 URL。

---

## 15. 最终建议

素材库-RAG 的正确接法不是“把素材库全量向量化”，而是：

```text
素材库管文件
RAG 管语义索引
运营管选择和标注
主管管审核
AI 管召回和推荐
前端管预览与发送
```

第一阶段请先坚持三个原则：

1. **精选，不全量。**
2. **先补语义，再入向量。**
3. **可发客户必须审核。**

这样素材库会从“文件存储地”升级成“教练可复用的内容资产库”，而 RAG 只负责让这些资产在正确场景被看见、被推荐、被审计。
