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

  return { formatYoudaoPreview, menuTitles, notificationFor, safeMessage };
});
