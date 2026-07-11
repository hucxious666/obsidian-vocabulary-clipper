const assert = require("assert");
const ui = require("../../extension/lib.js");

function eventChannel() {
  const listeners = [];
  return {
    addListener(listener) { listeners.push(listener); },
    emit(value) { for (const listener of listeners) listener(value); },
  };
}

assert.deepStrictEqual(ui.menuTitles({ selectedChapter: 22 }), {
  chapter: "加入 Chapter 22",
  news: "加入 NEWS",
});

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

assert.strictEqual(
  ui.formatYoudaoPreview({
    word: "ignominious",
    phonetic: "ˌɪɡnəˈmɪniəs",
    explains: ["adj. 可耻的", "adj. 不名誉的"],
  }),
  "ignominious /ˌɪɡnəˈmɪniəs/\n• adj. 可耻的\n• adj. 不名誉的",
);
assert.strictEqual(ui.formatYoudaoPreview(null), "");

assert.strictEqual(ui.normalizeLookupText("  “well-being,”  "), "well-being");
assert.strictEqual(ui.normalizeLookupText("two words"), "");
assert.strictEqual(ui.normalizeLookupText("中文"), "");
assert.strictEqual(ui.isSecondLeftMouseUp({ button: 0, detail: 2 }), true);
assert.strictEqual(ui.isSecondLeftMouseUp({ button: 0, detail: 1 }), false);
assert.strictEqual(ui.isSecondLeftMouseUp({ button: 2, detail: 2 }), false);
const ordinaryText = "Double-click ordinary words.";
assert.strictEqual(
  ui.wordAtOffset(ordinaryText, ordinaryText.indexOf("ordinary") + 3),
  "ordinary",
);
assert.strictEqual(ui.wordAtOffset("well-being works", 5), "well-being");
assert.strictEqual(ui.selectionWordForDisplay({
  enabled: true,
  selectedText: "Liverpool",
}), "Liverpool");
assert.strictEqual(ui.selectionWordForDisplay({
  enabled: true,
  selectedText: "two words",
}), "");
assert.strictEqual(ui.selectionWordForDisplay({
  enabled: false,
  selectedText: "Liverpool",
}), "");

let selectedText = "";
let scheduledLookup = null;
let lookedUpWord = "";
ui.scheduleLookupFromSelection(
  () => ({ toString: () => selectedText }),
  (word) => { lookedUpWord = word; },
  (callback) => { scheduledLookup = callback; },
);
assert.strictEqual(lookedUpWord, "");
selectedText = "ordinary";
scheduledLookup();
assert.strictEqual(lookedUpWord, "ordinary");

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

testNativeClient().then(() => console.log("extension lib tests passed"));
