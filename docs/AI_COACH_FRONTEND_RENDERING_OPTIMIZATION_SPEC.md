# AI 教练助手前端渲染优化技术规格

> 日期：2026-04-26
>
> 文档状态：plan / candidate design
>
> 适用范围：`CRM 客户档案 + AI 教练助手` 的前端渲染层
>
> 关联文档：`docs/AI_COACH_LATENCY_OPTIMIZATION_PLAN.md`、`docs/CRM_AI_COACH_PHASE2_OPTIMIZATION_PLAN.md`

---

## 1. 这份文档解决什么问题

当前 AI 教练助手已经具备正式可用的会话闭环：能读取客户上下文、发起双 SSE 流、展示思考摘要、输出正式回复、回看历史会话。

但前端渲染层还停留在轻量实现：

1. `AiCoachPanel.vue` 仍承担抽屉布局、会话状态、消息展示、Markdown 渲染、思考框、输入区、侧栏等多种职责，当前约 1588 行，已经超过 Vue 文件大小红线。
2. 助手回复和思考摘要使用 `v-html="renderMarkdown(...)"`，`renderMarkdown` 只做 HTML 转义、换行、粗体、斜体，无法支撑代码块、表格、数学公式、引用、图表等高质量输出。
3. `frontend/src/utils/simpleMarkdown.ts` 也只是项目内自研轻量 Markdown，适合系统教学文章预览，不适合作为 AI 长回答的正式渲染底座。
4. 当前流式渲染已能接收 `loading / meta / delta / done`，但 Markdown 半截状态、代码块未闭合、长内容滚动性能还没有系统治理。

所以本次优化的目标不是“给回答加一点样式”，而是建立一套可扩展、可验证、可复用的 AI 输出渲染层，让 AI 教练助手的输出从“能看”升级到“像正式工作台一样可读、可信、可复盘”。

---

## 2. 当前代码真值

### 2.1 已有能力

当前前端真值：

1. 技术栈为 Vue 3 + Composition API + TypeScript strict + Vite。
2. UI 框架为 Element Plus，已支持深色模式变量。
3. AI 教练助手位于：
   - `frontend/src/views/CrmProfile/components/AiCoachPanel.vue`
   - `frontend/src/views/CrmProfile/composables/useAiCoach.ts`
   - `frontend/src/views/CrmProfile/components/AiSessionHistoryList.vue`
4. `useAiCoach.ts` 已支持：
   - `/ai/chat-stream`
   - `/ai/thinking-stream`
   - `loading / meta / delta / done / error` 事件分发
   - `thinkingContent`
   - `loadingStage`
   - 历史会话恢复
5. `AiCoachPanel.vue` 已有思考框、loading 骨架、正式回复、复制、医疗复核提示等业务 UI。

### 2.2 还没有的能力

当前不能写成 official 的能力：

1. 没有 `markdown-it`、`shiki`、`katex`、`mermaid`、`dompurify`、`@tanstack/vue-virtual` 等渲染依赖。
2. 没有 Tailwind CSS 与 `@tailwindcss/typography`。
3. 没有统一的 `MarkdownRenderer` 组件。
4. 没有可插拔 fence renderer。
5. 没有流式 Markdown 安全闭合缓冲。
6. 没有代码块复制、折叠、行号、语言标签、高亮主题。
7. 没有 RAG 引用角标、来源 tooltip 或来源侧栏。
8. 没有长会话虚拟滚动。

### 2.3 当前风险

1. `v-html` 当前依赖手写 escape 降低风险，但这不是长期安全边界；一旦未来允许 raw HTML 或接入更复杂 Markdown，必须引入 DOMPurify。
2. `AiCoachPanel.vue` 继续追加渲染逻辑会加重维护风险。
3. 如果直接引入整套渲染依赖而不拆组件，会让首包体积和抽屉打开速度变差。
4. Mermaid、KaTeX、Shiki 都应懒加载，不应进入 AI 抽屉首次打开的关键路径。

---

## 3. 本地化目标

这套渲染优化只服务 AI 教练助手的真实业务场景，不照搬通用 Chatbot。

### 3.1 业务视角目标

面向健康教练，AI 输出需要稳定承载：

1. 跟进建议：分点、编号、待办清单。
2. 客户回复草稿：可复制、可直接转给客户。
3. 内部交接备注：结构化小标题、风险提示、下一步动作。
4. 数据解读：表格、趋势总结、异常原因。
5. 安全复核：医疗风险、过敏冲突、运动禁忌提示。
6. 历史复盘：引用历史会话、上下文快照和来源证据。

### 3.2 技术目标

1. 建立统一 `MarkdownRenderer`，替换 AI 教练助手内联 `renderMarkdown`。
2. 建立 `CodeBlock / ThinkingPanel / CitationInline / TableBlock` 等单一职责组件。
3. 建立 `chunkBuffer.safeCloseMarkdown()`，降低流式半截 Markdown 的视觉破碎。
4. 建立 fence renderer 注册机制，后续接入业务卡片，不执行模型输出代码。
5. 保持安全默认值：默认禁用 raw HTML，不使用 `eval` / `Function`，不引入代码执行沙箱。
6. 控制性能：Shiki、Mermaid、KaTeX、medium-zoom 按需加载。

### 3.3 不做什么

第一阶段不做：

1. 不把整个前端迁移到 Tailwind。
2. 不重写 AI 后端协议。
3. 不把 Mermaid 或图表作为默认能力强制加载。
4. 不让模型输出驱动任意组件或执行任意脚本。
5. 不把 candidate 渲染方案写成 official 完成。

---

## 4. 推荐目录结构

当前项目没有全局 chat 模块，AI 教练助手在 CRM 客户档案内，但 Markdown 渲染未来可复用于系统教学、发送中心预览、SOP 文档。因此建议把通用渲染层放在 `frontend/src/components/markdown` 与 `frontend/src/lib/markdown`，把 AI 教练业务包装放在 `CrmProfile/components`。

```text
frontend/src/
├── components/
│   ├── markdown/
│   │   ├── MarkdownRenderer.vue
│   │   ├── CodeBlock.vue
│   │   ├── MermaidBlock.vue
│   │   ├── MathBlock.vue
│   │   ├── ImageBlock.vue
│   │   ├── TableBlock.vue
│   │   ├── LinkInline.vue
│   │   └── CitationInline.vue
│   └── ui/
│       ├── CopyButton.vue
│       └── CollapsiblePanel.vue
├── composables/
│   ├── useMarkdownIt.ts
│   ├── useShiki.ts
│   └── useMermaid.ts
├── lib/
│   ├── markdown/
│   │   ├── index.ts
│   │   ├── sanitize.ts
│   │   └── plugins/
│   │       ├── citation.ts
│   │       ├── thinking.ts
│   │       └── customFence.ts
│   └── streaming/
│       ├── sse.ts
│       └── chunkBuffer.ts
├── styles/
│   ├── markdown.css
│   ├── shiki.css
│   └── katex.css
└── views/
    └── CrmProfile/
        └── components/
            ├── AiCoachPanel.vue
            ├── AiCoachMessageList.vue
            ├── AiCoachMessageItem.vue
            ├── AiCoachAssistantMessage.vue
            ├── AiCoachUserMessage.vue
            └── AiCoachThinkingPanel.vue
```

说明：

1. `MarkdownRenderer` 是通用能力，不绑定 CRM。
2. `AiCoachAssistantMessage` 负责把 AI 教练的 `safetyNotes / requiresMedicalReview / tokenUsage / thinkingContent` 组合起来。
3. `AiCoachThinkingPanel` 是业务包装，底层可复用 `CollapsiblePanel`。
4. `AiCoachPanel.vue` 第一轮应收缩为抽屉框架、顶部栏、侧栏切换和输入区编排，不再承载 Markdown 细节。

---

## 5. 依赖策略

### 5.1 P0 建议新增依赖

```json
{
  "dependencies": {
    "markdown-it": "^14",
    "markdown-it-task-lists": "^2",
    "dompurify": "^3",
    "shiki": "^1"
  },
  "devDependencies": {
    "@types/markdown-it": "^14",
    "@types/dompurify": "^3"
  }
}
```

P0 暂不强制接入 Tailwind，原因是当前项目全局样式体系是 Element Plus + 自定义 CSS。如果一次性加入 Tailwind 与 typography，容易影响全局构建和样式优先级。P0 先用 `styles/markdown.css` 做等价的 `.md-prose` 排版层；如果后续确认要全局接 Tailwind，再在 P1 建立 Tailwind Typography 版本。

### 5.2 P1 建议新增依赖

```json
{
  "dependencies": {
    "katex": "^0.16",
    "markdown-it-katex": "^2",
    "mermaid": "^11",
    "medium-zoom": "^1"
  },
  "devDependencies": {
    "@types/katex": "^0.16"
  }
}
```

### 5.3 P2 建议新增依赖

```json
{
  "dependencies": {
    "@tanstack/vue-virtual": "^3"
  }
}
```

依赖原则：

1. 每个依赖必须有明确使用点。
2. Mermaid、KaTeX、Shiki 主题资源必须按需加载。
3. 不引入 `marked`。
4. 不引入运行模型输出代码的沙箱或解释器。

---

## 6. 核心模块规格

### 6.1 MarkdownRenderer.vue

职责：

1. 接收 Markdown 原文。
2. 使用 `useMarkdownIt()` 单例解析。
3. 将普通 Markdown 渲染成安全结构。
4. 将 fence token 路由到 Vue 组件。
5. 暴露 `MarkdownContext`，让子组件读取 `streaming / citations / theme`。

Props：

```ts
interface Citation {
  id: string
  index: number
  title: string
  excerpt?: string
  url?: string
}

interface MarkdownRendererProps {
  content: string
  messageId?: string
  streaming?: boolean
  enableMath?: boolean
  enableMermaid?: boolean
  enableRawHtml?: boolean
  citations?: Citation[]
  customRenderers?: Record<string, Component>
}
```

本地化要求：

1. 默认 `enableRawHtml = false`。
2. AI 教练正式回复、思考摘要都走同一渲染器。
3. `customer_reply` 模式下，视觉上应更适合复制给客户：段落清晰、列表间距克制，不展示内部来源调试信息。
4. `coach_brief / handoff_note` 模式下，允许展示复核提示、来源角标和内部说明。
5. 流式中使用安全闭合后的内容；`done` 后用真实内容做最终渲染。

实现注意：

1. 不使用 `querySelector` 找占位符再替换组件。
2. fence token 通过解析阶段生成 vnode 描述或结构化 blocks，再用 Vue 渲染。
3. HTML 净化只在 `enableRawHtml = true` 时启用，但 link/img 安全规则始终启用。

### 6.2 useMarkdownIt.ts

职责：

1. 全局单例。
2. 集中注册插件。
3. 统一覆盖链接、图片、表格、代码块 token 规则。

建议配置：

```ts
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
  typographer: false,
})
```

本地化要求：

1. 中文业务场景关闭 `typographer`，避免标点被替换。
2. 链接统一加 `target="_blank"` 与 `rel="noopener noreferrer"`。
3. 图片默认 `loading="lazy"`，并经过域名白名单判断。
4. 任务列表支持教练待办场景。

### 6.3 chunkBuffer.ts

职责：

1. 承接当前 `useAiCoach.ts` 的 SSE chunk。
2. 维护真实内容 `content` 与安全渲染内容 `renderedContent`。
3. 处理半截 Markdown。

接口：

```ts
export function safeCloseMarkdown(input: string): string

export function createChunkBuffer() {
  const content = ref('')
  const renderedContent = ref('')
  function append(chunk: string): void
  function finish(): void
  function reset(): void
  return { content, renderedContent, append, finish, reset }
}
```

P0 安全闭合规则：

1. 未闭合代码块：临时补 ` ``` `。
2. 未闭合行内代码：临时补反引号。
3. 未闭合粗体或斜体：临时补闭合符。
4. 未闭合链接：暂时不渲染该行末尾。

本地化接入点：

1. `assistantMessage.content` 保留真实内容。
2. 新增 `assistantMessage.renderedContent` 或在组件内按 `streaming` 计算。
3. `thinkingContent` 同样可使用安全闭合，但不启用 Mermaid 渲染。

### 6.4 CodeBlock.vue

功能：

1. Shiki 高亮。
2. 顶部条显示语言。
3. 复制按钮。
4. 超过 30 行默认折叠。
5. 支持行号。
6. 支持深浅色主题。

本地化要求：

1. 顶部条视觉应贴合当前 Element Plus 管理台，不做过重的终端风格。
2. 复制成功使用 `ElMessage.success('已复制代码')`。
3. 对未知语言降级为纯文本，不阻塞整条消息。
4. 大于 100 行的代码块默认只渲染前 30 行，展开时再完整高亮，避免长回答卡顿。

### 6.5 ThinkingPanel.vue

当前 AI 教练助手已有“思考过程”区域。优化后应拆成独立组件。

职责：

1. 展示 thinking stream。
2. 流式期间展示 loading 骨架和打字状态。
3. done 后默认折叠，保留“查看思考摘要”入口。
4. answer done 时不要立刻清空思考内容；如果 thinking 为空，可收起；如果已有内容，应保留到用户关闭或新问题开始。

注意：

1. 这里展示的是“可见思考摘要”，不是不可泄露的完整 chain-of-thought。
2. 文案应使用“思考摘要”或“分析过程摘要”，避免让用户误解为完整内部推理。

### 6.6 CitationInline.vue

AI 教练未来会越来越依赖上下文快照、健康摘要、安全档案、历史会话。因此引用能力应提前设计。

支持格式：

1. `[^1]`
2. `[ref:health_summary_14d]`
3. `[source:safety_profile]`

渲染规则：

1. 角标可点击。
2. hover 展示来源标题和摘要。
3. 点击后打开 AI 抽屉右侧“已加载参考信息”侧栏，并定位到对应来源。
4. 没有匹配来源时，角标降级为普通文本，不报错。

### 6.7 自定义 Fence Renderer

这是 AI 教练助手最重要的扩展点。

约定：

```vue
<MarkdownRenderer
  :content="msg.content"
  :custom-renderers="{
    'coach-action': CoachActionBlock,
    'safety-risk': SafetyRiskBlock,
    'glucose-summary': GlucoseSummaryBlock,
    'meal-review': MealReviewBlock
  }"
/>
```

自定义组件统一接收：

```ts
interface CustomFenceProps {
  code: string
  meta?: string
  streaming?: boolean
  messageId?: string
}
```

首批业务 fence 候选：

1. `coach-action`：下一步跟进动作，渲染为内部待办清单。
2. `safety-risk`：医疗复核、过敏、运动禁忌风险。
3. `glucose-summary`：血糖趋势摘要，先用表格，后续可接图表。
4. `customer-reply`：客户话术卡，可一键复制。

强规则：

1. fence 内容只允许 JSON 或 Markdown 文本。
2. JSON 解析失败必须降级为普通代码块。
3. 不执行 fence 内任何 JS。
4. 自定义业务组件的 official 数据来源仍以后端返回结构化字段为准，模型输出的 fence 只能是 candidate 展示。

---

## 7. 安全规范

### 7.1 默认策略

1. 默认禁用 raw HTML。
2. 默认不渲染 `<script>`、`style`、iframe、事件属性。
3. 默认不执行任何模型输出。
4. 默认不信任图片 URL。
5. 外链统一 `target="_blank" rel="noopener noreferrer"`。

### 7.2 DOMPurify 白名单

只有 `enableRawHtml = true` 时才启用白名单：

```ts
const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'blockquote',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'table', 'thead',
  'tbody', 'tr', 'th', 'td', 'a', 'img', 'hr'
]

const ALLOWED_ATTR = [
  'href', 'src', 'alt', 'title', 'class', 'target', 'rel'
]
```

### 7.3 图片白名单

P0 只允许：

1. 公司 CDN：`cdn.mengfugui.com`
2. 后端已签名的素材访问 URL
3. data URL 禁止

不在白名单内的图片渲染为链接，不直接加载。

### 7.4 测试用例

必须覆盖：

1. `<script>alert(1)</script>` 不执行。
2. `<img src=x onerror=alert(1)>` 不执行。
3. `[x](javascript:alert(1))` 不生成可点击危险链接。
4. 未闭合代码块流式渲染不破版。
5. 自定义 fence JSON 解析失败时降级。

---

## 8. 性能设计

### 8.1 渲染缓存

完成态消息可以按 `messageId + contentHash + theme` 缓存解析结果。

缓存规则：

1. streaming 中不缓存最终 HTML，只缓存安全闭合后的轻量结果。
2. done 后写入缓存。
3. 内容变更或主题切换时失效。

### 8.2 懒加载

1. Shiki：首次遇到代码块时初始化。
2. Mermaid：首次遇到 `mermaid` fence 且非 streaming 时动态 import。
3. KaTeX：首次遇到公式时加载 CSS 与渲染器。
4. medium-zoom：首次点击图片或图片进入视口后加载。

### 8.3 虚拟滚动

当前 AI 教练助手是客户级会话，短期未必每次超过 200 条。虚拟滚动放到 P2，触发条件：

1. 单次会话消息数 > 80。
2. 历史恢复后滚动明显卡顿。
3. MarkdownRenderer 完成态缓存仍不能解决滚动性能。

### 8.4 流式节流

1. `appendChunk` 不直接触发完整解析。
2. 使用 `requestAnimationFrame` 合并渲染。
3. 最多每 16ms 刷新一次。
4. 后端 chunk 到达很密时，前端只渲染最后一次累积结果。

---

## 9. 分阶段实施计划

### P0：把渲染底座立起来

目标：先解决 AI 教练助手当前“手写 Markdown + 超大组件 + 流式半截破版”的核心问题。

任务：

1. 新增 `components/markdown/MarkdownRenderer.vue`。
2. 新增 `composables/useMarkdownIt.ts`。
3. 新增 `components/markdown/CodeBlock.vue`。
4. 新增 `lib/streaming/chunkBuffer.ts`。
5. 新增 `styles/markdown.css`。
6. 从 `AiCoachPanel.vue` 拆出：
   - `AiCoachMessageList.vue`
   - `AiCoachAssistantMessage.vue`
   - `AiCoachUserMessage.vue`
   - `AiCoachThinkingPanel.vue`
7. AI 回复与思考摘要改走 `MarkdownRenderer`。
8. 保留当前 `loadingStage` 骨架，不改变后端协议。

P0 验收：

1. 普通 Markdown、标题、列表、引用、表格可正常显示。
2. 代码块有语言标签、高亮、复制按钮。
3. 未闭合代码块流式输出不破版。
4. `<script>alert(1)</script>` 不执行。
5. `AiCoachPanel.vue` 行数降到 600 行以内。
6. `vue-tsc --noEmit` 与 `npm run build` 通过。
7. 后端与前端启动验证通过。

### P1：补齐专业内容能力

目标：让 AI 教练助手能渲染数据说明、公式、流程图、图片。

任务：

1. `MathBlock.vue` + KaTeX。
2. `MermaidBlock.vue` 懒加载。
3. `ImageBlock.vue` 懒加载 + 白名单。
4. `TableBlock.vue` 横向滚动 + 表头固定候选。
5. 深浅色主题变量统一。
6. 建立 `/playground/markdown-renderer` 或内部 demo 视图。

P1 验收：

1. 行内公式和块级公式正确渲染。
2. Mermaid 成功渲染，失败时显示原始代码和错误提示。
3. 表格横向滚动不撑破抽屉。
4. 图片懒加载，不在白名单内降级为链接。
5. 深浅色切换无明显闪烁。

### P2：业务增强和长会话治理

目标：把渲染层变成 AI 教练助手的正式扩展平台。

任务：

1. `customRenderers` 机制。
2. `CitationInline` + 来源侧栏联动。
3. 至少实现一个业务 fence：`safety-risk` 或 `customer-reply`。
4. 长会话虚拟滚动。
5. 完成态 Markdown 缓存。
6. 渲染性能统计：首帧、流式刷新次数、单条消息解析耗时。

P2 验收：

1. 自定义 fence 全流程可跑通。
2. 引用角标能定位到“已加载参考信息”。
3. 200 条历史消息滚动流畅。
4. 完成态消息重复打开不重复解析。

---

## 10. 与现有 AI 教练能力的衔接

### 10.1 与双流式体验衔接

当前 `useAiCoach.ts` 已分开接收 answer 与 thinking。优化后：

1. answer 使用 `MarkdownRenderer`，启用代码、表格、引用。
2. thinking 使用同一渲染器，但默认关闭 Mermaid、图片和业务 fence。
3. thinking 流式期间只展示轻量 Markdown，不做重型异步渲染。
4. answer done 后，如果 thinking 已有内容，保留折叠入口；如果 thinking 为空，则收起。

### 10.2 与安全门禁衔接

当前 assistant message 已有：

1. `safetyNotes`
2. `safetyResult`
3. `requiresMedicalReview`

渲染层不应把模型输出中的 `safety-risk` fence 当成正式门禁。正式安全提示仍以后端结构化字段为 official。模型输出 fence 只能作为 candidate 辅助展示。

### 10.3 与上下文治理衔接

未来 `CitationInline` 的来源数据应来自后端返回的上下文快照或“已加载参考信息”侧栏。不要让模型自己声明的来源直接成为 official 来源。

建议 Citation 数据结构：

```ts
interface AiCoachCitation {
  id: string
  index: number
  sourceType: 'health_summary' | 'safety_profile' | 'profile_note' | 'history_session' | 'crm_field'
  title: string
  excerpt?: string
  snapshotHash?: string
}
```

---

## 11. 验收标准

### 11.1 用户可感知验收

1. AI 回复里的代码块接近 VS Code 观感，有语言标签和复制按钮。
2. 长回答里的标题、列表、引用、表格层级清楚。
3. 流式输出时不出现半截代码块导致整屏错位。
4. 思考摘要可以折叠，不挤占正式回复。
5. 表格不会撑破 AI 抽屉。
6. 复制客户话术时不夹带内部复核说明。

### 11.2 工程验收

1. `AiCoachPanel.vue` 不再继续承担 Markdown 渲染职责。
2. 新增 Markdown 能力集中在 `components/markdown`、`composables/useMarkdownIt.ts`、`lib/markdown`。
3. `useMarkdownIt()` 是单例。
4. raw HTML 默认禁用。
5. Shiki、Mermaid、KaTeX 懒加载。
6. 新增依赖有明确使用点。
7. TypeScript strict 无 `any` 扩散，必要 `unknown` 先收窄。

### 11.3 安全验收

1. XSS 用例不执行。
2. dangerous URL 不可点击。
3. 非白名单图片不直接加载。
4. 自定义 fence 不执行脚本。
5. DOMPurify 只在允许 raw HTML 时启用，但安全链接规则始终启用。

---

## 12. 推荐开发顺序

第一轮不要并行开太多线，建议 3 条线以内：

1. 渲染底座线：
   建 `MarkdownRenderer / useMarkdownIt / markdown.css / sanitize`。

2. AI 教练接入线：
   拆 `AiCoachPanel.vue` 消息组件，把 `v-html + renderMarkdown` 替换为 `MarkdownRenderer`。

3. 流式稳定线：
   建 `chunkBuffer`，改造 `useAiCoach.ts` 的 content 渲染态，补半截 Markdown 测试。

收口顺序：

1. 先让普通 Markdown 和 AI 教练当前功能不回归。
2. 再接 Shiki 代码块。
3. 再做安全用例。
4. 最后做启动验证和截图验收。

---

## 13. 当前阶段判断

当前阶段是：

> candidate design 已形成，尚未进入代码实现。

已经能做什么：

1. AI 教练助手能完成客户级双流式问答。
2. 前端已经有 loading stage、思考摘要和正式回复展示。
3. 当前轻量 Markdown 对纯文本、换行、粗体、斜体可用。

半能做什么：

1. 能展示简单 Markdown，但不能高质量展示代码、表格、引用、图表。
2. 能通过手写 escape 降低 XSS 风险，但还不是可扩展的安全渲染体系。
3. 能显示思考摘要，但还没有与正式 Markdown 渲染层统一。

还不能做什么：

1. 不能把 Mermaid、公式、RAG 引用写成已完成。
2. 不能把自定义 fence 作为正式业务组件机制。
3. 不能说长会话滚动已经治理完成。
4. 不能说 Tailwind Typography 已接入。

当前 blocker：

1. `AiCoachPanel.vue` 过大，必须先拆组件再继续加渲染能力。
2. 当前项目未接入渲染依赖，新增依赖需要一次完整构建验证。
3. 安全渲染边界必须先定住，否则后续 raw HTML、图片、业务 fence 会带来风险。

最值得继续推进的线：

1. P0 渲染底座线。
2. AI 教练消息组件拆分线。
3. 流式 Markdown 稳定线。

