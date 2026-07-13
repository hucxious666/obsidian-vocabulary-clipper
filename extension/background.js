importScripts("lib.js");

const HOST_NAME = "com.local.obsidian_vocabulary_clipper";
const MENU_SECTION = "add-to-section";
const MENU_APPEND = "append-to-note";
const nativeClient = ClipperUi.createNativeClient(() => chrome.runtime.connectNative(HOST_NAME));

async function loadMeaningStyle() {
  const settings = await chrome.storage.local.get({ meaningStyle: "covered" });
  return ClipperUi.normalizeMeaningStyle(settings.meaningStyle);
}

const badgeController = ClipperUi.createMeaningBadgeController({
  readStyle: loadMeaningStyle,
  setBackground: (color) => chrome.action.setBadgeBackgroundColor({ color }),
  setText: (text) => chrome.action.setBadgeText({ text }),
});

async function sendNative(payload) {
  try {
    const request = ClipperUi.withMeaningStyle(payload, await loadMeaningStyle());
    return await nativeClient.send(request);
  } catch (error) {
    return { ok: false, status: "write_failed", message: "无法连接本地服务，请重新运行安装脚本" };
  }
}

async function loadSettings() {
  const response = await sendNative({ action: "get_settings" });
  if (response && response.ok) {
    const settings = ClipperUi.normalizeSettings(response);
    await chrome.storage.local.set(settings);
    return response;
  }
  const cached = await chrome.storage.local.get({
    selectedSection: "Chapter 22",
    sections: ["Chapter 22"],
  });
  return cached;
}

async function syncMenus() {
  const [settings, meaningStyle] = await Promise.all([loadSettings(), loadMeaningStyle()]);
  const titles = ClipperUi.menuTitles(settings, meaningStyle);
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({ id: MENU_SECTION, title: titles.section, contexts: ["selection"] });
  chrome.contextMenus.create({ id: MENU_APPEND, title: titles.append, contexts: ["selection"] });
}

async function syncModeBadge() {
  await badgeController.sync();
}

async function showSuccess() {
  await badgeController.showSuccess();
}

async function showResult(response) {
  const notification = ClipperUi.notificationFor(response);
  if (!notification) {
    await showSuccess();
    return;
  }
  await chrome.notifications.create({
    type: "basic",
    iconUrl: chrome.runtime.getURL("icon.png"),
    title: notification.title,
    message: notification.message,
  });
}

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== MENU_SECTION && info.menuItemId !== MENU_APPEND) return;
  const target = info.menuItemId === MENU_SECTION ? "section" : "append";
  const response = await sendNative({ action: "add_entry", target, text: info.selectionText || "" });
  await showResult(response);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.kind === "open_pdf_viewer") {
    if (!ClipperUi.isSafePdfSource(message.sourceUrl) || !sender.tab || !sender.tab.id) {
      sendResponse({ ok: false, status: "invalid", message: "PDF 地址无效" });
      return false;
    }
    const viewer = chrome.runtime.getURL("viewer.html");
    chrome.tabs.update(sender.tab.id, {
      url: `${viewer}?src=${encodeURIComponent(message.sourceUrl)}`,
    }).then(
      () => sendResponse({ ok: true, status: "ok" }),
      () => sendResponse({ ok: false, status: "write_failed", message: "无法打开 PDF 阅读器" }),
    );
    return true;
  }
  if (!message || message.kind !== "native" || typeof message.payload !== "object") return false;
  const optionsUrl = chrome.runtime.getURL("options.html");
  if (!ClipperUi.canForwardNativeAction(message.payload.action, sender.url || "", optionsUrl)) {
    sendResponse({ ok: false, status: "invalid", message: "词典下载器只能从扩展设置页打开" });
    return false;
  }
  sendNative(message.payload).then((response) => {
    sendResponse(response);
    const settingsActions = new Set([
      "save_settings", "select_dictionary", "select_section",
      "create_section", "create_section_and_add_entry",
    ]);
    if (response && response.ok && settingsActions.has(message.payload.action)) void syncMenus();
    if (["add_entry", "create_section_and_add_entry"].includes(message.payload.action)) {
      void showResult(response);
    }
  });
  return true;
});

async function initializeUi() {
  await Promise.all([syncMenus(), syncModeBadge()]);
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.meaningStyle) void initializeUi();
});
chrome.runtime.onInstalled.addListener(initializeUi);
chrome.runtime.onStartup.addListener(initializeUi);
void initializeUi();
