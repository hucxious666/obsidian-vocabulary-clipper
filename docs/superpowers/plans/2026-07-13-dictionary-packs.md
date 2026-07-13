# Offline Dictionary Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户可视化下载并切换 ECDICT 完整字段版与 Kaikki English，且不再由 Git 分发词典数据库。

**Architecture:** 下载器把不同官方来源转换成统一 SQLite 词典包；Native Host 通过词典仓库按配置选择包；扩展设置页只操作安装状态和当前词典。来源构建、包校验、运行时查询和 UI 分层，避免把 ECDICT/Kaikki 分支扩散到写入逻辑。

**Tech Stack:** Python 3.11+、SQLite、Tkinter、PowerShell、Chrome Manifest V3、Node 内置测试、Python unittest

**Status:** 2026-07-13 已完成实现；实际下载验证补充了 GitHub Contents API、Windows Schannel 下载路径和同包并发安装锁。最终回归结果记录在本次任务交付中。

---

## 文件结构

- 新建 `dictionary-catalog.json`：可下载词典白名单与来源元数据。
- 新建 `clipper/dictionary_schema.py`：统一 schema、元数据读写和包校验。
- 修改 `clipper/dictionary_builder.py`：构建完整字段 ECDICT 包。
- 新建 `clipper/kaikki_builder.py`：流式构建 Kaikki English 包。
- 新建 `clipper/dictionary_download.py`：安全下载、校验、临时构建和原子安装。
- 新建 `clipper/dictionary_repository.py`：列出已安装包并创建当前查询器。
- 修改 `clipper/dictionary.py`：返回统一义项、例句和来源模型。
- 新建 `clipper/dictionary_manager_gui.py` 与 `dictionary-manager.ps1`：可视化词典下载器。
- 修改 `clipper/config.py`、`clipper/service.py`、`native_host.py`：保存选择、暴露状态并打开下载器。
- 修改 `extension/options.html|js|css`、`extension/lib.js`、`extension/lookup-popover.js`：状态、切换与富词条展示。
- 修改 `install.ps1`、`.gitignore`、`README.md`、`THIRD_PARTY_NOTICES.md`、`data/SOURCE.txt`：分发与文档。

### Task 1: 统一词典包 schema 与 ECDICT 完整字段

- [ ] 在 `tests/test_dictionary_builder.py` 写失败测试：输入包含全部 ECDICT 字段，断言 SQLite 保存 `definition`、`translation`、`pos` 及 `metadata_json` 中的所有来源字段。
- [ ] 运行 `python -m unittest tests.test_dictionary_builder -v`，确认因新 schema 尚不存在而失败。
- [ ] 新建 `clipper/dictionary_schema.py`，定义 `SCHEMA_VERSION = 1`、建表 SQL、`write_pack_metadata()` 和 `validate_pack()`。
- [ ] 修改 `clipper/dictionary_builder.py` 使用统一 schema，并从 `exchange` 写入 `forms`。
- [ ] 再次运行该测试模块，确认通过。

### Task 2: Kaikki 流式构建

- [ ] 新建 `tests/test_kaikki_builder.py`，用 gzip JSONL fixture 表达多个词性、IPA、gloss、tags、example、quotation 和非英语记录；断言只导入英语、合并词头、保留普通例句并建立词形。
- [ ] 运行 `python -m unittest tests.test_kaikki_builder -v`，确认模块缺失导致失败。
- [ ] 新建 `clipper/kaikki_builder.py`，逐行读取 gzip，按词头写入 `entries/senses/examples/forms`，不把整个源加载进内存。
- [ ] 重跑该测试模块，确认通过。

### Task 3: 统一查询模型与仓库

- [ ] 重写 `tests/test_lookup.py` 的词典 fixture，并新增来源、英文义项、例句、词形回退和损坏包测试。
- [ ] 新建 `tests/test_dictionary_repository.py`，覆盖安装状态、未安装包、未知包和包 ID 不匹配。
- [ ] 运行两个测试模块，确认旧 `DictionaryLookup` API 无法满足新断言。
- [ ] 修改 `clipper/dictionary.py`，定义 `DictionarySense`、`DictionaryExample`、`DictionaryEntry` 并查询统一 schema。
- [ ] 新建 `clipper/dictionary_repository.py`，只允许目录内白名单文件并调用 `validate_pack()`。
- [ ] 重跑两个测试模块，确认通过。

### Task 4: 下载、校验与可视化管理器

- [ ] 新建 `tests/test_dictionary_download.py`，注入本地文件下载函数，覆盖 SHA 不匹配、gzip/构建失败不覆盖旧包、成功原子安装和临时文件清理。
- [ ] 运行测试，确认下载模块缺失导致失败。
- [ ] 新建 `dictionary-catalog.json`，登记固定提交 ECDICT 与官方 Kaikki English gzip。
- [ ] 新建 `clipper/dictionary_download.py`，实现 HTTPS 白名单、最大体积、SHA、进度回调、构建器分派和原子安装。
- [ ] 新建 `clipper/dictionary_manager_gui.py`，使用后台线程和队列更新 Tkinter 进度与状态。
- [ ] 新建 `dictionary-manager.ps1`，从 `python-path.txt` 或 PATH 启动 GUI。
- [ ] 重跑下载测试，确认通过。

### Task 5: 配置迁移和 Native Message 接口

- [ ] 在 `tests/test_config_and_protocol.py` 增加旧配置默认 `ecdict`、新配置持久化 `dictionary_id` 测试。
- [ ] 在 `tests/test_service.py` 增加 `get_settings` 返回词典列表、`save_settings` 拒绝未安装词典、查询使用选中词典及 `open_dictionary_manager` 测试。
- [ ] 运行两个模块，确认新字段和 action 尚不存在而失败。
- [ ] 修改 `clipper/config.py` 增加 `dictionary_id`，兼容旧 JSON。
- [ ] 修改 `clipper/service.py` 注入 `DictionaryRepository`，增加 `open_dictionary_manager`，并输出统一查词响应。
- [ ] 修改 `native_host.py` 传入词典目录、catalog 和下载器脚本。
- [ ] 重跑两个测试模块，确认通过。

### Task 6: 扩展设置和查词卡片

- [ ] 在 `tests/js/test_extension_lib.js` 增加词典设置归一化和来源标签测试，在 `tests/test_install_layout.py` 增加设置控件、下载器打包检查。
- [ ] 运行 `node --test tests/js/test_extension_lib.js` 和 `python -m unittest tests.test_install_layout -v`，确认失败。
- [ ] 修改 `extension/options.html|js|css`，增加当前词典下拉框、安装状态、刷新与“管理离线词典”按钮。
- [ ] 修改 `extension/lib.js` 归一化 `activeDictionary/dictionaries` 并格式化来源。
- [ ] 修改 `extension/lookup-popover.js|css`，显示来源名称、英文义项、标签和例句。
- [ ] 重跑 JavaScript 和布局测试，确认通过。

### Task 7: 分发、迁移和文档

- [ ] 先修改 `tests/test_install_layout.py`，要求安装器不复制仓库数据库、复制 catalog/下载器、生成词典目录，并要求 `.gitignore` 排除 `data/dictionaries`、`*.sqlite3`、下载源。
- [ ] 运行布局测试，确认失败。
- [ ] 修改 `install.ps1`，移除旧的仓库数据库复制逻辑，复制下载器与 catalog，并在未跳过词典时打开可视化管理器。
- [ ] 修改 `.gitignore`，从 Git 索引移除 `data/ecdict.sqlite3`，保留来源说明。
- [ ] 更新 `README.md`、`THIRD_PARTY_NOTICES.md`、`data/SOURCE.txt`，记录大小、滚动源、许可证和更新方法。
- [ ] 重跑布局测试，确认通过。

### Task 8: 完成验证

- [ ] 运行 `python -m unittest discover -s tests -v`，要求零失败。
- [ ] 运行 `node --test tests/js/test_extension_lib.js`，要求零失败。
- [ ] 对 `extension/background.js`、`content.js`、`lookup-popover.js`、`options.js`、`popup.js`、`viewer.js` 逐个运行 `node --check`。
- [ ] 运行 `powershell -ExecutionPolicy Bypass -File .\install.ps1 -SkipDictionary -NoOpenChrome`，检查幂等安装布局且不下载大词典。
- [ ] 使用小型 ECDICT/Kaikki fixture 执行两个构建器并用 `validate_pack()` 查询示例词。
- [ ] 检查 `git status --short` 与 `git diff --stat`，确认没有 SQLite、CSV、JSONL 或凭据进入待提交内容。

> 按工作区规则，本计划不执行 commit、push 或其他 Git 历史操作；这些操作需要用户另行明确授权。
