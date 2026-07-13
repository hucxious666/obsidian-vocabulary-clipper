"use strict";

const styleInputs = Array.from(document.querySelectorAll('input[name="meaning-style"]'));
const currentSection = document.querySelector("#current-section");
const modeHint = document.querySelector("#mode-hint");

function applyState(settings) {
  const style = ClipperUi.normalizeMeaningStyle(settings.meaningStyle);
  const selected = styleInputs.find((input) => input.value === style);
  if (selected) selected.checked = true;
  currentSection.textContent = settings.selectedSection || "未选择";
  modeHint.textContent = style === "plain"
    ? "当前为明文模式，扩展图标会显示“明”。"
    : "当前为遮蔽模式。";
}

async function load() {
  const settings = await chrome.storage.local.get({
    meaningStyle: "covered",
    selectedSection: "Chapter 22",
  });
  applyState(settings);
}

for (const input of styleInputs) {
  input.addEventListener("change", async () => {
    if (!input.checked) return;
    const meaningStyle = ClipperUi.normalizeMeaningStyle(input.value);
    await chrome.storage.local.set({ meaningStyle: meaningStyle });
    applyState({ meaningStyle, selectedSection: currentSection.textContent });
  });
}

document.querySelector("#open-options").addEventListener("click", () => {
  void chrome.runtime.openOptionsPage();
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local") return;
  if (!changes.meaningStyle && !changes.selectedSection) return;
  void load();
});

void load();
