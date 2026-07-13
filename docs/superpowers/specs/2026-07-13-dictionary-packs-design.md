# 离线词典包设计

## 目标

将当前写死的 ECDICT SQLite 改造成可安装、可切换的离线词典包。完整词典不进入 Git；用户通过可视化下载器安装 ECDICT 完整字段版或 Kaikki English，并在 Chrome 扩展设置中选择当前词典。MDX/MDD 不在本次范围。

## 已确认范围

- ECDICT 来源固定到已校验的上游提交，构建时保留 CSV 的全部字段。
- Kaikki 使用官方 English Wiktextract JSONL gzip 滚动数据，第一版保留英语词头、IPA、分义项、标签和例句。该按语言后处理包已被上游标记为未来弃用，因此作为实验性来源展示，转换层不依赖其下载 URL。
- 运行时只读取统一格式 SQLite；CSV/JSONL 仅是下载和构建输入。
- 词典安装目录为应用目录下的 `data/dictionaries/`，仓库通过 `.gitignore` 排除生成数据库和下载缓存。
- 设置页显示词典安装状态，能够打开可视化下载器，并只能切换到已经安装且格式有效的词典。
- Markdown 继续维持当前单行结构。Kaikki 例句先显示在查词卡片，不写入 Markdown，避免破坏已有编号、去重和尾部续号规则。

## 方案选择

### 采用：统一 SQLite 词典包

每个来源由独立构建器转换成相同的 schema。查询服务只依赖词典包接口，不了解 ECDICT CSV 或 Wiktextract JSONL 的结构。该方案增加一次构建成本，但运行时稳定、查询快，也为以后增加其他语言包保留边界。

### 未采用：运行时直接读取来源格式

直接读取 ECDICT CSV 与 Kaikki JSONL 会让查询、词形和 UI 逻辑充满格式分支；Kaikki 文件也不适合每次查词扫描。

### 未采用：把所有来源压成旧三字段表

旧表无法表达多义项、例句和来源元数据，会再次丢失本次希望观察的 Kaikki 效果。

## 词典包格式

每个包是一个独立 SQLite 文件，包含：

- `pack_metadata(key, value)`：包 ID、名称、schema 版本、语言、来源版本、许可证和构建时间。
- `entries(id, word, phonetic, definition, translation, pos, metadata_json)`：词头和来源原始字段。
- `senses(id, entry_id, position, part_of_speech, gloss, translated_gloss, tags)`：规范化义项。
- `examples(id, sense_id, position, text, translation)`：例句。
- `forms(form, lemma)`：词形映射。

ECDICT 的 `definition/translation/pos/collins/oxford/tag/bnc/frq/exchange/detail/audio` 全部保留；来源专有字段放入 `metadata_json`。Kaikki 同一个词性记录合并到词头下，并保留最多三个非 quotation 例句/义项，控制数据库体积。

## 下载与安装

仓库包含 `dictionary-catalog.json`，只记录包元数据、官方 HTTPS 地址、预估大小、构建格式和许可证链接。

`dictionary-manager.ps1` 启动本地 Tkinter 下载器。下载器在后台线程中执行以下流程：

1. 下载到系统临时目录并显示字节进度。Windows 优先使用系统 `curl.exe`/Schannel，规避 Python OpenSSL 与部分词典服务器的 TLS 兼容问题；其他环境保留 urllib 路径。
2. ECDICT 校验固定 SHA-256；Kaikki 校验 HTTPS、gzip CRC 和结构。
3. 构建同目录临时 SQLite，校验 schema、包 ID 和词条数。
4. 原子替换 `data/dictionaries/<id>.sqlite3`。
5. 删除源文件和临时文件。

ECDICT 通过 GitHub 官方 Contents API 的 raw 媒体类型下载，固定 commit 和 SHA-256。每个词典包使用 Windows named mutex 防止多个下载窗口并发构建同一目标。

设置页的“管理离线词典”按钮通过 Native Messaging 打开该下载器；关闭下载器后点击刷新即可看到安装状态。

## 查询与展示

- `AppConfig` 新增 `dictionary_id`，旧配置缺少该字段时默认使用 `ecdict`。
- 查询工厂根据配置选择词典包，不再接收单一固定数据库路径。
- ECDICT 优先显示中文分组释义，并附带英文释义和学习标签摘要。
- Kaikki 显示英文词性、英文义项、标签及例句。
- Markdown 使用当前词典的主要释义；为空时仍使用百度翻译兜底。
- 查词响应返回 `sourceId/sourceName/groups/examples/metadata`，UI 不再写死“来源：ECDICT”。

## 错误处理

- 未安装、schema 不兼容、包 ID 不匹配和损坏数据库都返回明确的 `lookup_failed`，不写 Markdown。
- 不能选择未安装词典；旧配置在 ECDICT 未安装时仍保留选择，但设置页显示“未安装”。
- 下载失败不会覆盖已有词典；日志和界面不包含百度/有道凭据。
- Kaikki 是滚动源，安装记录实际下载时间、ETag、Last-Modified 和 SHA-256，供后续更新判断。

## 验证

- Python 单元测试覆盖统一 schema、完整 ECDICT 字段、Kaikki 多义项/IPA/例句、配置迁移、词典状态和切换。
- 下载测试使用本地 fixture 和注入下载器，验证校验失败、构建失败与原子替换，不下载真实大型词库。
- 实机验收额外完成完整 ECDICT 与 Kaikki 下载、构建和查询：ECDICT 770,611 词条；Kaikki 1,346,447 词条、1,771,796 条义项和 137,800 条例句。
- JavaScript 测试覆盖设置归一化、词典状态和来源名称。
- 完整回归运行 `python -m unittest discover -s tests -v`、Node 测试及所有扩展脚本的 `node --check`。

## 授权边界

仓库只分发构建代码和来源说明。用户从 ECDICT、Kaikki/Wiktionary 官方地址自行下载数据；下载器展示来源与许可证链接。生成的 SQLite、源 CSV/JSONL 和缓存均不进入 Git。
