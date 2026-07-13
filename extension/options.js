const DEFAULTS = {
  sectionFile: "D:\\obsidian\\repository\\Workhouse\\study\\词汇积累-蒙蔽版.md",
  appendFile: "D:\\obsidian\\repository\\Workhouse\\study\\NEWS WORD - COVERED.md",
  selectedSection: "Chapter 22",
  sections: Array.from({ length: 22 }, (_, index) => `Chapter ${index + 1}`),
  credentialsConfigured: false,
  youdaoCredentialsConfigured: false,
  doubleClickLookupEnabled: true,
  autoOpenPdfEnabled: true,
};

const elements = {
  sectionFile: document.querySelector("#section-file"),
  appendFile: document.querySelector("#append-file"),
  section: document.querySelector("#section-select"),
  newSection: document.querySelector("#new-section"),
  appId: document.querySelector("#app-id"),
  secretKey: document.querySelector("#secret-key"),
  credentialStatus: document.querySelector("#credential-status"),
  youdaoAppKey: document.querySelector("#youdao-app-key"),
  youdaoSecretKey: document.querySelector("#youdao-secret-key"),
  youdaoCredentialStatus: document.querySelector("#youdao-credential-status"),
  youdaoTestText: document.querySelector("#youdao-test-text"),
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

function populateSections(sections, selected) {
  elements.section.replaceChildren();
  for (const value of sections || []) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    option.selected = String(value).toLocaleLowerCase() === String(selected).toLocaleLowerCase();
    elements.section.append(option);
  }
}

function applySettings(settings) {
  const raw = { ...DEFAULTS, ...(settings || {}) };
  const value = { ...raw, ...ClipperUi.normalizeSettings(raw) };
  elements.sectionFile.value = value.sectionFile;
  elements.appendFile.value = value.appendFile;
  populateSections(value.sections, value.selectedSection);
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
  const input = target === "section" ? elements.sectionFile : elements.appendFile;
  const response = await callNative({ action: "browse_file", target, initialPath: input.value });
  if (!response || response.status === "cancelled") return;
  if (!response.ok) return showMessage(response.message || "选择文件失败", true);
  input.value = response.path;
  if (target === "section") populateSections(response.sections, response.sections.at(-1));
  showMessage("文件已选择，保存后生效。");
}

async function save() {
  showMessage("正在保存…");
  const response = await callNative({
    action: "save_settings",
    sectionFile: elements.sectionFile.value,
    appendFile: elements.appendFile.value,
    selectedSection: elements.section.value,
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

async function createSection() {
  showMessage("正在新增章节…");
  const response = await callNative({
    action: "create_section",
    sectionName: elements.newSection.value,
  });
  if (!response || !response.ok) {
    return showMessage((response && response.message) || "新增章节失败", true);
  }
  elements.newSection.value = "";
  applySettings(response);
  showMessage(`已新增并选择章节：${response.selectedSection}`);
}

async function testYoudaoTranslation() {
  elements.youdaoPreview.hidden = true;
  elements.youdaoPreview.textContent = "";
  showMessage("正在调用有道文本翻译…");
  const response = await callNative({
    action: "test_youdao_translation",
    text: elements.youdaoTestText.value,
  });
  if (!response || !response.ok) {
    return showMessage((response && response.message) || "有道文本翻译测试失败", true);
  }
  elements.youdaoPreview.textContent = ClipperUi.formatTranslationPreview(response.preview);
  elements.youdaoPreview.hidden = false;
  showMessage(response.message || "有道文本翻译成功。");
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
document.querySelector("#create-section").addEventListener("click", createSection);
document.querySelector("#test").addEventListener("click", testConnection);
document.querySelector("#test-youdao").addEventListener("click", testYoudaoTranslation);
elements.doubleClickLookup.addEventListener("change", saveBrowserPreferences);
elements.autoOpenPdf.addEventListener("change", saveBrowserPreferences);
load();
