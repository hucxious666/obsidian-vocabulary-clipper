(function () {
  "use strict";

  let preferences = { doubleClickLookupEnabled: true, autoOpenPdfEnabled: true };
  let lastPointer = { clientX: 0, clientY: 0 };
  let lastLookup = { at: 0, key: "" };
  const sendNative = (payload) => chrome.runtime.sendMessage({ kind: "native", payload });
  const popover = new LookupPopover(sendNative);
  const selectionDispatcher = ClipperUi.createSelectionDispatcher(handleSelectionAction);

  function isTopLevelPdf() {
    if (window.top !== window) return false;
    if (document.contentType === "application/pdf") return true;
    const pdf = document.querySelector('embed[type="application/pdf"], object[type="application/pdf"]');
    if (!pdf || !document.body) return false;
    return document.body.children.length === 1 || pdf.getBoundingClientRect().height >= innerHeight * 0.8;
  }

  function redirectPdfIfNeeded() {
    const shouldRedirect = ClipperUi.shouldRedirectPdf({
      autoOpen: preferences.autoOpenPdfEnabled,
      topLevel: window.top === window,
      hasPdfEmbed: isTopLevelPdf(),
      bypass: ClipperUi.hasPdfBypass(location.href),
    });
    if (!shouldRedirect || !ClipperUi.isSafePdfSource(location.href)) return false;
    chrome.runtime.sendMessage({ kind: "open_pdf_viewer", sourceUrl: location.href });
    return true;
  }

  function selectionAnchor(selection, event) {
    if (selection && selection.rangeCount) {
      const rect = selection.getRangeAt(0).getBoundingClientRect();
      if (rect.width || rect.height) return rect;
    }
    return { left: event.clientX, right: event.clientX, top: event.clientY, bottom: event.clientY };
  }

  function wordAtPoint(point) {
    const caret = document.caretPositionFromPoint
      ? document.caretPositionFromPoint(point.clientX, point.clientY)
      : document.caretRangeFromPoint
        ? document.caretRangeFromPoint(point.clientX, point.clientY)
        : null;
    const node = caret && (caret.offsetNode || caret.startContainer);
    const offset = caret && (caret.offset ?? caret.startOffset);
    if (!node || node.nodeType !== Node.TEXT_NODE) return "";
    return ClipperUi.wordAtOffset(node.nodeValue, offset);
  }

  function selectionAtPoint(point) {
    const selection = window.getSelection();
    if (ClipperUi.classifySelection(selection ? selection.toString() : "")) return selection;
    return { rangeCount: 0, toString: () => wordAtPoint(point) };
  }

  function handleSelectionAction(action, selection, point) {
    const now = Date.now();
    const key = `${action.mode}:${action.text}`;
    if (!preferences.doubleClickLookupEnabled || (lastLookup.key === key && now - lastLookup.at < 800)) return;
    lastLookup = { at: now, key };
    const anchor = selectionAnchor(selection, point);
    if (action.mode === "translation") popover.translate(action.text, anchor);
    else popover.lookup(action.text, anchor);
  }

  function queueLookup(point, readSelection, delay = 0) {
    selectionDispatcher.schedule(readSelection, point, delay);
  }

  window.addEventListener("mousedown", (event) => {
    if (
      event.button !== 0
      || !ClipperUi.shouldHandleSelectionEvent(event, popover.host, popover.isOpen())
    ) return;
    lastPointer = { clientX: event.clientX, clientY: event.clientY };
  }, true);

  document.addEventListener("selectionchange", (event) => {
    if (!ClipperUi.shouldHandleSelectionEvent(event, popover.host, popover.isOpen())) return;
    queueLookup(lastPointer, () => window.getSelection(), 200);
  }, true);

  window.addEventListener("mouseup", (event) => {
    if (
      event.button !== 0
      || !ClipperUi.shouldHandleSelectionEvent(event, popover.host, popover.isOpen())
    ) return;
    const point = { clientX: event.clientX, clientY: event.clientY };
    queueLookup(point, () => window.getSelection());
  }, true);

  window.addEventListener("dblclick", (event) => {
    if (!ClipperUi.shouldHandleSelectionEvent(event, popover.host, popover.isOpen())) return;
    const point = { clientX: event.clientX, clientY: event.clientY };
    queueLookup(point, () => selectionAtPoint(point));
  }, true);

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    for (const key of Object.keys(preferences)) {
      if (changes[key]) preferences[key] = Boolean(changes[key].newValue);
    }
  });

  chrome.storage.local.get(preferences).then((stored) => {
    preferences = stored;
    if (redirectPdfIfNeeded()) return;
    const observer = new MutationObserver(() => {
      if (redirectPdfIfNeeded()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), 5000);
  });
})();
