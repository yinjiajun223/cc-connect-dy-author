# 验证方式与范围

在全新的 Python 3.12 虚拟环境中安装本仓库的 requirements.lock.txt，再运行 pip check 和完整 unittest：

~~~sh
python -m pip install -r requirements.lock.txt
python -m pip check
python -B -m unittest discover -s tests -v
~~~

测试使用临时 Vault、合成材料和显式替代的外部接口，覆盖显式命令范围、作者分页与归属、游标、视频与图文、原始材料补录、全库查重、作者文档、面试题库、通知去重、事务回滚和安装配置。测试只加载本仓库的脚本。

知识总索引和导入总日志由本仓库维护。日志摘要显示总记录数，历史来源单元格仍被保留。笔记、题目文档和总览在本仓库的锁与事务中提交。

离线回归、依赖安装与实际在线导入分别判断。单元测试不能证明抖音接口、账号权限或 Cookie 当前可用，也不能证明任意素材的转写和识别质量。doctor 只检查本机配置和依赖发现。

本文给出当前源码的验证方法；具体测试结果以对应提交或 Release 的运行记录为准。

完整功能支持 macOS Apple Silicon 与 Windows 10/11 x64。Linux、Intel Mac 与 Windows ARM 的在线导入与识别不在当前验证承诺中。

## 2026-11-18：Windows 在线小样本

- 使用独立 Chrome 资料手动登录并退出浏览器后，`doctor` 返回 `ready`，抖音会话状态为 `available`。在线验证读取同一作者的两页作品，共 40 条，测试在页数上限处停止。
- 真实图文下载 5 张原图并完成 RapidOCR。首次写入空测试 Vault 时，笔记、附件、知识总索引和导入总日志一并提交；重复提交同一作品返回 `exists`。
- 两条公开视频成功下载并提取音轨。转写只输出一句字幕样文字，未据此生成笔记。另用合成中文语音验证 FFmpeg 提取与 faster-whisper CPU 转写。
- 随后使用一条有清晰中文口播的公开视频复测。约 108 秒音轨转写为 52 段，整理的笔记已写入测试 Vault。索引和日志各包含一条视频记录，重复提交返回 `exists`。转写存在部分游戏术语误识别，笔记只采用语义明确的片段。
- Windows 本机运行 `python -B -m unittest discover -s tests` 共 201 项通过。

## 2026-11-16：Windows 支持

在 Windows 10（10.0.19045，x64）与 Python 3.12.14 上加入平台后端，macOS Apple Silicon 的原路线保持不变：

- 本地 ASR：macOS 继续使用 MLX Whisper；Windows 使用 faster-whisper（默认 CPU int8，可用 `asr_device` 切换 CUDA/auto）。`transcript.json` 增加 `asr_backend` 字段，其余结构与材料校验不变。
- 图文 OCR：macOS 继续使用 Apple Vision（Swift）；Windows 使用 RapidOCR（ONNX Runtime）。两种后端输出同一 `pages` 结构。
- Chrome 资料、Cookie 与 Simple Cache 读取支持 Windows（`%LOCALAPPDATA%\Google\Chrome\User Data`）；可见恢复直接启动已安装的 Chrome/Edge/Firefox，Windows 没有标签页自动化（`opened_tab_closed=unavailable`）。
- 文件锁改为跨平台实现（POSIX `fcntl.flock`，Windows `msvcrt` 字节锁）；笔记属性区解析兼容 CRLF/BOM；文本与哈希显式使用 UTF-8；Windows 保留文件名（CON、NUL 等）自动改写；安装器在无符号链接权限时改用目录联接（junction）。
- 浏览器缓存扫描容忍文件时间戳略微超前系统时钟（Windows 上可见），避免刚写入的官方响应被误判为过期；超前超过 60 秒的异常时间戳仍被忽略。
- CLI 输出强制 UTF-8：Windows 的控制台与管道编码跟随系统区域代码页（中文主机为 cp936），而六个入口都用 `ensure_ascii=False` 输出中文 JSON，宿主 Agent 按 UTF-8 解析会得到乱码。新增 `scripts/console.py`，在 `author_works`、`backfill_authors`、`configure`、`doctor`、`dy_author`、`pipeline` 的 `main()` 开头把 stdout/stderr 重设为 UTF-8；无法重设的流（如测试替身）原样跳过。同理，`batch_notice` 向 cc-connect 的 `--stdin` 写入时显式指定 `encoding="utf-8"`，否则中文批次提示会按 cp936 编码送达。
- `requirements.lock.txt` 使用环境标记区分平台：Windows 安装 faster-whisper、RapidOCR 及其运行依赖，macOS Apple Silicon 安装 MLX。在 Windows 上排除需 GitHub 网络的 F2 行后，`pip install --dry-run -r requirements.lock.txt` 可完整解析。

验证结果：Windows 上 `python -B -m unittest discover -s tests` 共 197 项全部通过（含 4 项新增的 CLI 编码回归；其中在 `PYTHONIOENCODING=gbk` 下断言 stdout 为合法 UTF-8 的那一项，已确认在缺少修复时会因 GBK 字节解码失败而报错）。`scripts/configure.py` 在项目副本中实际生成 `config.json`、命令文件与技能目录链接——符号链接权限不足时回退为目录联接（`os.path.isjunction` 为真，且可透过链接读到 `SKILL.md`）；随后 `scripts/doctor.py` 返回 `ready`、退出码 0（Windows AMD64、asr=faster-whisper、ocr=rapidocr、8 个依赖模块全部可发现、`--no-browser` 配置下会话为 disabled）。ffmpeg 由 `imageio-ffmpeg` 自带的 Windows 二进制解析成功，无需系统安装。RapidOCR 对合成中文图片执行完整 `image_posts.extract`，经 sha256 证据校验后写出 `transcript.json`，10 个汉字全部正确识别。faster-whisper 按 `pipeline.transcribe` 的真实契约（`wave` 解码后的 float32 numpy 数组，而非文件路径）在 CPU 上完成合成音频转写，返回 `{text, segments, language}` 结构且 `language=zh`。以上回归与安装验证均在项目副本（D: 盘）上执行，未向仓库目录写入 `config.json`。

已知依赖约束：`av==19.0.2` 的 `av.open()` 不再接受 `metadata_errors`，而 `faster-whisper==1.2.1` 的 `decode_audio` 在**输入为文件路径时**仍会传该参数，因此向 `asr.transcribe` 传路径会抛 `TypeError`。当前流程不受影响：`pipeline.transcribe` 先用 `wave` 自行解码并强制 16kHz 单声道 PCM，只把 numpy 数组交给引擎，该路径不经过 `av.open`。若日后改为直接传媒体路径，需先给 `av` 加上界或改走数组解码。

未验证项：本机未执行真实抖音在线导入（作者分页、接口与真实账号的 Chrome 会话读取），也未在 macOS 真机复跑回归。离线测试不能证明平台接口、账号权限或识别质量始终可用。

## 2026-10-26：Chrome 会话与默认静默

在固定的 Python 3.12.14 环境下，针对本次修改运行 `test_chrome_session`、`test_configure`、`test_douyin_access`、`test_author_works`、`test_dy_author`、`test_invocation_scope`：84 项通过，无失败、错误或跳过。Skill 的 `quick_validate.py` 通过。

覆盖 zcode 改写 HOME 后仍定位真实用户资料、多个 profile 中复用抖音会话、缓存资料匹配、缺少/过期会话提示、读取失败脱敏、首次配置默认不弹页、默认详情失败不启动浏览器，以及当前关闭设置约束旧批次且保留已保存条目。可见恢复测试显式配置 `auto_browser_recovery=true`。

会话检查仅判断本机是否读到未过期标记，不验证服务器是否接受，也不构成真实作者全量下载通过。接口拒绝、缓存查找不完整与缺少登录会话仍分别判断。
