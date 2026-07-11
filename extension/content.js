(function () {
  "use strict";

  let preferences = { doubleClickLookupEnabled: true, autoOpenPdfEnabled: true };
  let lastPointer = { clientX: 0, clientY: 0 };
  let lastLookup = { at: 0, word: "" };
  const sendNative = (payload) => chrome.runtime.sendMessage({ kind: "native", payload });
  const popover = new LookupPopover(sendNative);

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
    if (ClipperUi.normalizeLookupText(selection ? selection.toString() : "")) return selection;
    return { rangeCount: 0, toString: () => wordAtPoint(point) };
  }

  function queueLookup(point, readSelection) {
    ClipperUi.scheduleLookupFromSelection(
      readSelection,
      (word, selection) => {
        const now = Date.now();
        const selectedWord = ClipperUi.selectionWordForDisplay({
          enabled: preferences.doubleClickLookupEnabled,
          selectedText: word,
        });
        if (!selectedWord || (lastLookup.word === selectedWord && now - lastLookup.at < 800)) return;
        lastLookup = { at: now, word: selectedWord };
        popover.lookup(selectedWord, selectionAnchor(selection, point));
      },
      (callback) => requestAnimationFrame(callback),
    );
  }

  window.addEventListener("mousedown", (event) => {
    if (event.button !== 0) return;
    lastPointer = { clientX: event.clientX, clientY: event.clientY };
  }, true);

  document.addEventListener("selectionchange", () => {
    queueLookup(lastPointer, () => window.getSelection());
  }, true);

  window.addEventListener("mouseup", (event) => {
    if (event.button !== 0) return;
    const point = { clientX: event.clientX, clientY: event.clientY };
    queueLookup(point, () => window.getSelection());
  }, true);

  window.addEventListener("dblclick", (event) => {
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
