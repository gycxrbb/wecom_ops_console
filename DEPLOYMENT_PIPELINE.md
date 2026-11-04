# 自动部署流水线

## 日常使用

1. 把改动提交并推送到 `master`。
2. 打开 [GitHub Actions — Build and deploy](https://github.com/gycxrbb/wecom_ops_console/actions/workflows/deploy.yml)。
3. 自动执行：GitHub 后端/部署回归与前端类型检查 → 小体积 Git 源码包 → 测试机干净构建一次 → 隔离启动烟测 → 测试环境部署与健康检查。
4. 测试成功后，生产阶段显示等待审批。确认测试环境符合预期，再点击 **Review deployments → production → Approve and deploy**。
5. 生产通过测试站点现有 HTTPS 静态入口获取同一次运行的镜像产物，核对归档 SHA256 和镜像 ID，不重新构建。失败时查看运行结果；服务器详细日志不上传到公开 Actions 日志。

生产审批人：仓库所有者 `gycxrbb`。允许该账号批准自己触发的发布，避免单人维护仓库无法审批；不会由脚本自动批准。
GitHub 小描述文件保留 7 天；测试机镜像归档仅保留最近 2 份且不超过 7 天，以先到者为准。请审批最新通过测试的运行；过期候选需重新构建。过期运行若已被较新生产版本超越，会被禁止反向覆盖。

## 环境

| GitHub Environment | 服务器 | 项目目录 | 策略 |
| --- | --- | --- | --- |
| test | 120.48.156.119:22 | /www/wwwroot/wecom-ops-console | master 验证通过后自动部署 |
| production | 39.106.212.142:22 | /home/xr/wecom-ops-console | 测试成功且人工批准后部署 |

每个环境有独立 `SSH_PRIVATE_KEY` 和 `SSH_KNOWN_HOSTS` Secrets，及 `DEPLOY_HOST` 变量。密钥不进入 Git、镜像或日志。
服务器 CI 公钥通过 forced command 限制为固定环境的发布接收器，禁止交互终端、端口转发和任意 SSH 命令。
更换主机密钥时，应由管理员核对指纹后更新对应环境的 `SSH_KNOWN_HOSTS`；不要关闭主机校验。

## 发布约束

- GitHub 托管 runner 运行回归和类型检查，只跨境传输小源码包；测试机构建 linux/amd64 镜像，生产只加载镜像，不安装依赖或构建前端。首轮实测海外大镜像直传/HTTPS拉取都过慢，已弃用。
- 发布包绑定完整 Git SHA、镜像 ID、镜像 revision 标签和文件 SHA256。测试运行的镜像直接打包，生产获取同一份产物；GitHub 仅保存小源码包和描述文件。
- PR 运行测试与构建，不获得部署环境密钥、不进入发布阶段；环境仅允许 master 分支。
- GitHub 每个环境有并发门禁；服务器另有部署锁。只更新应用容器，不重启 Qdrant、数据库或其他项目。
- 服务器保留 `.env`、上传文件、证书、数据库等运行数据。运行时 RSA 私钥缓存禁止打入镜像。
- 生产可用内存不足 256 MiB、负载明显过高或磁盘余量不足时，在切换前停止；测试构建需要至少 1 GiB 可用内存和约 3.5 GiB 磁盘余量，构建命令限制1536 MiB内存并请求1664 MiB总内存与交换空间；当前测试机MemoryLimit=true、SwapLimit=false，实际保证内存上限，swap请求会被内核忽略并记录警告，不能当作已生效的swap限制。
- 健康验收同时检查 Docker healthy、API 的 status=ok/db=true，以及前端首页 HTTP 200。
- 健康失败时恢复上一应用镜像与 Git 提交。**不会自动回滚数据库内容**；涉及数据库结构变更，应先确认备份和前后版本兼容性。

测试构建上下文来自精确提交的 `git archive`，不复制服务器工作区、真实 .env 或运行数据；发布前另检查镜像内无运行时 RSA 缓存。归档位于原站点 `uploads/pipeline-releases/<SHA>-<随机值>/release.tar`，只含公开仓库干净构建产物。固定 HTTPS 来源、不接受重定向，SHA256通过受限SSH独立传递。仅清理该目录内本流水线管理的过期候选，不触碰用户素材。

镜像加载前保留旧镜像，成功后继续保留当前和上一发布标签。只清理本应用的旧 release 标签，不做全局 docker prune。
首次发布前的手工备份标签也会保留；需要释放空间时应单独核对，不能盲目删除其他项目镜像。

## 运维入口

- 发布接收器：`/usr/local/lib/wecom-deploy/receive.py`。
- 部署脚本：`/usr/local/lib/wecom-deploy/deploy.sh`；测试构建：同目录 `build_test.sh`；容器探针：`probe.py`；固定分发站点配置：`config.json`。
- 发布状态：`/var/lib/wecom-deploy/<环境>/current.json`，含当前/上一提交和镜像 ID。
- 私有日志：同目录 `deploy-<完整提交>.log`，仅 root 可访问。
- 回退镜像：`wecom-ops-console-rollback:previous`。

首次基础镜像缓存缺失时，`ensure_bases.py` 从国内代理按 Docker Hub 官方 manifest 摘要拉取，并核对官方 config ID；只预热缺失标签，不改 Docker 全局镜像源、不替换已有标签。批准摘要放在服务器 `config.json` 的 `base_images` 中，升级 Node/Python 基础版本或增加新 FROM 时，应先由管理员核验并更新对应摘要。

更新接收协议/服务端脚本后，需要通过管理员 SSH 同步 `/usr/local/lib/wecom-deploy/`；CI 受限密钥不能自行替换这套管理员入口。
原测试环境 `*/10 * * * * .../deploy.sh` 定时任务在切换时备份并停用，避免与流水线竞争；原脚本保留作为人工应急参考。

源码包使用 `scripts/deploy/package_release.py` 中的初始共同基线提交，以 Git bundle 同步精确提交，不依赖服务器访问 GitHub。重写历史或迁移仓库时需先检查基线兼容性。

## 验证与恢复

本地可执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_user_default_permissions.py tests/test_deployment_release.py -q
```

Linux 上还会运行实际 shell 事务测试，使用隔离临时 Git 仓库和假 Docker 验证成功切换、健康失败回退及数据库探测失败回退。它们不会操作真实容器。
真实流水线在测试机临时容器内做启动烟测：空白隔离 SQLite、启用 CRM/生图表注册，不加载服务器 .env、不挂载业务数据、不连接真实 CRM 或模型；通过后才切换测试应用。
如连接中断或发布报错，先检查服务器 current.json、Git SHA、实际容器镜像及健康，再决定重试或回退；不要仅凭工作区已更新判断上线成功。

GitHub 官方参考：[环境审批与 Secrets](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)、[环境管理 API](https://docs.github.com/en/rest/deployments/environments)。
