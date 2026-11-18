# 个人配置

推荐通过 `scripts/configure.py` 生成本地 `config.json`，不要直接修改示例来提交 Git。配置快照会复制到每次 run_dir，勿公开运行目录。

| 字段 | 含义与配置方式 |
| --- | --- |
| `vault` | 已有 Obsidian Vault 的绝对路径；写入目标。必须可读写。 |
| `python` | 本技能虚拟环境的 Python 绝对入口，配置器取当前 `sys.executable`；Windows 为 `.venv\Scripts\python.exe`。不要写另一个技能或他人的 Python。 |
| `cache_dir` | 个人运行材料/状态目录，默认仓库下 `.cache`；不要放在公开同步目录。 |
| `material_cache_dirs` | 可选的原始材料目录，默认空；补录时只读检索作品 ID 一致的 bundle.json 与 transcript.json。只加入自己明确授权的路径。 |
| `browser` | `chrome`；无浏览器模式为 JSON `null`。 |
| `browser_profile` | 默认 `null`：从真实系统用户的 Chrome 资料中优先选择有抖音会话的资料，不依赖 zcode 改写的 HOME。也可指定完整 profile 目录（Windows 形如 `C:\Users\<you>\AppData\Local\Google\Chrome\User Data\Default`）。 |
| `browser_cache_dir` | 默认 `null`：与所选 profile 自动匹配（Windows 位于 `...\User Data\<Profile>\Cache\Cache_Data`）；显式自定义资料目录须指定对应 Cache_Data。 |
| `auto_browser_recovery` | 默认 `false`：不自动弹出作品页。仅用户明确允许可见恢复时设置 `true`。当前关闭设置同样约束旧批次。 |
| `prefer_browser_media` | 默认 `false`；为 `true` 时优先浏览器恢复。 |
| `background_detail_first` | 默认 `true`；先后台取严格匹配 ID 的详情。只有显式启用自动开页时才允许可见恢复。 |
| `close_opened_tabs` | 默认 `true`；仅尝试关闭本次打开、严格匹配作品的新增标签。需系统授权。 |
| `browser_recovery_wait_seconds` | 默认 8，0–20 秒。 |
| `browser_media_timeout_seconds` | 默认 40，0–40 秒，共享缓存等待预算。 |
| `prepare_workers` | 默认 2；本地材料并行准备进程数。不要并行运行多个 `prepare-all`。 |
| `prepare_batch` | 默认 10；Agent 流程也显式传 `--limit 10`，不要超过十条。 |
| `asr_backend` | 默认 `auto`：macOS Apple Silicon 使用 `mlx`，其他平台使用 `faster-whisper`。也可显式设为 `mlx` 或 `faster-whisper`；`mlx` 只在 Apple Silicon 可用。 |
| `asr_device` | 默认 `cpu`；仅 faster-whisper 使用，可设 `cuda`（需可用的 CUDA 运行库）或 `auto`。 |
| `asr_model` | 平台默认值不同：macOS 为 `mlx-community/whisper-small-mlx`，Windows 配置器写入 `small`（faster-whisper 模型名）。首次从模型托管方下载，需网络；带 `mlx-community/` 前缀的模型名在 faster-whisper 下会自动换算。 |
| `ocr_backend` | 默认 `auto`：macOS 使用 Apple Vision（`vision`，需要 Swift），其他平台使用 `rapidocr`（RapidOCR + ONNX Runtime）。 |
| `notes_dir` | 默认 `知识库`，Vault 内的知识笔记相对目录。 |
| `attachments_dir` | 默认 `附件`，Vault 内图片附件相对目录。 |
| `authors_dir` | 默认 `抖音作者`，作者文档相对目录。 |
| `question_root` | 默认 `面试题库`，置于 `notes_dir` 内；写作规则使用此默认分类名称，首次安装建议保留。 |
| `review_state_file` | 默认 `.dy-author-review-state.json`，Vault 内的学习/审核状态文件。 |
| `unified_only` | 保持 `true`，使用现有统一索引和日志格式。 |
| `cc_binary` | 可选 cc-connect 可执行文件的绝对路径；未填时尝试 `~/.local/bin/cc-connect`。建议明确填写。 |
| `cc_data_dir` | 可选 cc-connect 当前服务的实际 data-dir；未填时使用 `~/.cc-connect`。须与该服务一致。 |

目录配置不是任意 shell 代码。路径包含空格时在终端中完整引用。相对分类目录不要带 `..` 或绝对路径；不把聊天内容拼入 shell。修改输出目录时也要同步审阅写作规则，避免 Agent 的分类输出与脚本配置不一致。Windows 下配置器创建技能链接时优先使用符号链接，权限不足时自动改用目录联接（junction）。

不在 `config.json` 保存 API key、Cookie、UIFID、Chrome 密钥、平台 token 或会话 ID。模型和消息平台认证在你自己的 Agent/cc-connect 中配置。`CC_PROJECT`、`CC_SESSION_KEY` 只由当前运行会话提供，不能从别人的安装示例复制。

## 在 Windows 使用独立 Chrome 资料

当 `doctor.py` 报告 `cookie_decryption_failed` 时，可为本项目创建独立资料。在 PowerShell 运行以下命令，若 Chrome 安装在其他位置，请替换可执行文件路径。

```powershell
$dyChromeData = Join-Path $env:LOCALAPPDATA 'dy-author\Chrome'
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" "--user-data-dir=$dyChromeData" "https://www.douyin.com/"
```

在新窗口手动登录抖音。打开 `chrome://version` 确认 **Profile Path**，通常是 `%LOCALAPPDATA%\dy-author\Chrome\Default`。从 Chrome 菜单完全退出此实例，让数据库释放文件锁。

首次配置时，通过 `--chrome-profile` 和 `--chrome-cache` 传入资料目录及其 `Cache\Cache_Data` 子目录。已有配置时，在 `config.json` 中更新 `browser_profile` 和 `browser_cache_dir`，填写实际的绝对路径，`browser` 使用 `chrome`。运行 `scripts\doctor.py` 检查状态。

## 手动检查队列

使用配置中相同的 Python 和本技能真实脚本路径。例如在仓库根：

```sh
./.venv/bin/python -B scripts/dy_author.py --help
./.venv/bin/python -B scripts/dy_author.py init
```

Windows 使用 `.\.venv\Scripts\python.exe -B scripts\dy_author.py --help` 等同一组命令。

`init` 会创建运行目录。下一步由 Agent 将**当前带显式命令前缀的请求**写入返回的 `input_file`，再执行 `plan`。不要直接拿 README 的占位作品 ID 运行，也不要为裸分享补前缀冒充用户授权。

`plan/prepare-all/catalog-search/commit/skip/fail/progress/status` 的 `--run` 一律取实际返回值，作品 `--id` 取该批次实际 ID。`--config` 是全局参数，放在子命令前；首次配置通常无需传它。

## 更新与卸载

- 更新前保留本地配置和未完成 `.cache`，不要覆盖运行快照。依赖变更后重新安装版本清单并运行本地测试/doctor。
- 配置器拒绝覆盖旧安装。重新配置前自行备份并检查旧 `config.json` 和命令，明确移除旧安装入口后再生成；不要删除已保存笔记。
- 卸载只移除你安装的 `.claude/skills/dy-author` 链接与 `.claude/commands/dy-author.md`，再按需归档仓库和缓存。不要对 Vault 运行清理命令。
