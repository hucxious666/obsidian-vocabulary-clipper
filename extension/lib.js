(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClipperUi = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function normalizeSettings(settings) {
    const value = settings || {};
    const selectedSection = value.selectedSection
      || `Chapter ${Number(value.selectedChapter) || 22}`;
    const sections = Array.isArray(value.sections)
      ? value.sections.map(String)
      : (value.chapters || []).map((chapter) => `Chapter ${chapter}`);
    const dictionaries = Array.isArray(value.dictionaries)
      ? value.dictionaries.map((dictionary) => ({
        id: String(dictionary.id || ""),
        name: String(dictionary.name || dictionary.id || "离线词典"),
        installed: Boolean(dictionary.installed),
      }))
      : [];
    return {
      sectionFile: value.sectionFile || value.chapterFile || "",
      appendFile: value.appendFile || value.newsFile || "",
      selectedSection,
      sections,
      activeDictionary: String(value.activeDictionary || value.dictionaryId || "ecdict"),
      dictionaries,
    };
  }

  function dictionarySourceLabel(definition) {
    const value = definition || {};
    if (value.sourceName) return String(value.sourceName);
    const source = value.sourceId || value.source;
    if (source === "baidu") return "百度翻译";
    if (source === "kaikki-en") return "Kaikki English";
    if (source === "ecdict") return "ECDICT";
    return "离线词典";
  }

  function normalizeMeaningStyle(value) {
    return value === "plain" ? "plain" : "covered";
  }

  function meaningStyleBadge(value) {
    return normalizeMeaningStyle(value) === "plain" ? "明" : "";
  }

  function createMeaningBadgeController(options) {
    const setTimer = options.setTimer || ((callback, delay) => setTimeout(callback, delay));
    async function sync() {
      await options.setBackground("#c05a16");
      await options.setText(meaningStyleBadge(await options.readStyle()));
    }
    async function showSuccess() {
      await options.setBackground("#16803a");
      await options.setText("✓");
      setTimer(() => sync(), 1600);
    }
    return { showSuccess, sync };
  }

  function withMeaningStyle(payload, value) {
    const writeActions = new Set(["add_entry", "create_section_and_add_entry"]);
    return writeActions.has(payload && payload.action)
      ? { ...payload, meaningStyle: normalizeMeaningStyle(value) }
      : payload;
  }

  function canForwardNativeAction(action, senderUrl, optionsUrl) {
    return action !== "open_dictionary_manager" || senderUrl === optionsUrl;
  }

  function nativeProtocolMismatch(response, expectedVersion) {
    if (!response) return false;
    if (response.ok) return Number(response.protocolVersion) !== expectedVersion;
    return response.status === "invalid" && response.message === "不支持的操作";
  }

  function menuTitles(settings, meaningStyle = "covered") {
    const value = normalizeSettings(settings);
    const suffix = normalizeMeaningStyle(meaningStyle) === "plain" ? "（明文）" : "";
    return {
      section: `加入 ${value.selectedSection}${suffix}`,
      append: `添加到笔记末尾${suffix}`,
    };
  }

  function safeMessage(response) {
    const value = response && typeof response.message === "string" ? response.message : "操作失败";
    return value.slice(0, 200);
  }

  function eventOccursWithin(event, host) {
    const path = event && typeof event.composedPath === "function" ? event.composedPath() : [];
    return path.includes(host) || host.contains(event && event.target);
  }

  function shouldDismissPopover(event, host, activeElement) {
    if (event && event.type === "scroll" && activeElement && activeElement.tagName === "SELECT") {
      return false;
    }
    return !eventOccursWithin(event, host);
  }

  function shouldHandleSelectionEvent(event, host, popoverOpen) {
    if (event && event.type === "selectionchange") return !popoverOpen;
    return !eventOccursWithin(event, host);
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

  function formatTranslationPreview(preview) {
    if (!preview || typeof preview.sourceText !== "string") return "";
    const source = preview.source === "youdao" ? "有道翻译" : "百度翻译";
    return `${preview.sourceText}\n→ ${preview.translatedText || ""}\n来源：${source}`;
  }

  function normalizeLookupText(value) {
    const edge = /^[\s"“”‘’()[\]{}<>.,;:!?，。；：！？、]+|[\s"“”‘’()[\]{}<>.,;:!?，。；：！？、]+$/g;
    const text = String(value || "").normalize("NFC").replace(edge, "").replace(/\s+/g, " ");
    return /^[A-Za-z]+(?:['’-][A-Za-z]+)*$/.test(text) && text.length <= 120 ? text : "";
  }

  function normalizeTranslationText(value) {
    const text = String(value || "").normalize("NFC").trim().replace(/\s+/g, " ");
    const hasNonEnglishLetter = Array.from(text).some(
      (character) => /\p{L}/u.test(character) && !/[A-Za-z]/.test(character),
    );
    if (!text || text.length > 500 || hasNonEnglishLetter) {
      return "";
    }
    const words = text.match(/[A-Za-z]+(?:['’-][A-Za-z]+)*/g) || [];
    return words.length >= 2 ? text : "";
  }

  function classifySelection(value) {
    const definition = normalizeLookupText(value);
    if (definition) return { mode: "definition", text: definition };
    const translation = normalizeTranslationText(value);
    return translation ? { mode: "translation", text: translation } : null;
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

  function createSelectionDispatcher(onAction, timers = {}) {
    const setTimer = timers.set || ((callback, delay) => setTimeout(callback, delay));
    const clearTimer = timers.clear || ((timer) => clearTimeout(timer));
    let pendingTimer = null;
    return {
      schedule(readSelection, context, delay = 0) {
        if (pendingTimer !== null) clearTimer(pendingTimer);
        pendingTimer = setTimer(() => {
          pendingTimer = null;
          const selection = readSelection();
          const action = classifySelection(selection ? selection.toString() : "");
          if (action) onAction(action, selection, context);
        }, delay);
      },
    };
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
    canForwardNativeAction,
    classifySelection,
    createMeaningBadgeController,
    createSelectionDispatcher,
    createNativeClient,
    dictionarySourceLabel,
    formatTranslationPreview,
    hasPdfBypass,
    isSafePdfSource,
    meaningStyleBadge,
    menuTitles,
    nativeProtocolMismatch,
    normalizeMeaningStyle,
    normalizeSettings,
    normalizeLookupText,
    notificationFor,
    positionPopover,
    safeMessage,
    shouldDismissPopover,
    shouldHandleSelectionEvent,
    shouldRedirectPdf,
    withMeaningStyle,
    wordAtOffset,
  };
});
