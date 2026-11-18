# 抖音作者作品批量入库（/dy-author）

从作品链接识别抖音作者，分页获取其可访问的公开视频与图文，通过分批处理、作品 ID 去重和运行检查点，将内容整理为按主题组织的 Obsidian 知识笔记，同步维护作者文档、知识索引和导入日志。

当前 Agent 负责内容理解、核心知识提炼与笔记写作；本项目脚本负责内容获取、去重、校验和事务保存。核心流程不依赖 CC Connect 或微信 Bot，CC Connect 命令接入与批次通知均为可选功能。

## 核心功能

- 以一条作品识别作者，收集其公开视频与图文，按作品 ID 查重；每批最多十条，每条完成立即保存。
- 从真实音轨做本地 Whisper 转写；图文下载完整图片并做本地 OCR（macOS Apple Vision / Windows RapidOCR），Agent 再逐页看图。
- 生成知识笔记、维护作者文档、知识总索引与导入总日志；保留已有笔记和“我的补充”。
- 对原始材料含“面试”的作品生成/合并面试题；`/dy-author 补录` 为已有面试类知识笔记补建题库。
- 保存运行检查点；后续条目失败或模型额度耗尽不回滚已经成功的作品。
- 可向**明确绑定的当前 cc-connect 会话**发批次进度；发送失败不影响保存，不自动重发未知送达结果。

普通作品链接不会授权全作者导入。只有当前消息显式使用 `/dy-author` 或 `$dy-author` 才启动本技能。

## 宿主与运行依赖

完整媒体路线支持 **macOS Apple Silicon（M 系列）+ Python 3.12** 与 **Windows 10/11 x64 + Python 3.12**；两个平台使用相同的队列、去重、检查点和写入逻辑，只替换本地识别组件：

| 平台 | 本地 ASR | 图文 OCR | 额外系统依赖 |
| --- | --- | --- | --- |
| macOS Apple Silicon | MLX Whisper（`mlx-whisper`） | Apple Vision（Swift） | Apple Command Line Tools（含 Swift） |
| Windows 10/11 x64 | faster-whisper（CPU，可用 `asr_device=cuda`） | RapidOCR（ONNX Runtime） | 无；FFmpeg 来自系统或 `imageio-ffmpeg` |

Linux、Intel Mac 与 Windows ARM 的完整流程目前不承诺支持。两个平台都需要可用的 Google Chrome profile。首次转写会从 Hugging Face 下载模型，需要网络和本地磁盘空间。FFmpeg 可来自系统，或依赖中的 `imageio-ffmpeg`。

宿主 Agent 需要读取 Skill、读写本地文件、执行脚本，并能查看图文原图。只运行 Python 不会自动生成知识笔记；模型账号与服务由用户自行配置。

### 宿主接入范围

可独立配置 Skill，也可选用 [CC Connect](https://github.com/chenhg5/cc-connect) 接入聊天平台。配置器的命令集成采用 .claude 布局；Codex 等其他宿主需按其技能发现机制加载本仓库，文档中的 `$dy-author` 是显式技能入口。不同宿主的命令与工具权限不同，不承诺下载后在任意 Agent 中即用。

仅在需要聊天平台接入时，配置 CC Connect、Agent、模型账号、消息平台及实际 `work_dir`。微信 Bot 不是核心运行前提。

没有 Chrome 访问也可用 `--no-browser` 配置，但匿名请求可能拿不到完整作品；不会承诺绕过登录、验证码、私密或删除限制。首次使用建议选一个小作者，并先备份 Vault。

## 下载和安装

### 安装依赖

macOS：

```sh
git clone https://github.com/llm-xiaoye/cc-connect-dy-author.git
cd cc-connect-dy-author

# 将此路径替换为你电脑上 Python 3.12 的真实绝对路径。
/absolute/path/to/python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.lock.txt
```

Windows（PowerShell，先安装 64 位 Python 3.12）：

```powershell
git clone https://github.com/llm-xiaoye/cc-connect-dy-author.git
cd cc-connect-dy-author
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

也可以在 GitHub 点 **Code → Download ZIP** 后解压，再在解压目录执行后两步。不要复制开发者的虚拟环境，不要把仓库放进会同步公开的 Vault 内。下文命令以 macOS 的 `./.venv/bin/python` 为例；Windows 请改用 `.\.venv\Scripts\python.exe`，路径同样换成本机绝对路径。

`requirements.lock.txt` 保留原功能所用版本，包含固定 commit 与摘要的 F2 源码依赖；需要访问 PyPI/GitHub。它使用环境标记区分平台：macOS Apple Silicon 安装 MLX 依赖，Windows 安装 faster-whisper、RapidOCR 及其运行依赖。它是版本固定清单，**不是全包 wheel hash 锁**，不要加 `--require-hashes`。依赖安装失败时保留错误，不把它当成作品或技能处理失败；不建议任意升级 F2、yt-dlp 或 MLX 后仍假定行为不变。

### 生成配置

独立使用时，在仓库根执行以下命令，再按宿主的技能发现机制加载仓库：

```sh
./.venv/bin/python scripts/configure.py --vault "/absolute/path/to/your/ObsidianVault"
```

Windows 示例：`.\.venv\Scripts\python.exe scripts\configure.py --vault "D:\Obsidian\YourVault"`。

需要 CC Connect 命令集成时，改用下面的命令。两种配置方式选择一种，不要对已有配置重复执行。`--cc-workspace` 是 CC Connect 项目的实际工作目录，不是程序安装目录或 .claude 目录。

```sh
./.venv/bin/python scripts/configure.py \
  --vault "/absolute/path/to/your/ObsidianVault" \
  --cc-workspace "/absolute/path/to/your/cc-connect-workspace"
```

配置器会只读寻找真实系统用户的 Chrome 资料，优先复用已有的抖音会话；zcode 改写 HOME 不影响这个查找。缺少会话时提示你手动打开抖音登录，再重试。关闭登录页面通常不会清除会话，无需一直保持页面打开。读取失败会说明权限或路径问题，不等于账号已经退出。

1. 验证 Vault 与显式提供的路径，不新建 Chrome 资料。
2. 生成权限为 `0600`、被 Git 忽略的 `config.json`，记录当前虚拟环境入口；默认 `browser_profile=null` 自动识别、`auto_browser_recovery=false`。获取作者清单及下载作品默认不弹出页面。
3. 指定 --cc-workspace 时，在 work_dir 创建 `.claude/skills/dy-author` 链接与 `.claude/commands/dy-author.md`；Windows 优先创建符号链接，权限不足时自动改用目录联接（junction）。

已有配置、同名技能或命令时拒绝覆盖。更新时保留个人配置、虚拟环境与缓存。旧安装升级后，请将当前 `config.json` 的 `auto_browser_recovery` 设为 `false`；这一关闭设置也约束旧批次。其他运行参数仍使用创建时的快照，不删除旧批次或已保存笔记。

需要固定资料时，用 `chrome://version` 的 **Profile Path** 填入 `--chrome-profile`。标准 Chrome 缓存自动匹配；自定义 user-data 目录还需 `--chrome-cache`。只有明确希望可见浏览器恢复时才手动启用 `auto_browser_recovery=true`。请只授权自己的资料，不粘贴或提交 Cookie。

只安装 Skill、不创建 cc-connect 命令时省略 `--cc-workspace`。无浏览器模式用 `--no-browser` 代替 Chrome 参数。手动配置可参考 [config.example.json](config.example.json)，实际配置必须保存为本仓库的 `config.json`，所有路径换成你自己的绝对路径。字段说明见 [docs/configuration.md](docs/configuration.md)。

### 可选的批次通知

若需要在长任务中主动收到每批十条的提示，在**首次配置**时再加：

```sh
  --cc-binary "/absolute/path/to/cc-connect" \
  --cc-data-dir "/absolute/path/to/the/running-service-data"
```

这两个参数须同时指定；data-dir 必须与正在运行的 cc-connect 服务一致。已配置者可手动更新本地 `config.json` 的 `cc_binary` 与 `cc_data_dir`。不要把这些参数单独当成一条 shell 命令执行。

运行时由 cc-connect 提供当前 `CC_PROJECT` 和 `CC_SESSION_KEY`，技能不会猜测其他活跃会话。不要把示例或别人的会话 ID 写死到环境。没有会话绑定时由正常 Agent 回复展示进度；没有主动提示不影响笔记保存。

### 检查安装

```sh
./.venv/bin/python -B scripts/doctor.py
```

此检查只检查本地路径、平台和依赖模块发现，不联网、不下载模型、不写 Vault，也不证明抖音接口可用。完成后让 Agent 刷新技能发现或开启新会话；使用 CC Connect 时刷新对应会话。

## 使用方式

在已加载技能的会话中发送：

```text
/dy-author https://www.douyin.com/video/作品ID
```

也可以 `/dy-author` 后直接粘贴**完整分享文本**，其中必须恰好一条官方作品链接。不要先删掉 `/dy-author`。补录命令：

```text
/dy-author 补录
```

期望流程是：识别作者 → 翻页列作品 → 查重 → 每批准备材料 → 当前 Agent 写笔记/题目 → 逐条提交 → 继续下一批 → 最终汇报。**不要把 `scripts/dy_author.py` 的一次运行误当作整套 AI 写作**；它是供 Agent 驱动的队列接口。细节见 [references/workflow.md](references/workflow.md)。

## 配置与输出

输出通常位于你的 Vault：

```text
知识库/<主题分类>/<标题>.md
知识库/面试题库/<一级>/<子方向>/<题目>.md
抖音作者/<昵称>.md
知识总索引.md
导入总日志.md
附件/...
```

运行材料、转写、草稿和状态位于本地 `.cache/runs/<run_id>/` 等目录。它们可能包含个人学习记录及源作品内容，不能上传。中断后优先保留同一 run_dir 与检查点；新发同一显式命令会建立新批次，并排除已有/已跳过作品。

## 常见问题

- **接口 403/429、翻页中断**：会记录清单不完整；已获取作品可继续入库，不能称“全部”。不反复刷新，不编造签名。
- **抖音长文字文章（type 163）**：目前只列清单、标记暂不支持，不拿背景音乐冒充正文。视频和图文保留原支持范围。
- **需要登录/系统权限**：只在自己的 Chrome 完成必要交互。macOS 可能询问读取 Chrome 密钥/控制 Chrome 的权限；Windows 从当前系统用户的 Chrome 资料只读会话，读取受浏览器自身加密策略和文件权限影响，失败时报告 `read_error`。不愿授权时用无浏览器路线并接受其限制。
- **Windows 提示 `cookie_database_inaccessible`**：先在对应的 Chrome 资料中确认抖音已登录，保存工作后完全退出 Chrome（包括后台进程），再运行诊断。若仍失败，检查 Chrome 资料路径和读取权限。
- **Windows 提示 `cookie_decryption_failed`**：按[独立 Chrome 资料配置](docs/configuration.md#在-windows-使用独立-chrome-资料)登录并切换资料，再运行诊断。
- **Windows 提示缺少 faster_whisper / rapidocr_onnxruntime**：通常是依赖装到了另一个 Python 解释器。用 `.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt` 重装，再运行 `.\.venv\Scripts\python.exe -B scripts\doctor.py` 检查。
- **Windows 可见恢复**：只有显式启用 `auto_browser_recovery=true` 才自动打开已安装的 Chrome/Edge/Firefox；Windows 没有 AppleScript 等价的标签页管理，本次打开的新标签不会自动关闭（`opened_tab_closed=unavailable`）。
- **下载成功但没笔记**：Agent 仍需读取完整材料并写作/commit；标题、封面和摘要不足以入库。
- **命令没出现**：检查安装的 work_dir 与当前会话一致、`.claude` 适配器支持情况、安装路径是否移动，然后刷新/重启会话。
- **运行出错**：保留原批次；先检查具体阶段。浏览器缓存扫描不完整不能判为作品不可提取。恢复说明见 [references/recovery.md](references/recovery.md)。

只有清单完整、全部处理、无失败且无暂不支持时，才能称作者“全部作品已入库”。这里只处理账号可访问的公开内容；请遵守平台条款和内容权利。

## 限制与隐私

发布包只含技能、源代码、规则、测试和通用示例；个人配置与缓存被排除。数据流、反馈脱敏和权限边界见 [PRIVACY.md](PRIVACY.md)。模型服务仍可能接收到当前 Agent 为写作读取的转写、图片和所需目录/笔记摘录；本地 ASR/OCR 不等于整套流程完全离线。

## 开发与验证

```sh
./.venv/bin/python -B -m unittest discover -s tests
```

Windows 使用 `.\.venv\Scripts\python.exe -B -m unittest discover -s tests`。这些是本地回归，使用临时 Vault 与受控材料，不发真实抖音请求或主动聊天通知；它们不能保证未来平台接口一直可用。设计和保留的行为边界见 [docs/design.md](docs/design.md)。

## 许可证

采用 [MIT 许可证](LICENSE)；第三方依赖按各自许可证使用，见 [第三方声明](THIRD_PARTY_NOTICES.md)。

