const elements = {
  container: document.querySelector("#viewer-container"),
  viewer: document.querySelector("#viewer"),
  pageNumber: document.querySelector("#page-number"),
  pageCount: document.querySelector("#page-count"),
  status: document.querySelector("#viewer-status"),
  zoomOut: document.querySelector("#zoom-out"),
  zoomIn: document.querySelector("#zoom-in"),
  fitWidth: document.querySelector("#fit-width"),
  download: document.querySelector("#download"),
  openNative: document.querySelector("#open-native"),
};

const sourceUrl = new URLSearchParams(location.search).get("src") || "";
const sendNative = (payload) => chrome.runtime.sendMessage({ kind: "native", payload });
const popover = new LookupPopover(sendNative);
let pdfDocument = null;
let pdfViewer = null;
let pdfjsLib = null;
let viewerLibrary = null;
let lastSelectionPoint = { clientX: 0, clientY: 0 };
let lastSelectionAction = { at: 0, key: "" };
const selectionDispatcher = ClipperUi.createSelectionDispatcher(handleSelectionAction);

function showStatus(message, error = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", error);
}

function selectionAnchor(selection, event) {
  if (selection && selection.rangeCount) {
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    if (rect.width || rect.height) return rect;
  }
  return { left: event.clientX, right: event.clientX, top: event.clientY, bottom: event.clientY };
}

function handleSelectionAction(action, selection, point) {
  const now = Date.now();
  const key = `${action.mode}:${action.text}`;
  if (lastSelectionAction.key === key && now - lastSelectionAction.at < 800) return;
  lastSelectionAction = { at: now, key };
  const anchor = selectionAnchor(selection, point);
  if (action.mode === "translation") popover.translate(action.text, anchor);
  else popover.lookup(action.text, anchor);
}

function queueSelection(point, delay = 0) {
  selectionDispatcher.schedule(() => window.getSelection(), point, delay);
}

function bindLookup() {
  window.addEventListener("mousedown", (event) => {
    if (event.button !== 0) return;
    lastSelectionPoint = { clientX: event.clientX, clientY: event.clientY };
  }, true);
  document.addEventListener("selectionchange", () => {
    queueSelection(lastSelectionPoint, 200);
  }, true);
  window.addEventListener("mouseup", (event) => {
    if (event.button !== 0) return;
    lastSelectionPoint = { clientX: event.clientX, clientY: event.clientY };
    queueSelection(lastSelectionPoint);
  }, true);
  document.addEventListener("dblclick", (event) => {
    lastSelectionPoint = { clientX: event.clientX, clientY: event.clientY };
    queueSelection(lastSelectionPoint);
  }, true);
}

function bindToolbar(eventBus) {
  eventBus.on("pagechanging", ({ pageNumber }) => {
    elements.pageNumber.value = String(pageNumber);
  });
  const goToPage = () => {
    const requested = Number(elements.pageNumber.value);
    if (Number.isInteger(requested) && requested >= 1 && requested <= pdfDocument.numPages) {
      pdfViewer.currentPageNumber = requested;
    }
  };
  elements.pageNumber.addEventListener("change", goToPage);
  elements.pageNumber.addEventListener("keydown", (event) => {
    if (event.key === "Enter") goToPage();
  });
  elements.zoomOut.addEventListener("click", () => pdfViewer.decreaseScale());
  elements.zoomIn.addEventListener("click", () => pdfViewer.increaseScale());
  elements.fitWidth.addEventListener("click", () => { pdfViewer.currentScaleValue = "page-width"; });
  elements.download.addEventListener("click", downloadPdf);
  elements.openNative.addEventListener("click", () => { location.href = ClipperUi.addPdfBypass(sourceUrl); });
}

async function downloadPdf() {
  if (!pdfDocument) return;
  elements.download.disabled = true;
  try {
    const data = await pdfDocument.getData();
    const objectUrl = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = decodeURIComponent(new URL(sourceUrl).pathname.split("/").pop()) || "document.pdf";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } finally {
    elements.download.disabled = false;
  }
}

async function loadPdf() {
  if (!ClipperUi.isSafePdfSource(sourceUrl)) {
    showStatus("PDF 地址无效", true);
    elements.openNative.disabled = true;
    return;
  }
  pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("vendor/pdfjs/build/pdf.worker.min.js");
  const eventBus = new viewerLibrary.EventBus();
  const linkService = new viewerLibrary.PDFLinkService({ eventBus });
  pdfViewer = new viewerLibrary.PDFViewer({
    container: elements.container,
    viewer: elements.viewer,
    eventBus,
    linkService,
    textLayerMode: 1,
  });
  linkService.setViewer(pdfViewer);
  bindToolbar(eventBus);
  eventBus.on("pagesinit", () => { pdfViewer.currentScaleValue = "page-width"; });
  try {
    const loadingTask = pdfjsLib.getDocument({
      url: sourceUrl,
      withCredentials: true,
      cMapUrl: chrome.runtime.getURL("vendor/pdfjs/cmaps/"),
      cMapPacked: true,
      standardFontDataUrl: chrome.runtime.getURL("vendor/pdfjs/standard_fonts/"),
      wasmUrl: chrome.runtime.getURL("vendor/pdfjs/wasm/"),
      iccUrl: chrome.runtime.getURL("vendor/pdfjs/iccs/"),
    });
    pdfDocument = await loadingTask.promise;
    elements.pageCount.textContent = String(pdfDocument.numPages);
    elements.pageNumber.max = String(pdfDocument.numPages);
    linkService.setDocument(pdfDocument, null);
    pdfViewer.setDocument(pdfDocument);
    showStatus("选中英文单词查看释义，选中英文句子进行翻译");
  } catch (error) {
    showStatus(`PDF 加载失败：${error && error.message ? error.message : "未知错误"}`, true);
  }
}

async function bootstrap() {
  pdfjsLib = await import("./vendor/pdfjs/build/pdf.min.js");
  globalThis.pdfjsLib = pdfjsLib;
  viewerLibrary = await import("./vendor/pdfjs/web/pdf_viewer.js");
  bindLookup();
  await loadPdf();
}

bootstrap().catch((error) => {
  showStatus(`阅读器启动失败：${error && error.message ? error.message : "未知错误"}`, true);
});
