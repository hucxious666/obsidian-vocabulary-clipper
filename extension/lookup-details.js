(function (root) {
  "use strict";

  const LABELS = {
    tag: "学习标签",
    collins: "柯林斯星级",
    oxford: "牛津核心词",
    bnc: "BNC 词频",
    frq: "当代词频",
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function groupSection(title, groups) {
    if (!Array.isArray(groups) || !groups.length) return null;
    const section = element("section", "lookup-extra");
    section.append(element("h3", "lookup-extra-title", title));
    const list = document.createElement("ul");
    for (const group of groups) {
      for (const definition of group.definitions || []) {
        list.append(element("li", "", definition));
      }
    }
    section.append(list);
    return section;
  }

  function exampleSection(examples) {
    if (!Array.isArray(examples) || !examples.length) return null;
    const section = element("section", "lookup-extra lookup-examples");
    section.append(element("h3", "lookup-extra-title", "例句"));
    const list = document.createElement("ol");
    for (const example of examples.slice(0, 6)) {
      const item = element("li", "", example.text || "");
      if (example.translation) item.append(element("small", "", example.translation));
      list.append(item);
    }
    section.append(list);
    return section;
  }

  function metadataSection(metadata) {
    const values = Object.entries(metadata || {}).filter(([, value]) => value);
    if (!values.length) return null;
    const section = element("div", "lookup-metadata");
    for (const [key, value] of values) {
      section.append(element("span", "lookup-meta", `${LABELS[key] || key}：${value}`));
    }
    return section;
  }

  function render(definition) {
    return [
      groupSection("英文释义", definition && definition.englishGroups),
      exampleSection(definition && definition.examples),
      metadataSection(definition && definition.metadata),
    ].filter(Boolean);
  }

  root.LookupDetails = { render };
})(typeof globalThis !== "undefined" ? globalThis : this);
