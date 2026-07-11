const DEFAULTS = {
  chapterFile: "D:\\obsidian\\repository\\Workhouse\\study\\词汇积累-蒙蔽版.md",
  newsFile: "D:\\obsidian\\repository\\Workhouse\\study\\NEWS WORD - COVERED.md",
  selectedChapter: 22,
  chapters: Array.from({ length: 22 }, (_, index) => index + 1),
  credentialsConfigured: false,
  youdaoCredentialsConfigured: false,
  doubleClickLookupEnabled: true,
  autoOpenPdfEnabled: true,
};

const elements = {
  chapterFile: document.querySelector("#chapter-file"),
  newsFile: document.querySelector("#news-file"),
  chapter: document.querySelector("#chapter"),
  appId: document.querySelector("#app-id"),
  secretKey: document.querySelector("#secret-key"),
  credentialStatus: document.querySelector("#credential-status"),
  youdaoAppKey: document.querySelector("#youdao-app-key"),
  youdaoSecretKey: document.querySelector("#youdao-secret-key"),
  youdaoCredentialStatus: document.querySelector("#youdao-credential-status"),
  youdaoTestWord: document.querySelector("#youdao-test-word"),
  youdaoPreview: document.querySelector("#youdao-preview"),
  message: document.querySelector("#message"),
  doubleClickLookup: document.querySelector("#double-click-lookup"),
  autoOpenPdf: document.querySelector("#auto-open-pdf"),
};

function callNative(payload) {
  return chrome.runtime.sendMessage({ kind: "native", payload });
}

function showMessage(text, error = false) {
  elements.message.textContent = text;
  elements.message.classList.toggle("error", error);
}

function populateChapters(chapters, selected) {
  elements.chapter.replaceChildren();
  for (const value of chapters || []) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `Chapter ${value}`;
    option.selected = Number(value) === Number(selected);
    elements.chapter.append(option);
  }
}

function applySettings(settings) {
  const value = { ...DEFAULTS, ...(settings || {}) };
  elements.chapterFile.value = value.chapterFile;
  elements.newsFile.value = value.newsFile;
  populateChapters(value.chapters, value.selectedChapter);
  elements.credentialStatus.textContent = value.credentialsConfigured ? "已安全配置" : "未配置";
  elements.credentialStatus.classList.toggle("ready", value.credentialsConfigured);
  elements.youdaoCredentialStatus.textContent = value.youdaoCredentialsConfigured
    ? "已安全配置"
    : "未配置";
  elements.youdaoCredentialStatus.classList.toggle("ready", value.youdaoCredentialsConfigured);
}

async function load() {
  const [response, preferences] = await Promise.all([
    callNative({ action: "get_settings" }),
    chrome.storage.local.get({
      doubleClickLookupEnabled: true,
      autoOpenPdfEnabled: true,
    }),
  ]);
  applySettings(response && response.ok ? response : DEFAULTS);
  elements.doubleClickLookup.checked = preferences.doubleClickLookupEnabled;
  elements.autoOpenPdf.checked = preferences.autoOpenPdfEnabled;
  if (!response || !response.ok) showMessage("请保存设置并配置百度凭据。", true);
}

async function saveBrowserPreferences() {
  await chrome.storage.local.set({
    doubleClickLookupEnabled: elements.doubleClickLookup.checked,
    autoOpenPdfEnabled: elements.autoOpenPdf.checked,
  });
  showMessage("浏览体验设置已保存。");
}

async function browse(target) {
  const input = target === "chapter" ? elements.chapterFile : elements.newsFile;
  const response = await callNative({ action: "browse_file", target, initialPath: input.value });
  if (!response || response.status === "cancelled") return;
  if (!response.ok) return showMessage(response.message || "选择文件失败", true);
  input.value = response.path;
  if (target === "chapter") populateChapters(response.chapters, response.chapters.at(-1));
  showMessage("文件已选择，保存后生效。");
}

async function save() {
  showMessage("正在保存…");
  const response = await callNative({
    action: "save_settings",
    chapterFile: elements.chapterFile.value,
    newsFile: elements.newsFile.value,
    selectedChapter: Number(elements.chapter.value),
    appId: elements.appId.value,
    secretKey: elements.secretKey.value,
    youdaoAppKey: elements.youdaoAppKey.value,
    youdaoSecretKey: elements.youdaoSecretKey.value,
  });
  if (!response || !response.ok) return showMessage((response && response.message) || "保存失败", true);
  elements.appId.value = "";
  elements.secretKey.value = "";
  elements.youdaoAppKey.value = "";
  elements.youdaoSecretKey.value = "";
  applySettings(response);
  showMessage("设置已保存，右键菜单已更新。");
}

async function testYoudaoDictionary() {
  elements.youdaoPreview.hidden = true;
  elements.youdaoPreview.textContent = "";
  showMessage("正在查询有道词典…");
  const response = await callNative({
    action: "test_youdao_dictionary",
    text: elements.youdaoTestWord.value,
  });
  if (!response || !response.ok) {
    return showMessage((response && response.message) || "有道词典测试失败", true);
  }
  elements.youdaoPreview.textContent = ClipperUi.formatYoudaoPreview(response.preview);
  elements.youdaoPreview.hidden = false;
  showMessage(response.message || "有道词典查询成功。");
}

async function testConnection() {
  showMessage("正在测试词典、百度翻译和文件访问…");
  const response = await callNative({ action: "test_connection" });
  showMessage((response && response.message) || "测试失败", !response || !response.ok);
}

document.querySelectorAll("[data-browse]").forEach((button) => {
  button.addEventListener("click", () => browse(button.dataset.browse));
});
document.querySelector("#save").addEventListener("click", save);
document.querySelector("#test").addEventListener("click", testConnection);
document.querySelector("#test-youdao").addEventListener("click", testYoudaoDictionary);
elements.doubleClickLookup.addEventListener("change", saveBrowserPreferences);
elements.autoOpenPdf.addEventListener("change", saveBrowserPreferences);
load();
