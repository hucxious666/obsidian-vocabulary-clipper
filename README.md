# Obsidian 词汇采集器

在 Chrome PDF 中选中英文单词或短语，通过右键菜单直接写入指定 Obsidian Chapter 或 NEWS Markdown 文件。

## 安装

1. 在 PowerShell 中进入本目录，运行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

2. 安装器会打开 `chrome://extensions`。开启“开发者模式”，点击“加载已解压的扩展程序”，选择安装器输出的扩展目录：

   ```text
   %LOCALAPPDATA%\ObsidianVocabularyClipper\app\extension
   ```

3. 打开扩展的“详情 → 扩展程序选项”，确认两个 Markdown 路径，选择当前 Chapter，并填写百度翻译 APP ID 与密钥。
4. 点击“保存设置”，再点击“测试连接”。

> 百度凭据只由本地 Native Messaging 宿主接收，并使用 Windows DPAPI 加密；扩展存储、源码和日志中不保存明文。由于此前凭据曾出现在聊天内容中，正式使用前建议先在百度控制台轮换。

## 使用

- 在 Chrome PDF 中选中 1–5 个英文单词。
- 右键选择“加入 Chapter N”或“加入 NEWS”。
- 成功时扩展图标短暂显示 `✓`；重复、查询失败或写入失败时弹出通知。
- Chapter 目标只在当前章节内去重；NEWS 在整个 NEWS 文件内去重。

## 释义来源

写入笔记时按以下顺序查询：

1. ECDICT 作为主要释义来源，保留词性和多条中文释义。
2. 单词为复数、时态等词形变化时，保留所选单词的音标和拼写，优先使用词元的完整释义。
3. 只有 ECDICT 释义为空时才调用百度翻译兜底。

例如 `ignominious` 会写为类似：

```md
1. ignominious /.ignәu'miniәs/: <span class="meaning">adj.可耻的；不名誉的；下流的</span>
```

## 有道词典预览（可选）

扩展设置页支持配置有道智云 `App Key` 和 `App Secret`，保存后输入测试单词并点击“测试有道词典”。

- 调用的是有道词典 API `/v2/dict`，不是已经下线词典字段的普通文本翻译 API。
- 有道词典服务通常需要单独申请权限；若显示错误 `110`，请先联系有道开通词典服务。
- 查询结果只在设置页临时显示，不写入 Markdown、不保存、不缓存。
- 有道凭据与百度凭据一样由 Windows DPAPI 加密，设置页和 Native Message 响应均不回显密钥。

官方文档：[有道词典 API](https://ai.youdao.com/DOCSIRMA/html/dictionary/api/ydcd/index.html)

## 默认文件

- Chapter：`D:\obsidian\repository\Workhouse\study\词汇积累-蒙蔽版.md`
- NEWS：`D:\obsidian\repository\Workhouse\study\NEWS WORD - COVERED.md`
- 当前章节：`chapter 22`

## 测试

```powershell
python -m unittest discover -s tests -v
node tests\js\test_extension_lib.js
node --check extension\background.js
node --check extension\options.js
```

## 卸载

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

默认保留加密配置与最近备份；如需全部清理，使用 `-Purge`。Chrome 中的解压扩展需在 `chrome://extensions` 手动移除。

## 第三方数据

音标数据来自 [ECDICT](https://github.com/skywind3000/ECDICT)，采用 MIT License。安装包固定校验原始 CSV 的 SHA-256；若上游内容发生变化，安装会停止并提示哈希不匹配。
