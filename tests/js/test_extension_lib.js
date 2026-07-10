const assert = require("assert");
const ui = require("../../extension/lib.js");

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

console.log("extension lib tests passed");
