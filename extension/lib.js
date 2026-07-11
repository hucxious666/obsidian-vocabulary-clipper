(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClipperUi = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function menuTitles(settings) {
    const chapter = Number(settings && settings.selectedChapter) || 22;
    return { chapter: `加入 Chapter ${chapter}`, news: "加入 NEWS" };
  }

  function safeMessage(response) {
    const value = response && typeof response.message === "string" ? response.message : "操作失败";
    return value.slice(0, 200);
  }

  function notificationFor(response) {
    if (response && response.ok && response.status === "added") return null;
    const status = response && response.status;
    const titles = {
      duplicate: "未写入：词汇已存在",
      invalid: "选词或设置无效",
      lookup_failed: "词汇添加失败",
      conflict: "文件正在变化",
      write_failed: "Markdown 写入失败",
    };
    return { title: titles[status] || "词汇添加失败", message: safeMessage(response) };
  }

  function formatYoudaoPreview(preview) {
    if (!preview || typeof preview.word !== "string") return "";
    const phonetic = typeof preview.phonetic === "string" && preview.phonetic
      ? ` /${preview.phonetic.replace(/^\/+|\/+$/g, "")}/`
      : "";
    const explains = Array.isArray(preview.explains)
      ? preview.explains.filter((item) => typeof item === "string" && item.trim())
      : [];
    return [`${preview.word}${phonetic}`, ...explains.map((item) => `• ${item.trim()}`)].join("\n");
  }

  function normalizeLookupText(value) {
    const edge = /^[\s"“”‘’()[\]{}<>.,;:!?，。；：！？、]+|[\s"“”‘’()[\]{}<>.,;:!?，。；：！？、]+$/g;
    const text = String(value || "").normalize("NFC").replace(edge, "").replace(/\s+/g, " ");
    return /^[A-Za-z]+(?:['’-][A-Za-z]+)*$/.test(text) && text.length <= 120 ? text : "";
  }

  function isSecondLeftMouseUp(event) {
    return Boolean(event && event.button === 0 && event.detail === 2);
  }

  function wordAtOffset(value, offset) {
    const text = String(value || "");
    const isWordCharacter = (character) => /[A-Za-z'’-]/.test(character || "");
    let cursor = Math.min(Math.max(Number(offset) || 0, 0), text.length);
    if (!isWordCharacter(text[cursor]) && isWordCharacter(text[cursor - 1])) cursor -= 1;
    if (!isWordCharacter(text[cursor])) return "";
    let start = cursor;
    let end = cursor + 1;
    while (start > 0 && isWordCharacter(text[start - 1])) start -= 1;
    while (end < text.length && isWordCharacter(text[end])) end += 1;
    return normalizeLookupText(text.slice(start, end));
  }

  function selectionWordForDisplay(state) {
    if (!state || !state.enabled) return "";
    return normalizeLookupText(state.selectedText);
  }

  function scheduleLookupFromSelection(readSelection, onLookup, schedule) {
    const defer = schedule || ((callback) => setTimeout(callback, 0));
    defer(() => {
      const selection = readSelection();
      const word = normalizeLookupText(selection ? selection.toString() : "");
      if (word) onLookup(word, selection);
    });
  }

  function positionPopover(rect, popover, viewport) {
    const gap = 8;
    const margin = 12;
    const left = Math.min(
      Math.max(margin, viewport.width - popover.width - margin),
      Math.max(margin, rect.left + (rect.right - rect.left - popover.width) / 2),
    );
    const below = viewport.height - rect.bottom;
    const useBelow = below >= popover.height + gap || below >= rect.top;
    const rawTop = useBelow ? rect.bottom + gap : rect.top - popover.height - gap;
    const top = Math.min(
      Math.max(margin, viewport.height - popover.height - margin),
      Math.max(margin, rawTop),
    );
    return { left: Math.round(left), top: Math.round(top), placement: useBelow ? "below" : "above" };
  }

  function isSafePdfSource(value) {
    try {
      return ["http:", "https:", "file:"].includes(new URL(value).protocol);
    } catch (_error) {
      return false;
    }
  }

  function addPdfBypass(value) {
    const url = new URL(value);
    const fragment = new URLSearchParams(url.hash.slice(1));
    fragment.set("ovcNative", "1");
    url.hash = fragment.toString();
    return url.toString();
  }

  function hasPdfBypass(value) {
    try {
      return new URLSearchParams(new URL(value).hash.slice(1)).get("ovcNative") === "1";
    } catch (_error) {
      return false;
    }
  }

  function shouldRedirectPdf(state) {
    return Boolean(state && state.autoOpen && state.topLevel && state.hasPdfEmbed && !state.bypass);
  }

  function createNativeClient(connect, idFactory) {
    const pending = new Map();
    const makeId = idFactory || (() => crypto.randomUUID());
    let port = null;
    function ensurePort() {
      if (port) return port;
      port = connect();
      port.onMessage.addListener((response) => {
        const request = pending.get(response && response.requestId);
        if (!request) return;
        pending.delete(response.requestId);
        request.resolve(response);
      });
      port.onDisconnect.addListener(() => {
        port = null;
        for (const request of pending.values()) request.reject(new Error("本地服务连接已断开"));
        pending.clear();
      });
      return port;
    }
    return {
      send(payload) {
        const requestId = makeId();
        return new Promise((resolve, reject) => {
          pending.set(requestId, { resolve, reject });
          try {
            ensurePort().postMessage({ ...payload, requestId });
          } catch (error) {
            pending.delete(requestId);
            port = null;
            reject(error);
          }
        });
      },
    };
  }

  return {
    addPdfBypass,
    createNativeClient,
    formatYoudaoPreview,
    hasPdfBypass,
    isSafePdfSource,
    isSecondLeftMouseUp,
    menuTitles,
    normalizeLookupText,
    notificationFor,
    positionPopover,
    safeMessage,
    scheduleLookupFromSelection,
    selectionWordForDisplay,
    shouldRedirectPdf,
    wordAtOffset,
  };
});
