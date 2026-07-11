(function (root) {
  "use strict";

  class LookupPopover {
    constructor(sendNative) {
      this.sendNative = sendNative;
      this.sequence = 0;
      this.anchor = null;
      this.host = document.createElement("div");
      this.host.id = "obsidian-vocabulary-lookup";
      this.host.dataset.ovcVersion = chrome.runtime.getManifest().version;
      this.host.style.setProperty("all", "initial", "important");
      this.host.style.setProperty("position", "fixed", "important");
      this.host.style.setProperty("z-index", "2147483647", "important");
      this.host.style.setProperty("visibility", "visible", "important");
      this.host.style.setProperty("opacity", "1", "important");
      this.host.style.setProperty("pointer-events", "auto", "important");
      this.host.style.setProperty("display", "none", "important");
      this.shadow = this.host.attachShadow({ mode: "closed" });
      this.card = document.createElement("section");
      this.card.className = "lookup-card";
      this.card.setAttribute("role", "dialog");
      this.card.setAttribute("aria-label", "词汇释义或翻译");
      const stylesheet = document.createElement("link");
      stylesheet.rel = "stylesheet";
      stylesheet.href = chrome.runtime.getURL("lookup-popover.css");
      stylesheet.addEventListener("load", () => this.position());
      this.shadow.append(stylesheet, this.card);
      document.documentElement.append(this.host);
      this.bindDismissal();
    }

    bindDismissal() {
      document.addEventListener("mousedown", (event) => {
        if (this.host.style.display !== "none" && !this.host.contains(event.target)) this.close();
      }, true);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") this.close();
      }, true);
      window.addEventListener("scroll", (event) => {
        if (!this.host.contains(event.target)) this.close();
      }, true);
      window.addEventListener("resize", () => this.close());
    }

    async lookup(word, anchor) {
      const request = ++this.sequence;
      this.anchor = anchor;
      this.renderLoading(word);
      try {
        const response = await this.sendNative({ action: "lookup_definition", text: word });
        if (request !== this.sequence) return;
        if (!response || !response.ok) {
          this.renderError(word, response && response.message);
          return;
        }
        await this.renderDefinition(response.definition, request);
      } catch (_error) {
        if (request === this.sequence) this.renderError(word, "无法连接本地服务，请重新运行安装脚本");
      }
    }

    async translate(text, anchor) {
      const request = ++this.sequence;
      this.anchor = anchor;
      this.renderLoading(text, "正在翻译…", "lookup-original");
      try {
        const response = await this.sendNative({ action: "translate_selection", text });
        if (request !== this.sequence) return;
        if (!response || !response.ok) {
          this.renderError(text, response && response.message);
          return;
        }
        this.renderTranslation(response.translation);
      } catch (_error) {
        if (request === this.sequence) this.renderError(text, "无法连接本地翻译服务");
      }
    }

    renderLoading(word, message = "正在查询释义…", className = "lookup-word") {
      this.card.replaceChildren();
      const title = this.element("strong", className, word);
      const loading = this.element("div", "lookup-loading", message);
      this.card.append(title, loading);
      this.open();
    }

    renderError(word, message) {
      this.card.replaceChildren();
      const header = this.element("header", "lookup-header");
      header.append(this.element("strong", "lookup-word", word), this.closeButton());
      const error = this.element("div", "lookup-error", message || "词典中没有该单词的释义");
      this.card.append(header, error);
      this.open();
    }

    async renderDefinition(definition, request) {
      this.card.replaceChildren();
      const header = this.element("header", "lookup-header");
      const heading = this.element("div", "lookup-heading");
      heading.append(
        this.element("strong", "lookup-word", definition.word || ""),
        this.element("span", "lookup-phonetic", definition.phonetic ? `/${definition.phonetic}/` : ""),
      );
      header.append(heading, this.closeButton());
      const groups = this.element("div", "lookup-groups");
      for (const group of definition.groups || []) groups.append(this.definitionGroup(group));
      const chapter = await chrome.storage.local.get({ selectedChapter: 22 });
      if (request !== this.sequence) return;
      const status = this.element("div", "lookup-status");
      status.setAttribute("role", "status");
      const actions = this.element("footer", "lookup-actions");
      actions.append(
        this.actionButton(`加入 Chapter ${chapter.selectedChapter}`, "chapter", definition.word, status),
        this.actionButton("加入 NEWS", "news", definition.word, status),
      );
      const source = this.element("div", "lookup-source", definition.source === "baidu" ? "来源：百度翻译" : "来源：ECDICT");
      this.card.append(header, groups, source, status, actions);
      this.open();
    }

    renderTranslation(translation) {
      this.card.replaceChildren();
      const header = this.element("header", "lookup-header");
      header.append(
        this.element("div", "lookup-original", translation.sourceText || ""),
        this.closeButton(),
      );
      const translated = this.element(
        "div", "lookup-translation", translation.translatedText || "",
      );
      const sourceName = translation.source === "youdao" ? "有道翻译" : "百度翻译";
      const source = this.element("div", "lookup-source", `来源：${sourceName}`);
      this.card.append(header, translated, source);
      this.open();
    }

    definitionGroup(group) {
      const section = this.element("section", "lookup-group");
      section.append(this.element("div", "lookup-pos", group.partOfSpeech || "其他"));
      const list = document.createElement("ul");
      for (const definition of group.definitions || []) {
        const item = document.createElement("li");
        item.textContent = definition;
        list.append(item);
      }
      section.append(list);
      return section;
    }

    actionButton(label, target, word, status) {
      const button = this.element("button", "lookup-action", label);
      button.type = "button";
      button.addEventListener("click", async () => {
        const buttons = this.card.querySelectorAll("button.lookup-action");
        for (const item of buttons) item.disabled = true;
        status.textContent = "正在写入…";
        try {
          const response = await this.sendNative({ action: "add_entry", target, text: word });
          status.textContent = response && response.message ? response.message : "写入失败";
        } catch (_error) {
          status.textContent = "无法连接本地服务";
        } finally {
          for (const item of buttons) item.disabled = false;
        }
      });
      return button;
    }

    closeButton() {
      const button = this.element("button", "lookup-close", "×");
      button.type = "button";
      button.setAttribute("aria-label", "关闭释义");
      button.addEventListener("click", () => this.close());
      return button;
    }

    element(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text) node.textContent = text;
      return node;
    }

    open() {
      this.host.style.setProperty("display", "block", "important");
      requestAnimationFrame(() => this.position());
    }

    position() {
      if (!this.anchor || this.host.style.display === "none") return;
      const size = this.card.getBoundingClientRect();
      const result = ClipperUi.positionPopover(
        this.anchor,
        { width: size.width || 360, height: size.height || 260 },
        { width: window.innerWidth, height: window.innerHeight },
      );
      this.host.style.setProperty("left", `${result.left}px`, "important");
      this.host.style.setProperty("top", `${result.top}px`, "important");
      this.card.dataset.placement = result.placement;
    }

    close() {
      this.sequence += 1;
      this.host.style.setProperty("display", "none", "important");
      this.card.replaceChildren();
      this.anchor = null;
    }
  }

  root.LookupPopover = LookupPopover;
})(typeof globalThis !== "undefined" ? globalThis : this);
