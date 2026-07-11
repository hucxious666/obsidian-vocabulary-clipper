# Obsidian 词汇采集器

在普通网页或自带 PDF 阅读器中选中英文内容：单个词显示音标、词性和完整中文释义，短语或句子直接翻译为中文；单词还可写入指定 Obsidian Chapter 或 NEWS Markdown 文件。

## 安装

1. 在 PowerShell 中进入本目录，运行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

2. 安装器会打开 `chrome://extensions`。开启“开发者模式”，点击“加载已解压的扩展程序”，选择安装器输出的扩展目录：

   ```text
   %LOCALAPPDATA%\ObsidianVocabularyClipper\app\extension
   ```

   如需读取本地 PDF，请在扩展的“详情”页开启“允许访问文件网址”。

3. 打开扩展的“详情 → 扩展程序选项”，确认两个 Markdown 路径，选择当前 Chapter，并填写百度翻译 APP ID 与密钥。
4. 点击“保存设置”，再点击“测试连接”。

> 百度凭据只由本地 Native Messaging 宿主接收，并使用 Windows DPAPI 加密；扩展存储、源码和日志中不保存明文。由于此前凭据曾出现在聊天内容中，正式使用前建议先在百度控制台轮换。

## 使用

- 在普通网页中选中单个英文词，会在选区附近显示分组释义卡片。
- 选中包含至少两个英文词的短语或句子时，直接显示中文翻译；允许标点、数字和换行，最多 500 字符。
- 打开在线或本地 PDF 时，扩展默认切换到“词汇 PDF 阅读器”；阅读器支持连续滚动、页码、缩放、适合宽度、下载和返回 Chrome 原阅读器。
- 释义卡片显示单词、音标、按词性分组的完整中文释义，并提供“加入 Chapter N”和“加入 NEWS”；翻译卡片只显示原文、译文和来源。
- 原有右键选词菜单继续支持 1–5 个英文单词或短语。
- 成功时扩展图标短暂显示 `✓`；重复、查询失败或写入失败时弹出通知。
- Chapter 目标只在当前章节内去重；NEWS 在整个 NEWS 文件内去重。
- 可在扩展设置页分别关闭“网页选区查词与翻译”或“自动使用词汇 PDF 阅读器”。

> Chrome 设置页、Chrome Web Store 等受限页面不允许扩展注入双击查词脚本。若某个在线 PDF 因登录或站点限制无法加载，可点击“返回 Chrome 阅读器”。

## 释义来源

写入笔记时按以下顺序查询：

1. ECDICT 作为主要释义来源，保留词性和多条中文释义。
2. 单词为复数、时态等词形变化时，保留所选单词的音标和拼写，优先使用词元的完整释义。
3. 只有 ECDICT 释义为空时才调用百度翻译兜底。

例如 `ignominious` 会写为类似：

```md
1. ignominious /.ignәu'miniәs/: <span class="meaning">adj.可耻的；不名誉的；下流的</span>
```

## 句子翻译来源

多词选区按以下顺序翻译：

1. 优先调用百度文本翻译。
2. 百度出现网络、签名、额度或空结果错误时，若已配置有道凭据，则调用有道 NMT 文本翻译后备。
3. 两个服务都失败时，弹窗显示经过清理的错误信息，不包含凭据、签名或原始 API 响应。

扩展设置页支持配置有道智云 `App Key` 和 `App Secret`，保存后可输入英文句子并点击“测试有道翻译”。调用的是有道文本翻译 API `/api`，不再依赖 `/v2/dict` 词典服务。测试结果只在设置页临时显示，不写入 Markdown、不保存、不缓存；凭据仍由 Windows DPAPI 加密。

官方文档：[有道文本翻译 API](https://ai.youdao.com/DOCSIRMA/html/trans/api/wbfy/index.html)

## 默认文件

- Chapter：`D:\obsidian\repository\Workhouse\study\词汇积累-蒙蔽版.md`
- NEWS：`D:\obsidian\repository\Workhouse\study\NEWS WORD - COVERED.md`
- 当前章节：`chapter 22`

## 测试

```powershell
python -m unittest discover -s tests -v
node tests\js\test_extension_lib.js
node --check extension\background.js
node --check extension\content.js
node --check extension\lookup-popover.js
node --check extension\options.js
node --check extension\viewer.js
```

## 卸载

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

默认保留加密配置与最近备份；如需全部清理，使用 `-Purge`。Chrome 中的解压扩展需在 `chrome://extensions` 手动移除。

## 第三方数据

- 音标和释义数据来自 [ECDICT](https://github.com/skywind3000/ECDICT)，采用 MIT License。
- PDF 阅读器使用 [Mozilla PDF.js](https://github.com/mozilla/pdf.js) 6.1.200，采用 Apache-2.0 License，必要运行文件和许可证已随扩展固定打包。
