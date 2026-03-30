const state = {
  currentUser: window.__BOOTSTRAP__?.currentUser || null,
  dashboard: {},
  messageTrend: [],
  failureDistribution: [],
  groups: [],
  templates: [],
  assets: [],
  schedules: [],
  logs: [],
  approvals: [],
  users: [],
  selectedTemplateId: null,
};

const views = {
  dashboard: { title: '仪表盘', render: renderDashboard },
  send: { title: '发送中心', render: renderSendCenter },
  groups: { title: '群管理', render: renderGroups },
  templates: { title: '模板中心', render: renderTemplates },
  assets: { title: '素材库', render: renderAssets },
  schedules: { title: '定时任务', render: renderSchedules },
  logs: { title: '发送记录', render: renderLogs },
  approvals: { title: '审批中心', render: renderApprovals },
  users: { title: '用户管理', render: renderUsers },
};

const api = {
  get: (url) => fetch(url, { credentials: 'same-origin' }).then(handleResponse),
  post: (url, body) => fetch(url, { method: 'POST', headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' }, body: body instanceof FormData ? body : JSON.stringify(body), credentials: 'same-origin' }).then(handleResponse),
  del: (url) => fetch(url, { method: 'DELETE', credentials: 'same-origin' }).then(handleResponse),
};

async function handleResponse(resp) {
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.error_message || data.message || JSON.stringify(data)); 
  }
  if (data.code !== undefined) {
    if (data.code !== 0) throw new Error(data.message || 'Error');
    return data.data;
  }
  return data;
}

function toast(msg, isError = false) {
  alert((isError ? '错误：' : '提示：') + msg);
}

function escapeHtml(str) {
  return String(str || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function qs(id) { return document.getElementById(id); }
function tag(status) {
  if (status === 'completed' || status === 'approved' || status === 'scheduled') return `<span class="pill success">${status}</span>`;
  if (status === 'pending_approval' || status === 'draft') return `<span class="pill pending">${status}</span>`;
  return `<span class="pill error">${status}</span>`;
}

async function loadAll() {
  const bootstrap = await api.get('/api/v1/bootstrap');
  state.dashboard = bootstrap.dashboard;
  state.currentUser = bootstrap.current_user;
  state.groups = await api.get('/api/v1/groups');
  state.templates = await api.get('/api/v1/templates');
  state.assets = await api.get('/api/v1/assets');
  state.schedules = await api.get('/api/v1/schedules');
  state.logs = await api.get('/api/v1/logs');
  state.approvals = (await api.get('/api/v1/approvals')).list;
  
  api.get('/api/v1/dashboard/message-trend').then(res => state.messageTrend = res.trend).catch(console.error);
  api.get('/api/v1/dashboard/failure-distribution').then(res => state.failureDistribution = res.distribution).catch(console.error);

  if (state.currentUser.role === 'admin') {
    state.users = await api.get('/api/v1/users');
  }
}

function mountView(viewName) {
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.toggle('active', btn.dataset.view === viewName));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === viewName));
  qs('view-title').textContent = views[viewName].title;
  views[viewName].render(qs(viewName));
}

function renderDashboard(root) {
  const recentLogs = state.logs.slice(0, 8);
  const pendingCount = (state.approvals || []).filter(a => a.status === 'pending').length;
  root.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi"><div class="muted">群聊数</div><div class="num">${state.dashboard.group_count || 0}</div></div>
      <div class="kpi"><div class="muted">模板数</div><div class="num">${state.dashboard.template_count || 0}</div></div>
      <div class="kpi"><div class="muted">任务数</div><div class="num">${state.dashboard.schedule_count || 0}</div></div>
      <div class="kpi"><div class="muted">发送记录</div><div class="num">${state.dashboard.log_count || 0}</div></div>
      <div class="kpi"><div class="muted">待审批</div><div class="num" style="color:var(--primary)">${pendingCount}</div></div>
      <div class="kpi"><div class="muted">成功率</div><div class="num">${state.dashboard.success_rate || 0}%</div></div>
    </div>
    <div class="grid grid-2" style="margin-top:16px;">
      <div class="card">
        <div class="panel-title"><h3>最近发送记录</h3></div>
        ${recentLogs.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>时间</th><th>群</th><th>类型</th><th>结果</th></tr></thead><tbody>${recentLogs.map(log => `<tr><td>${log.created_at.replace('T', ' ').slice(0, 19)}</td><td>${escapeHtml(log.group_name)}</td><td>${log.msg_type}</td><td>${log.success ? '<span class="pill success">成功</span>' : '<span class="pill error">失败</span>'}</td></tr>`).join('')}</tbody></table></div>` : `<div class="empty">暂无记录</div>`}
      </div>
      <div class="card">
        <h3>项目提示</h3>
        <ul>
          <li>先在“群管理”替换测试群和正式群的 webhook。</li>
          <li>先用“发送中心 -> 测试群发送”验证模板。</li>
          <li>需要审批的任务，管理员在“定时任务”里批准后才会跑。</li>
          <li>单机器人内置 20 条/分钟保护。</li>
        </ul>
      </div>
    </div>
  `;
}

function groupOptions(selected = []) {
  return state.groups.filter(g => g.is_enabled).map(g => `<label><input type="checkbox" name="group_ids" value="${g.id}" ${selected.includes(g.id) ? 'checked' : ''}> ${escapeHtml(g.name)} ${g.is_test_group ? '(测试群)' : ''}</label>`).join('<br>');
}

function templateOptions(selectedId = '') {
  return `<option value="">不使用模板，手动编辑</option>` + state.templates.map(t => `<option value="${t.id}" ${String(selectedId) === String(t.id) ? 'selected' : ''}>[${escapeHtml(t.category)}] ${escapeHtml(t.name)} (${t.msg_type})</option>`).join('');
}

function assetOptions(type, selectedId = '') {
  return `<option value="">请选择</option>` + state.assets.filter(a => a.asset_type === type).map(a => `<option value="${a.id}" ${String(selectedId) === String(a.id) ? 'selected' : ''}>${escapeHtml(a.name)} (${escapeHtml(a.file_name)})</option>`).join('');
}

function exampleContentForType(type) {
  if (type === 'text') return JSON.stringify({ content: '大家好，今晚 20:00 请按时提交总结。', mentioned_list: [], mentioned_mobile_list: [] }, null, 2);
  if (type === 'markdown') return JSON.stringify({ content: '### 今日主题\n- 先执行\n- 再反馈\n- 最后总结' }, null, 2);
  if (type === 'news') return JSON.stringify({ articles: [{ title: '今日课程', description: '点击查看图文说明', url: 'https://example.com', picurl: 'https://picsum.photos/640/360' }] }, null, 2);
  if (type === 'image') return JSON.stringify({ asset_id: '' }, null, 2);
  if (type === 'file') return JSON.stringify({ asset_id: '' }, null, 2);
  if (type === 'template_card') return JSON.stringify({ template_card: { card_type: 'text_notice', main_title: { title: '提醒', desc: '今晚 20:00 总结' }, sub_title_text: '请按时提交反馈', card_action: { type: 1, url: 'https://example.com' } } }, null, 2);
  return JSON.stringify({ msgtype: 'markdown', markdown: { content: '自定义原始 JSON' } }, null, 2);
}

function renderSendCenter(root) {
  const defaultTemplate = state.templates[0];
  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="panel-title"><h3>消息编排</h3></div>
        <div class="field-inline">
          <label class="field"><span>模板</span><select id="send-template-id">${templateOptions()}</select></label>
          <label class="field"><span>消息类型</span>
            <select id="send-msg-type">
              <option value="text">text</option>
              <option value="markdown" selected>markdown</option>
              <option value="news">news</option>
              <option value="image">image</option>
              <option value="file">file</option>
              <option value="template_card">template_card(JSON)</option>
              <option value="raw_json">raw_json</option>
            </select>
          </label>
        </div>
        <label class="field"><span>目标群</span><div class="card" style="border-radius:12px;padding:10px;">${groupOptions()}</div></label>
        <label class="field"><span>模板变量 JSON</span><textarea id="send-variables-json" rows="8">${JSON.stringify(defaultTemplate?.variables_json || { topic: '211餐盘 + 餐后走' }, null, 2)}</textarea></label>
        <label class="field"><span>消息内容 JSON</span><textarea id="send-content-json" rows="18">${JSON.stringify(defaultTemplate?.content_json || { content: '### 今日提醒' }, null, 2)}</textarea></label>
        <div class="hint">image/file 类型请在 JSON 里填 <code>{"asset_id": 资产ID}</code>，也可以从模板中心复制示例。</div>
        <div class="form-actions" style="margin-top:12px;">
          <button class="btn" id="preview-btn">预览 payload</button>
          <button class="btn success" id="send-now-btn">立即发送</button>
          <button class="btn warning" id="send-test-btn">发送到测试群</button>
        </div>
      </div>
      <div class="card preview-box">
        <div class="panel-title"><h3>预览</h3></div>
        <div id="preview-result" class="code-block">点击“预览 payload”后，这里会展示渲染结果。</div>
        <div style="height:12px"></div>
        <div class="card" style="background:#f8fafc;">
          <h3>快速创建定时任务</h3>
          <div class="field-inline">
            <label class="field"><span>任务标题</span><input id="schedule-title" placeholder="例如：周一 20:00 晚安总结"></label>
            <label class="field"><span>时区</span><input id="schedule-timezone" value="Asia/Shanghai"></label>
          </div>
          <div class="field-inline">
            <label class="field"><span>计划类型</span>
              <select id="schedule-type">
                <option value="once">一次性</option>
                <option value="cron">周期 cron</option>
              </select>
            </label>
            <label class="field"><span>需要审批</span>
              <select id="schedule-approval"><option value="false">否</option><option value="true">是</option></select>
            </label>
          </div>
          <div class="field-inline">
            <label class="field"><span>执行时间（一次性）</span><input id="schedule-run-at" type="datetime-local"></label>
            <label class="field"><span>cron 表达式（5 位）</span><input id="schedule-cron" placeholder="0 20 * * 1-5"></label>
          </div>
          <div class="field-inline">
            <label class="field"><span>跳过日期（逗号分隔）</span><input id="schedule-skip-dates" placeholder="2026-04-05,2026-05-01"></label>
            <label class="field"><span>跳过周末</span><select id="schedule-skip-weekends"><option value="false">否</option><option value="true">是</option></select></label>
          </div>
          <div class="form-actions">
            <button class="btn primary" id="save-schedule-btn">保存为定时任务</button>
          </div>
        </div>
      </div>
    </div>
  `;
  qs('send-template-id').addEventListener('change', applyTemplateToSend);
  qs('send-msg-type').addEventListener('change', () => {
    if (!qs('send-template-id').value) {
      qs('send-content-json').value = exampleContentForType(qs('send-msg-type').value);
    }
  });
  qs('preview-btn').addEventListener('click', previewSendPayload);
  qs('send-now-btn').addEventListener('click', () => sendNow(false));
  qs('send-test-btn').addEventListener('click', () => sendNow(true));
  qs('save-schedule-btn').addEventListener('click', saveScheduleFromSend);
}

function renderGroups(root) {
  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="panel-title"><h3>新增 / 编辑群聊</h3></div>
        <input type="hidden" id="group-id">
        <label class="field"><span>群名称</span><input id="group-name"></label>
        <label class="field"><span>别名</span><input id="group-alias"></label>
        <label class="field"><span>描述</span><textarea id="group-description" rows="3"></textarea></label>
        <label class="field"><span>标签（逗号分隔）</span><input id="group-tags"></label>
        <label class="field"><span>Webhook</span><input id="group-webhook" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."></label>
        <div class="field-inline">
          <label class="field"><span>启用</span><select id="group-enabled"><option value="true">是</option><option value="false">否</option></select></label>
          <label class="field"><span>是否测试群</span><select id="group-test"><option value="false">否</option><option value="true">是</option></select></label>
        </div>
        <div class="form-actions"><button class="btn primary" id="save-group-btn">保存群聊</button></div>
      </div>
      <div class="card">
        <div class="panel-title"><h3>已配置群聊</h3></div>
        <div class="table-wrap">
          <table class="table"><thead><tr><th>名称</th><th>别名</th><th>标签</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            ${state.groups.map(g => `<tr>
              <td>${escapeHtml(g.name)} ${g.is_test_group ? '<span class="pill pending">测试群</span>' : ''}</td>
              <td>${escapeHtml(g.alias || '-')}</td>
              <td>${(g.tags || []).map(t => `<span class="badge">${escapeHtml(t)}</span>`).join(' ')}</td>
              <td>${g.is_enabled ? '<span class="pill success">启用</span>' : '<span class="pill error">停用</span>'}</td>
              <td><button class="btn" onclick='editGroup(${JSON.stringify(g).replaceAll("'", '&apos;')})'>编辑</button> <button class="btn danger" onclick='removeGroup(${g.id})'>删除</button></td>
            </tr>`).join('')}
          </tbody></table>
        </div>
      </div>
    </div>
  `;
  qs('save-group-btn').onclick = saveGroup;
}

function renderTemplates(root) {
  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="panel-title"><h3>新增 / 编辑模板</h3></div>
        <input type="hidden" id="template-id">
        <div class="field-inline">
          <label class="field"><span>模板名称</span><input id="template-name"></label>
          <label class="field"><span>分类</span><input id="template-category" value="general"></label>
        </div>
        <div class="field-inline">
          <label class="field"><span>消息类型</span><select id="template-msg-type"><option value="text">text</option><option value="markdown">markdown</option><option value="news">news</option><option value="image">image</option><option value="file">file</option><option value="template_card">template_card</option><option value="raw_json">raw_json</option></select></label>
          <label class="field"><span>描述</span><input id="template-description"></label>
        </div>
        <label class="field"><span>内容 JSON</span><textarea id="template-content-json" rows="14">${exampleContentForType('markdown')}</textarea></label>
        <label class="field"><span>变量 JSON</span><textarea id="template-variables-json" rows="8">{}</textarea></label>
        <div class="form-actions"><button class="btn primary" id="save-template-btn">保存模板</button></div>
      </div>
      <div class="card">
        <div class="panel-title"><h3>模板列表</h3></div>
        <div class="table-wrap">
          <table class="table"><thead><tr><th>名称</th><th>类型</th><th>分类</th><th>操作</th></tr></thead><tbody>
            ${state.templates.map(t => `<tr>
              <td>${escapeHtml(t.name)} ${t.is_system ? '<span class="pill pending">系统</span>' : ''}</td>
              <td>${t.msg_type}</td>
              <td>${escapeHtml(t.category)}</td>
              <td><button class="btn" onclick='editTemplate(${JSON.stringify(t).replaceAll("'", '&apos;')})'>编辑</button> <button class="btn" onclick='cloneTemplate(${t.id})'>复制</button> <button class="btn danger" onclick='removeTemplate(${t.id})'>删除</button></td>
            </tr>`).join('')}
          </tbody></table>
        </div>
      </div>
    </div>
  `;
  qs('save-template-btn').onclick = saveTemplate;
  qs('template-msg-type').onchange = () => {
    if (!qs('template-id').value) qs('template-content-json').value = exampleContentForType(qs('template-msg-type').value);
  };
}

function renderAssets(root) {
  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="panel-title"><h3>上传素材</h3></div>
        <label class="field"><span>选择图片或文件</span><input id="asset-file" type="file"></label>
        <div class="form-actions"><button class="btn primary" id="upload-asset-btn">上传</button></div>
      </div>
      <div class="card">
        <div class="panel-title"><h3>素材列表</h3></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>名称</th><th>类型</th><th>文件</th><th>操作</th></tr></thead><tbody>
          ${state.assets.map(a => `<tr><td>${escapeHtml(a.name)}</td><td>${a.asset_type}</td><td>${escapeHtml(a.file_name)}</td><td><a class="btn" href="${a.url}" target="_blank">下载</a> <button class="btn danger" onclick='removeAsset(${a.id})'>删除</button></td></tr>`).join('')}
        </tbody></table></div>
        <div class="hint">image/file 类型消息在 JSON 中引用 <code>asset_id</code> 即可。</div>
      </div>
    </div>
  `;
  qs('upload-asset-btn').onclick = uploadAsset;
}

function renderSchedules(root) {
  root.innerHTML = `
    <div class="card">
      <div class="panel-title"><h3>定时任务</h3></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>标题</th><th>群</th><th>类型</th><th>计划</th><th>状态</th><th>操作</th></tr></thead><tbody>
      ${state.schedules.map(s => {
        const groupNames = (s.group_ids || []).map(id => state.groups.find(g => g.id === id)?.name || `#${id}`).join('、');
        const plan = s.schedule_type === 'once' ? (s.run_at || '-') : (s.cron_expr || '-');
        const ops = [`<button class="btn" onclick="runScheduleNow(${s.id})">立即执行</button>`, `<button class="btn" onclick="cloneSchedule(${s.id})">复制</button>`, `<button class="btn" onclick="toggleSchedule(${s.id})">${s.enabled ? '停用' : '启用'}</button>`, `<button class="btn danger" onclick="removeSchedule(${s.id})">删除</button>`];
        if (state.currentUser.role === 'admin' && s.status === 'pending_approval') ops.unshift(`<button class="btn success" onclick="approveSchedule(${s.id})">批准</button>`);
        return `<tr><td>${escapeHtml(s.title)}</td><td>${escapeHtml(groupNames)}</td><td>${s.msg_type}</td><td>${escapeHtml(plan)}</td><td>${tag(s.status)} ${s.enabled ? '' : '<span class="pill error">disabled</span>'}</td><td>${ops.join(' ')}</td></tr>`;
      }).join('')}
      </tbody></table></div>
    </div>
  `;
}

function renderLogs(root) {
  root.innerHTML = `
    <div class="card">
      <div class="panel-title"><h3>发送记录</h3></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>时间</th><th>群</th><th>类型</th><th>模式</th><th>结果</th><th>详情</th><th>操作</th></tr></thead><tbody>
      ${state.logs.map(log => `<tr>
        <td>${log.created_at.replace('T', ' ').slice(0, 19)}</td>
        <td>${escapeHtml(log.group_name || '')}</td>
        <td>${log.msg_type}</td>
        <td>${log.run_mode}</td>
        <td>${log.success ? '<span class="pill success">成功</span>' : '<span class="pill error">失败</span>'}</td>
        <td><details><summary>查看</summary><div class="code-block">request:
${escapeHtml(JSON.stringify(log.request_json, null, 2))}

response:
${escapeHtml(JSON.stringify(log.response_json, null, 2))}

error:
${escapeHtml(log.error_message || '')}</div></details></td>
        <td><button class="btn" onclick="retryLog(${log.id})">重试</button></td>
      </tr>`).join('')}
      </tbody></table></div>
    </div>
  `;
}

function renderUsers(root) {
  if (state.currentUser.role !== 'admin') {
    root.innerHTML = '<div class="card">无权限</div>';
    return;
  }
  root.innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <div class="panel-title"><h3>新增 / 编辑用户</h3></div>
        <input type="hidden" id="user-id">
        <label class="field"><span>用户名</span><input id="user-username"></label>
        <label class="field"><span>显示名</span><input id="user-display-name"></label>
        <div class="field-inline">
          <label class="field"><span>角色</span><select id="user-role"><option value="coach">coach</option><option value="admin">admin</option></select></label>
          <label class="field"><span>启用</span><select id="user-active"><option value="true">是</option><option value="false">否</option></select></label>
        </div>
        <label class="field"><span>密码（编辑时留空则不改）</span><input id="user-password" type="password"></label>
        <div class="form-actions"><button class="btn primary" id="save-user-btn">保存用户</button></div>
      </div>
      <div class="card">
        <div class="panel-title"><h3>用户列表</h3></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>用户名</th><th>显示名</th><th>角色</th><th>状态</th><th>操作</th></tr></thead><tbody>
        ${state.users.map(u => `<tr><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.display_name)}</td><td>${u.role}</td><td>${u.is_active ? '<span class="pill success">启用</span>' : '<span class="pill error">停用</span>'}</td><td><button class="btn" onclick='editUser(${JSON.stringify(u).replaceAll("'", '&apos;')})'>编辑</button></td></tr>`).join('')}
        </tbody></table></div>
      </div>
    </div>
  `;
  qs('save-user-btn').onclick = saveUser;
}

function getCheckedGroupIds() {
  return [...document.querySelectorAll('input[name="group_ids"]:checked')].map(el => Number(el.value));
}

function safeJson(value, fallback = {}) {
  try { return JSON.parse(value || '{}'); } catch (e) { throw new Error('JSON 格式错误：' + e.message); }
}

function applyTemplateToSend() {
  const id = Number(qs('send-template-id').value || 0);
  const tpl = state.templates.find(t => t.id === id);
  if (!tpl) return;
  qs('send-msg-type').value = tpl.msg_type;
  qs('send-content-json').value = JSON.stringify(tpl.content_json, null, 2);
  qs('send-variables-json').value = JSON.stringify(tpl.variables_json, null, 2);
}

async function previewSendPayload() {
  try {
    const payload = {
      group_ids: getCheckedGroupIds(),
      msg_type: qs('send-msg-type').value,
      content_json: safeJson(qs('send-content-json').value),
      variables_json: safeJson(qs('send-variables-json').value),
    };
    const res = await api.post('/api/v1/preview', payload);
    qs('preview-result').textContent = JSON.stringify(res, null, 2);
  } catch (e) { toast(e.message, true); }
}

async function sendNow(testOnly) {
  try {
    const payload = {
      group_ids: getCheckedGroupIds(),
      msg_type: qs('send-msg-type').value,
      content_json: safeJson(qs('send-content-json').value),
      variables_json: safeJson(qs('send-variables-json').value),
      test_group_only: testOnly,
    };
    const res = await api.post('/api/v1/send', payload);
    toast('发送完成：' + JSON.stringify(res.results));
    await refreshState();
  } catch (e) { toast(e.message, true); }
}

async function saveScheduleFromSend() {
  try {
    const payload = {
      title: qs('schedule-title').value || '未命名任务',
      group_ids: getCheckedGroupIds(),
      template_id: Number(qs('send-template-id').value || 0) || null,
      msg_type: qs('send-msg-type').value,
      content_json: safeJson(qs('send-content-json').value),
      variables_json: safeJson(qs('send-variables-json').value),
      schedule_type: qs('schedule-type').value,
      run_at: qs('schedule-run-at').value || null,
      cron_expr: qs('schedule-cron').value.trim(),
      timezone: qs('schedule-timezone').value || 'Asia/Shanghai',
      enabled: true,
      approval_required: qs('schedule-approval').value === 'true',
      skip_dates: (qs('schedule-skip-dates').value || '').split(',').map(v => v.trim()).filter(Boolean),
      skip_weekends: qs('schedule-skip-weekends').value === 'true',
    };
    await api.post('/api/v1/schedules', payload);
    toast('任务已保存');
    await refreshState('schedules');
  } catch (e) { toast(e.message, true); }
}

function editGroup(g) {
  qs('group-id').value = g.id || '';
  qs('group-name').value = g.name || '';
  qs('group-alias').value = g.alias || '';
  qs('group-description').value = g.description || '';
  qs('group-tags').value = (g.tags || []).join(',');
  qs('group-webhook').value = '';
  qs('group-enabled').value = String(g.is_enabled);
  qs('group-test').value = String(g.is_test_group);
}
window.editGroup = editGroup;

async function saveGroup() {
  try {
    const payload = {
      id: Number(qs('group-id').value || 0) || undefined,
      name: qs('group-name').value,
      alias: qs('group-alias').value,
      description: qs('group-description').value,
      tags: (qs('group-tags').value || '').split(',').map(v => v.trim()).filter(Boolean),
      webhook: qs('group-webhook').value,
      is_enabled: qs('group-enabled').value === 'true',
      is_test_group: qs('group-test').value === 'true',
    };
    await api.post('/api/v1/groups', payload);
    toast('群聊已保存');
    await refreshState('groups');
  } catch (e) { toast(e.message, true); }
}

async function removeGroup(id) {
  if (!confirm('确认删除该群吗？')) return;
  try { await api.del('/api/v1/groups/' + id); await refreshState('groups'); } catch (e) { toast(e.message, true); }
}
window.removeGroup = removeGroup;

function editTemplate(t) {
  qs('template-id').value = t.id || '';
  qs('template-name').value = t.name || '';
  qs('template-category').value = t.category || 'general';
  qs('template-msg-type').value = t.msg_type || 'markdown';
  qs('template-description').value = t.description || '';
  qs('template-content-json').value = JSON.stringify(t.content_json || {}, null, 2);
  qs('template-variables-json').value = JSON.stringify(t.variables_json || {}, null, 2);
}
window.editTemplate = editTemplate;

async function saveTemplate() {
  try {
    const payload = {
      id: Number(qs('template-id').value || 0) || undefined,
      name: qs('template-name').value,
      category: qs('template-category').value,
      msg_type: qs('template-msg-type').value,
      description: qs('template-description').value,
      content_json: safeJson(qs('template-content-json').value),
      variables_json: safeJson(qs('template-variables-json').value),
    };
    await api.post('/api/v1/templates', payload);
    toast('模板已保存');
    await refreshState('templates');
  } catch (e) { toast(e.message, true); }
}

async function cloneTemplate(id) { try { await api.post('/api/v1/templates/' + id + '/clone', {}); await refreshState('templates'); } catch (e) { toast(e.message, true); } }
window.cloneTemplate = cloneTemplate;
async function removeTemplate(id) { if (!confirm('确认删除模板？')) return; try { await api.del('/api/v1/templates/' + id); await refreshState('templates'); } catch (e) { toast(e.message, true); } }
window.removeTemplate = removeTemplate;

async function uploadAsset() {
  const fileInput = qs('asset-file');
  if (!fileInput.files[0]) return toast('请选择文件', true);
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  try { await api.post('/api/v1/assets', formData); toast('上传成功'); await refreshState('assets'); } catch (e) { toast(e.message, true); }
}

async function removeAsset(id) { if (!confirm('确认删除素材？')) return; try { await api.del('/api/v1/assets/' + id); await refreshState('assets'); } catch (e) { toast(e.message, true); } }
window.removeAsset = removeAsset;

async function approveSchedule(id) { try { await api.post('/api/v1/schedules/' + id + '/approve', {}); await refreshState('schedules'); } catch (e) { toast(e.message, true); } }
window.approveSchedule = approveSchedule;
async function runScheduleNow(id) { try { const res = await api.post('/api/v1/schedules/' + id + '/run-now', {}); toast('执行完成：' + JSON.stringify(res.results)); await refreshState('schedules'); } catch (e) { toast(e.message, true); } }
window.runScheduleNow = runScheduleNow;
async function cloneSchedule(id) { try { await api.post('/api/v1/schedules/' + id + '/clone', {}); await refreshState('schedules'); } catch (e) { toast(e.message, true); } }
window.cloneSchedule = cloneSchedule;
async function toggleSchedule(id) { try { await api.post('/api/v1/schedules/' + id + '/toggle', {}); await refreshState('schedules'); } catch (e) { toast(e.message, true); } }
window.toggleSchedule = toggleSchedule;
async function removeSchedule(id) { if (!confirm('确认删除任务？')) return; try { await api.del('/api/v1/schedules/' + id); await refreshState('schedules'); } catch (e) { toast(e.message, true); } }
window.removeSchedule = removeSchedule;

async function retryLog(id) { try { await api.post('/api/v1/logs/' + id + '/retry', {}); toast('已重试'); await refreshState('logs'); } catch (e) { toast(e.message, true); } }
window.retryLog = retryLog;

function editUser(u) {
  qs('user-id').value = u.id || '';
  qs('user-username').value = u.username || '';
  qs('user-display-name').value = u.display_name || '';
  qs('user-role').value = u.role || 'coach';
  qs('user-active').value = String(u.is_active);
  qs('user-password').value = '';
}
window.editUser = editUser;

async function saveUser() {
  try {
    const payload = {
      id: Number(qs('user-id').value || 0) || undefined,
      username: qs('user-username').value,
      display_name: qs('user-display-name').value,
      role: qs('user-role').value,
      is_active: qs('user-active').value === 'true',
      password: qs('user-password').value,
    };
    await api.post('/api/v1/users', payload);
    toast('用户已保存');
    await refreshState('users');
  } catch (e) { toast(e.message, true); }
}

async function refreshState(viewName) {
  await loadAll();
  Object.entries(views).forEach(([name, cfg]) => {
    const el = qs(name);
    if (el) cfg.render(el);
  });
  if (viewName) mountView(viewName);
}

async function init() {
  // 只在主页面初始化（登录页面没有 __BOOTSTRAP__）
  if (!window.__BOOTSTRAP__) return;
  await loadAll();
  Object.entries(views).forEach(([name, cfg]) => {
    const el = qs(name);
    if (el) cfg.render(el);
  });
  document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => mountView(btn.dataset.view)));
  mountView('dashboard');
}

function renderApprovals(root) {
  root.innerHTML = `
    <div class="card">
      <div class="panel-title">
        <h3>审批中心</h3>
        <button class="btn btn-sm" onclick="refreshApprovals()">刷新</button>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>申请人ID</th>
              <th>类型</th>
              <th>目标ID</th>
              <th>理由</th>
              <th>状态</th>
              <th>时间</th>
              <th>备注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${state.approvals.map(a => `
              <tr>
                <td>${a.id}</td>
                <td>${a.applicant_id}</td>
                <td>${escapeHtml(a.target_type)}</td>
                <td>${a.target_id}</td>
                <td>${escapeHtml(a.reason || '-')}</td>
                <td>
                  <span class="pill ${a.status === 'approved' ? 'success' : a.status === 'rejected' ? 'error' : ''}">
                    ${a.status === 'pending' ? '待审批' : a.status === 'approved' ? '已通过' : '已拒绝'}
                  </span>
                </td>
                <td>${(a.created_at || '').replace('T', ' ').slice(0, 19)}</td>
                <td>${escapeHtml(a.comment || '-')}</td>
                <td>
                  ${state.currentUser.role === 'admin' && a.status === 'pending' ? `
                    <button class="btn btn-sm" onclick="handleApprovalAction(${a.id}, 'approved')">通过</button>
                    <button class="btn btn-sm error" onclick="handleApprovalAction(${a.id}, 'rejected')">拒绝</button>
                  ` : '-'}
                </td>
              </tr>
            `).join('')}
            ${state.approvals.length === 0 ? '<tr><td colspan="9" class="empty">暂无审批数据</td></tr>' : ''}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.refreshApprovals = async () => {
  try {
    state.approvals = (await api.get('/api/v1/approvals')).list;
    renderApprovals(qs('approvals'));
  } catch(err) {
    toast(err.message, true);
  }
};

window.handleApprovalAction = async (id, action) => {
  const comment = prompt('请输入审批备注(选填)：', '');
  if (comment === null) return;
  try {
    await api.post(`/api/v1/approvals/${id}/approve`, { action, comment });
    toast('审批成功！');
    await refreshApprovals();
    if (state.schedules) {
        state.schedules = await api.get('/api/v1/schedules');
    }
  } catch (err) {
    toast(err.message, true);
  }
};

window.addEventListener('DOMContentLoaded', init);

