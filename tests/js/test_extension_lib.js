const assert = require("assert");
const ui = require("../../extension/lib.js");

function eventChannel() {
  const listeners = [];
  return {
    addListener(listener) { listeners.push(listener); },
    emit(value) { for (const listener of listeners) listener(value); },
  };
}

assert.deepStrictEqual(ui.menuTitles({ selectedSection: "Match Review" }), {
  section: "加入 Match Review",
  append: "添加到笔记末尾",
});
assert.deepStrictEqual(ui.menuTitles({ selectedSection: "Match Review" }, "plain"), {
  section: "加入 Match Review（明文）",
  append: "添加到笔记末尾（明文）",
});
assert.strictEqual(ui.normalizeMeaningStyle("plain"), "plain");
assert.strictEqual(ui.normalizeMeaningStyle("covered"), "covered");
assert.strictEqual(ui.normalizeMeaningStyle("unexpected"), "covered");
assert.strictEqual(ui.meaningStyleBadge("plain"), "明");
assert.strictEqual(ui.meaningStyleBadge("covered"), "");
assert.deepStrictEqual(
  ui.withMeaningStyle({ action: "add_entry", target: "append", text: "word" }, "plain"),
  { action: "add_entry", target: "append", text: "word", meaningStyle: "plain" },
);
assert.deepStrictEqual(
  ui.withMeaningStyle({ action: "create_section_and_add_entry", text: "word" }, "plain"),
  { action: "create_section_and_add_entry", text: "word", meaningStyle: "plain" },
);
assert.deepStrictEqual(
  ui.withMeaningStyle({ action: "lookup_definition", text: "word" }, "plain"),
  { action: "lookup_definition", text: "word" },
);
assert.deepStrictEqual(ui.normalizeSettings({
  chapterFile: "chapter.md",
  newsFile: "news.md",
  selectedChapter: 22,
  chapters: [21, 22],
}), {
  sectionFile: "chapter.md",
  appendFile: "news.md",
  selectedSection: "Chapter 22",
  sections: ["Chapter 21", "Chapter 22"],
  activeDictionary: "ecdict",
  dictionaries: [],
});

assert.deepStrictEqual(ui.normalizeSettings({
  selectedSection: "阅读",
  activeDictionary: "kaikki-en",
  dictionaries: [
    { id: "ecdict", name: "ECDICT", installed: true },
    { id: "kaikki-en", name: "Kaikki English", installed: false },
  ],
}), {
  sectionFile: "",
  appendFile: "",
  selectedSection: "阅读",
  sections: [],
  activeDictionary: "kaikki-en",
  dictionaries: [
    { id: "ecdict", name: "ECDICT", installed: true },
    { id: "kaikki-en", name: "Kaikki English", installed: false },
  ],
});
assert.strictEqual(ui.dictionarySourceLabel({ sourceName: "Kaikki English" }), "Kaikki English");
assert.strictEqual(ui.dictionarySourceLabel({ source: "baidu" }), "百度翻译");
assert.strictEqual(ui.dictionarySourceLabel({ sourceId: "ecdict" }), "ECDICT");
const optionsUrl = "chrome-extension://extension-id/options.html";
assert.strictEqual(ui.canForwardNativeAction(
  "open_dictionary_manager", optionsUrl, optionsUrl,
), true);
assert.strictEqual(ui.canForwardNativeAction(
  "open_dictionary_manager", "https://example.com/article", optionsUrl,
), false);
assert.strictEqual(ui.canForwardNativeAction(
  "lookup_definition", "https://example.com/article", optionsUrl,
), true);
assert.strictEqual(ui.nativeProtocolMismatch({ ok: true, protocolVersion: 2 }, 2), false);
assert.strictEqual(ui.nativeProtocolMismatch({ ok: true }, 2), true);
assert.strictEqual(ui.nativeProtocolMismatch({
  ok: false, status: "invalid", message: "不支持的操作",
}, 2), true);
assert.strictEqual(ui.nativeProtocolMismatch({
  ok: false, status: "write_failed", message: "连接失败",
}, 2), false);

assert.strictEqual(ui.notificationFor({ ok: true, status: "added" }), null);
assert.deepStrictEqual(ui.notificationFor({ ok: false, status: "duplicate", message: "已存在" }), {
  title: "未写入：词汇已存在",
  message: "已存在",
});
assert.deepStrictEqual(ui.notificationFor({ ok: false, status: "lookup_failed", message: "查询失败" }), {
  title: "词汇添加失败",
  message: "查询失败",
});

assert.strictEqual(ui.safeMessage({ message: "ok" }), "ok");
assert.strictEqual(ui.safeMessage({ message: "a".repeat(500) }).length, 200);

assert.strictEqual(typeof ui.shouldDismissPopover, "function");
const popoverHost = { contains: (target) => target === popoverHost };
const outsideTarget = {};
assert.strictEqual(ui.shouldDismissPopover(
  { type: "scroll", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  { tagName: "SELECT" },
), false);
assert.strictEqual(ui.shouldDismissPopover(
  { type: "mousedown", target: outsideTarget, composedPath: () => [{}, popoverHost, outsideTarget] },
  popoverHost,
  null,
), false);
assert.strictEqual(ui.shouldDismissPopover(
  { type: "mousedown", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  null,
), true);

assert.strictEqual(typeof ui.shouldHandleSelectionEvent, "function");
assert.strictEqual(ui.shouldHandleSelectionEvent(
  { type: "mouseup", target: outsideTarget, composedPath: () => [{}, popoverHost] },
  popoverHost,
  true,
), false);
assert.strictEqual(ui.shouldHandleSelectionEvent(
  { type: "mouseup", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  true,
), true);
assert.strictEqual(ui.shouldHandleSelectionEvent(
  { type: "selectionchange", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  true,
), false);
assert.strictEqual(ui.shouldHandleSelectionEvent(
  { type: "selectionchange", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  false,
), true);
assert.strictEqual(ui.shouldDismissPopover(
  { type: "mousedown", target: outsideTarget, composedPath: () => [outsideTarget] },
  popoverHost,
  { tagName: "SELECT" },
), true);

assert.strictEqual(
  ui.formatTranslationPreview({
    sourceText: "Liverpool are playing well.",
    translatedText: "利物浦踢得很好。",
    source: "youdao",
  }),
  "Liverpool are playing well.\n→ 利物浦踢得很好。\n来源：有道翻译",
);
assert.strictEqual(ui.formatTranslationPreview(null), "");

assert.strictEqual(ui.normalizeLookupText("  “well-being,”  "), "well-being");
assert.strictEqual(ui.normalizeLookupText("two words"), "");
assert.strictEqual(ui.normalizeLookupText("中文"), "");
assert.deepStrictEqual(ui.classifySelection(" player "), {
  mode: "definition",
  text: "player",
});
assert.deepStrictEqual(ui.classifySelection("Liverpool\nare playing well."), {
  mode: "translation",
  text: "Liverpool are playing well.",
});
assert.deepStrictEqual(ui.classifySelection("Liverpool won 2 games."), {
  mode: "translation",
  text: "Liverpool won 2 games.",
});
assert.strictEqual(ui.classifySelection("hello world 世界"), null);
assert.strictEqual(ui.classifySelection("hello world привет"), null);
assert.strictEqual(ui.classifySelection("one ".repeat(126)), null);
const ordinaryText = "Double-click ordinary words.";
assert.strictEqual(
  ui.wordAtOffset(ordinaryText, ordinaryText.indexOf("ordinary") + 3),
  "ordinary",
);
assert.strictEqual(ui.wordAtOffset("well-being works", 5), "well-being");
let selectedText = "";
let timerId = 0;
const pendingTimers = new Map();
const dispatchedActions = [];
const dispatcher = ui.createSelectionDispatcher(
  (action) => dispatchedActions.push(action),
  {
    set(callback) {
      const id = ++timerId;
      pendingTimers.set(id, callback);
      return id;
    },
    clear(id) { pendingTimers.delete(id); },
  },
);
selectedText = "ordinary words";
dispatcher.schedule(() => ({ toString: () => selectedText }), null, 200);
selectedText = "ordinary words in context";
dispatcher.schedule(() => ({ toString: () => selectedText }), null, 200);
for (const callback of pendingTimers.values()) callback();
assert.deepStrictEqual(dispatchedActions, [
  { mode: "translation", text: "ordinary words in context" },
]);

assert.deepStrictEqual(
  ui.positionPopover(
    { left: 760, right: 790, top: 700, bottom: 720 },
    { width: 360, height: 400 },
    { width: 800, height: 800 },
  ),
  { left: 428, top: 292, placement: "above" },
);
assert.deepStrictEqual(
  ui.positionPopover(
    { left: 0, right: 20, top: 0, bottom: 20 },
    { width: 360, height: 400 },
    { width: 320, height: 240 },
  ),
  { left: 12, top: 12, placement: "below" },
);

assert.strictEqual(ui.isSafePdfSource("https://example.com/a.pdf"), true);
assert.strictEqual(ui.isSafePdfSource("file:///D:/books/a.pdf"), true);
assert.strictEqual(ui.isSafePdfSource("javascript:alert(1)"), false);
const bypassedPdf = ui.addPdfBypass("https://example.com/a.pdf#page=3");
assert.strictEqual(ui.hasPdfBypass(bypassedPdf), true);
assert.strictEqual(bypassedPdf.includes("page=3"), true);
assert.strictEqual(
  ui.shouldRedirectPdf({ autoOpen: true, topLevel: true, hasPdfEmbed: true, bypass: false }),
  true,
);
assert.strictEqual(
  ui.shouldRedirectPdf({ autoOpen: true, topLevel: false, hasPdfEmbed: true, bypass: false }),
  false,
);

async function testNativeClient() {
  const ports = [];
  const posted = [];
  let nextId = 0;
  const connect = () => {
    const port = { onMessage: eventChannel(), onDisconnect: eventChannel() };
    port.postMessage = (message) => posted.push(message);
    ports.push(port);
    return port;
  };
  const client = ui.createNativeClient(connect, () => `request-${++nextId}`);

  const first = client.send({ action: "lookup_definition", text: "word" });
  assert.strictEqual(posted[0].requestId, "request-1");
  ports[0].onMessage.emit({ requestId: "request-1", ok: true });
  assert.deepStrictEqual(await first, { requestId: "request-1", ok: true });

  const disconnected = client.send({ action: "get_settings" });
  ports[0].onDisconnect.emit();
  await assert.rejects(disconnected, /本地服务连接已断开/);

  const reconnected = client.send({ action: "get_settings" });
  ports[1].onMessage.emit({ requestId: "request-3", ok: true });
  assert.strictEqual((await reconnected).ok, true);
  assert.strictEqual(ports.length, 2);
}

async function testMeaningBadgeController() {
  let meaningStyle = "covered";
  let scheduled = null;
  const badges = [];
  const controller = ui.createMeaningBadgeController({
    readStyle: async () => meaningStyle,
    setBackground: async (color) => badges.push({ kind: "color", value: color }),
    setText: async (value) => badges.push({ kind: "text", value }),
    setTimer: (callback) => { scheduled = callback; },
  });

  await controller.sync();
  assert.deepStrictEqual(badges.at(-1), { kind: "text", value: "" });
  await controller.showSuccess();
  assert.deepStrictEqual(badges.at(-1), { kind: "text", value: "✓" });
  meaningStyle = "plain";
  await scheduled();
  assert.deepStrictEqual(badges.at(-1), { kind: "text", value: "明" });
}

Promise.all([testNativeClient(), testMeaningBadgeController()])
  .then(() => console.log("extension lib tests passed"));
