const linkForm = document.querySelector("#linkForm");
const urlInput = document.querySelector("#urlInput");
const pasteButton = document.querySelector("#pasteButton");
const loadButton = document.querySelector("#loadButton");
const appStatus = document.querySelector("#appStatus");
const workspace = document.querySelector("#workspace");
const message = document.querySelector("#message");
const videoTitle = document.querySelector("#videoTitle");
const durationLabel = document.querySelector("#durationLabel");
const videoList = document.querySelector("#videoList");
const selectAllButton = document.querySelector("#selectAllButton");
const downloadSelectedButton = document.querySelector("#downloadSelectedButton");
const downloadFrame = document.querySelector("#downloadFrame");

let currentVideo = null;
let previewTimers = new Map();
let waitingForDownloadResponse = false;
let activeDownloadButton = null;
let bulkSubmitting = false;

function setStatus(text) {
  appStatus.textContent = text;
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function setLoading(isLoading) {
  loadButton.disabled = isLoading;
  loadButton.textContent = isLoading ? "Cargando..." : "Cargar";
}

function secondsToTime(value) {
  if (!Number.isFinite(value)) return "";
  const total = Math.floor(value);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function clearPreviewTimers() {
  previewTimers.forEach((timer) => clearInterval(timer));
  previewTimers = new Map();
}

function node(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function option(label, value) {
  return new Option(label, value);
}

function mediaFormats(mediaIndex) {
  const filtered = (currentVideo?.formats || []).filter(
    (format) => String(format.mediaIndex || "1") === String(mediaIndex),
  );
  return filtered.length ? filtered : currentVideo?.formats || [];
}

function updatePlayerControls(refs) {
  refs.playPauseButton.textContent = refs.video.paused ? "Play" : "Pause";
  refs.muteButton.textContent = refs.video.muted || refs.video.volume === 0 ? "Muted" : "Vol";
  const duration = Number.isFinite(refs.video.duration) ? refs.video.duration : currentVideo?.duration || 0;
  const current = Number.isFinite(refs.video.currentTime) ? refs.video.currentTime : 0;
  refs.seekSlider.value = duration ? String(Math.round((current / duration) * 1000)) : "0";
  refs.timeReadout.textContent = `${secondsToTime(current)} / ${secondsToTime(duration) || "0:00"}`;
}

function setStageSize(stage, videoData) {
  const previewWidth = Number(videoData?.width || currentVideo?.previewWidth) || 16;
  const previewHeight = Number(videoData?.height || currentVideo?.previewHeight) || 9;
  stage.style.aspectRatio = `${previewWidth} / ${previewHeight}`;
  stage.classList.toggle("is-vertical", previewHeight > previewWidth);
}

function resetPreview(refs) {
  refs.video.hidden = true;
  refs.video.removeAttribute("src");
  refs.video.removeAttribute("poster");
  refs.video.load();
  refs.controls.hidden = true;
  refs.seekSlider.value = "0";
  refs.timeReadout.textContent = `0:00 / ${currentVideo?.duration ? secondsToTime(currentVideo.duration) : "0:00"}`;
  refs.thumbnail.hidden = !refs.thumbnailSrc;
  refs.thumbnail.removeAttribute("src");
  if (refs.thumbnailSrc) {
    refs.thumbnail.src = refs.thumbnailSrc;
    refs.video.poster = refs.thumbnailSrc;
  }
  refs.loader.hidden = false;
  refs.loader.textContent = "Preparando vista previa...";
}

function populateQualitySelect(select, mediaIndex) {
  select.innerHTML = "";
  select.append(option("Mejor calidad disponible", "bestvideo+bestaudio/best"));
  mediaFormats(mediaIndex).forEach((format) => {
    select.append(option(format.label, format.id));
  });
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "No se pudo completar la accion.");
  return data;
}

async function pollPreview(refs) {
  const existingTimer = previewTimers.get(refs.mediaIndex);
  if (existingTimer) clearInterval(existingTimer);

  const timer = setInterval(async () => {
    try {
      const response = await fetch(
        `/api/preview-status?token=${encodeURIComponent(currentVideo.token)}&media=${encodeURIComponent(refs.mediaIndex)}`,
      );
      const data = await response.json();
      if (data.status === "ready") {
        clearInterval(timer);
        previewTimers.delete(refs.mediaIndex);
        const separator = data.url.includes("?") ? "&" : "?";
        refs.video.src = `${data.url}${separator}preview=${Date.now()}`;
        refs.video.hidden = false;
        refs.thumbnail.hidden = !refs.thumbnailSrc;
        refs.loader.hidden = true;
        refs.controls.hidden = false;
        updatePlayerControls(refs);
        refs.video.addEventListener(
          "loadeddata",
          () => {
            refs.thumbnail.hidden = true;
            updatePlayerControls(refs);
          },
          { once: true },
        );
        refs.video.addEventListener(
          "playing",
          () => {
            refs.thumbnail.hidden = true;
          },
          { once: true },
        );
        setStatus("Vista previa lista");
      }
      if (data.status === "error") {
        clearInterval(timer);
        previewTimers.delete(refs.mediaIndex);
        refs.loader.textContent = "Vista previa no disponible";
        setStatus("Listo");
      }
    } catch {
      clearInterval(timer);
      previewTimers.delete(refs.mediaIndex);
      refs.loader.textContent = "Vista previa no disponible";
      setStatus("Listo");
    }
  }, 1200);

  previewTimers.set(refs.mediaIndex, timer);
}

async function loadPreview(refs) {
  resetPreview(refs);
  await api("/api/preview", { token: currentVideo.token, media: refs.mediaIndex });
  pollPreview(refs);
}

function wirePlayerControls(refs) {
  refs.playPauseButton.addEventListener("click", async () => {
    try {
      if (refs.video.paused) {
        await refs.video.play();
      } else {
        refs.video.pause();
      }
    } catch {
      setMessage("La vista previa todavia no esta lista para reproducirse. Intenta de nuevo en unos segundos.", true);
    }
    updatePlayerControls(refs);
  });

  refs.muteButton.addEventListener("click", () => {
    refs.video.muted = !refs.video.muted;
    updatePlayerControls(refs);
  });

  refs.volumeSlider.addEventListener("input", () => {
    refs.video.volume = Number(refs.volumeSlider.value);
    refs.video.muted = refs.video.volume === 0;
    updatePlayerControls(refs);
  });

  refs.seekSlider.addEventListener("input", () => {
    const duration = Number.isFinite(refs.video.duration) ? refs.video.duration : 0;
    if (duration) refs.video.currentTime = (Number(refs.seekSlider.value) / 1000) * duration;
    updatePlayerControls(refs);
  });

  refs.video.addEventListener("click", () => refs.playPauseButton.click());
  refs.video.addEventListener("play", () => updatePlayerControls(refs));
  refs.video.addEventListener("pause", () => updatePlayerControls(refs));
  refs.video.addEventListener("timeupdate", () => updatePlayerControls(refs));
  refs.video.addEventListener("durationchange", () => updatePlayerControls(refs));
  refs.video.addEventListener("volumechange", () => updatePlayerControls(refs));
  refs.video.addEventListener("error", () => {
    refs.loader.hidden = false;
    refs.loader.textContent = "Vista previa no disponible";
  });
}

function createPreviewPanel(videoData) {
  const previewPanel = node("div", "preview-panel");
  const stage = node("div", "video-stage");
  const thumbnail = node("img");
  const video = node("video");
  const loader = node("div", "loader", "Preparando vista previa...");
  const controls = node("div", "custom-controls");
  const playPauseButton = node("button", "", "Play");
  const seekSlider = node("input");
  const timeReadout = node("span", "time-readout", "0:00 / 0:00");
  const muteButton = node("button", "", "Vol");
  const volumeSlider = node("input");
  const meta = node("div", "video-meta");
  const selectLabel = node("label", "media-select");
  const selectInput = node("input");
  const titleWrap = node("div");

  thumbnail.alt = "";
  thumbnail.hidden = true;
  video.playsInline = true;
  video.hidden = true;
  controls.hidden = true;
  playPauseButton.type = "button";
  playPauseButton.setAttribute("aria-label", "Reproducir");
  muteButton.type = "button";
  muteButton.setAttribute("aria-label", "Silenciar");
  seekSlider.type = "range";
  seekSlider.min = "0";
  seekSlider.max = "1000";
  seekSlider.value = "0";
  seekSlider.setAttribute("aria-label", "Progreso");
  volumeSlider.type = "range";
  volumeSlider.min = "0";
  volumeSlider.max = "1";
  volumeSlider.step = "0.05";
  volumeSlider.value = "1";
  volumeSlider.setAttribute("aria-label", "Volumen");
  selectInput.type = "checkbox";
  selectInput.className = "media-check";
  selectInput.checked = true;
  selectInput.setAttribute("aria-label", `Seleccionar ${videoData.label || `Video ${videoData.id}`}`);

  controls.append(playPauseButton, seekSlider, timeReadout, muteButton, volumeSlider);
  setStageSize(stage, videoData);
  stage.append(thumbnail, video, loader, controls);

  const title = node("h3", "", videoData.label || `Video ${videoData.id}`);
  const size = videoData.width && videoData.height ? `${videoData.width}x${videoData.height}` : "";
  titleWrap.append(title, node("span", "", size));
  selectLabel.append(selectInput, node("span", "", "Incluir"));
  meta.append(titleWrap, selectLabel);
  previewPanel.append(stage, meta);

  const refs = {
    mediaIndex: String(videoData.id || "1"),
    stage,
    thumbnail,
    video,
    loader,
    controls,
    playPauseButton,
    muteButton,
    seekSlider,
    volumeSlider,
    timeReadout,
    selectInput,
    thumbnailSrc: videoData.thumbnail || "",
  };
  wirePlayerControls(refs);
  return { previewPanel, refs };
}

function createDownloadPanel(videoData, refs) {
  const form = node("form", "download-panel");
  const tokenInput = node("input");
  const mediaInput = node("input");
  const qualityLabel = node("label", "field-label", "Calidad");
  const qualitySelect = node("select");
  const rangeHead = node("div", "range-head");
  const fullButton = node("button", "", "Todo el video");
  const timeGrid = node("div", "time-grid");
  const startLabel = node("label");
  const endLabel = node("label");
  const startInput = node("input");
  const endInput = node("input");
  const hint = node("p", "hint");
  const downloadButton = node("button", "download-button", "Descargar");

  form.method = "post";
  form.action = "/download";
  form.target = "downloadFrame";
  tokenInput.type = "hidden";
  tokenInput.name = "token";
  tokenInput.value = currentVideo.token;
  mediaInput.type = "hidden";
  mediaInput.name = "media";
  mediaInput.value = String(videoData.id || "1");
  qualitySelect.name = "format";
  qualitySelect.id = `quality-${videoData.id}`;
  qualityLabel.htmlFor = qualitySelect.id;
  fullButton.type = "button";
  startInput.name = "start";
  startInput.type = "text";
  startInput.inputMode = "numeric";
  startInput.placeholder = "0:00";
  endInput.name = "end";
  endInput.type = "text";
  endInput.inputMode = "numeric";
  endInput.placeholder = "final";
  downloadButton.type = "submit";

  populateQualitySelect(qualitySelect, videoData.id);
  rangeHead.append(node("span", "", "Rango"), fullButton);
  startLabel.append(node("span", "", "Desde"), startInput);
  endLabel.append(node("span", "", "Hasta"), endInput);
  timeGrid.append(startLabel, endLabel);

  if (currentVideo.canTrim) {
    hint.textContent = "Usa 1:23 o 00:01:23. Dejalo vacio para descargar completo.";
  } else {
    startInput.disabled = true;
    endInput.disabled = true;
    hint.textContent = "El recorte necesita ffmpeg. En este equipo la app descargara el video completo.";
  }

  fullButton.addEventListener("click", () => {
    startInput.value = "";
    endInput.value = "";
  });

  form.addEventListener("submit", () => {
    waitingForDownloadResponse = true;
    activeDownloadButton = downloadButton;
    downloadButton.disabled = true;
    downloadButton.textContent = "Enviando...";
    setStatus("Descargando");
    if (!bulkSubmitting) {
      setMessage("Descarga enviada al navegador. Si el video requiere recorte o merge, puede tardar un poco en aparecer.");
    }
    setTimeout(() => {
      downloadButton.disabled = false;
      downloadButton.textContent = "Descargar";
      setStatus("Listo");
    }, 2500);
  });

  form.append(tokenInput, mediaInput, qualityLabel, qualitySelect, rangeHead, timeGrid, hint, downloadButton);
  refs.form = form;
  refs.downloadButton = downloadButton;
  return form;
}

function createMediaCard(videoData) {
  const item = node("section", "media-item");
  const { previewPanel, refs } = createPreviewPanel(videoData);
  const downloadPanel = createDownloadPanel(videoData, refs);
  refs.selectInput.addEventListener("change", updateSelectionButtons);
  item.append(previewPanel, downloadPanel);
  item.refs = refs;
  return item;
}

function mediaCards() {
  return [...videoList.querySelectorAll(".media-item")];
}

function selectedMediaCards() {
  return mediaCards().filter((card) => card.refs?.selectInput?.checked);
}

function updateSelectionButtons() {
  const cards = mediaCards();
  const selectedCount = selectedMediaCards().length;
  const allSelected = cards.length > 0 && selectedCount === cards.length;
  selectAllButton.textContent = allSelected ? "Limpiar seleccion" : "Seleccionar todos";
  selectAllButton.disabled = cards.length === 0;
  downloadSelectedButton.disabled = selectedCount === 0;
  downloadSelectedButton.textContent = selectedCount > 1 ? `Descargar ${selectedCount} seleccionados` : "Descargar seleccionados";
}

function showVideo(data) {
  currentVideo = data;
  clearPreviewTimers();
  workspace.hidden = false;
  videoTitle.textContent = data.title;
  durationLabel.textContent = data.durationLabel || "";
  videoList.innerHTML = "";

  const videos = data.videos?.length ? data.videos : [{ id: "1", label: "Video 1", width: 16, height: 9 }];
  workspace.classList.toggle("is-single", videos.length === 1);
  workspace.classList.toggle("is-grid", videos.length > 1);
  videoList.classList.toggle("is-single", videos.length === 1);
  videoList.classList.toggle("is-grid", videos.length > 1);
  videos.forEach((videoData) => {
    const card = createMediaCard(videoData);
    videoList.append(card);
    loadPreview(card.refs).catch((error) => {
      card.refs.loader.textContent = "Vista previa no disponible";
      setMessage(error.message, true);
    });
  });
  updateSelectionButtons();
}

linkForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  setStatus("Buscando");
  setMessage("");
  try {
    const data = await api("/api/info", { url: urlInput.value.trim() });
    showVideo(data);
    setStatus("Calidades encontradas");
    const count = data.videos?.length || 1;
    const resolverNote = data.resolver === "x2twitter" ? " Video restringido resuelto con URLs directas de media." : "";
    const pluralNote = count > 1 ? ` Se encontraron ${count} videos en este post.` : "";
    setMessage(`Descarga cada video desde su propio bloque.${pluralNote}${resolverNote}`);
  } catch (error) {
    setStatus("Error");
    setMessage(error.message, true);
  } finally {
    setLoading(false);
  }
});

pasteButton.addEventListener("click", async () => {
  setMessage("");
  try {
    const text = await navigator.clipboard.readText();
    urlInput.value = text.trim();
    urlInput.focus();
  } catch {
    setMessage("No pude leer el clipboard. Pega el enlace con Ctrl+V.", true);
  }
});

selectAllButton.addEventListener("click", () => {
  const cards = mediaCards();
  const shouldSelect = selectedMediaCards().length !== cards.length;
  cards.forEach((card) => {
    card.refs.selectInput.checked = shouldSelect;
  });
  updateSelectionButtons();
});

downloadSelectedButton.addEventListener("click", async () => {
  const selected = selectedMediaCards();
  if (!selected.length) {
    setMessage("Selecciona al menos un video para descargar.", true);
    return;
  }
  downloadSelectedButton.disabled = true;
  bulkSubmitting = selected.length > 1;
  setStatus("Descargando");
  setMessage(
    selected.length > 1
      ? "Enviando descargas seleccionadas. El navegador puede pedir permiso para varias descargas."
      : "Enviando descarga seleccionada al navegador.",
  );

  try {
    for (const card of selected) {
      card.refs.form.requestSubmit();
      await new Promise((resolve) => {
        setTimeout(resolve, 1200);
      });
    }
  } finally {
    bulkSubmitting = false;
  }

  setTimeout(() => {
    updateSelectionButtons();
  }, 2600);
});

downloadFrame.addEventListener("load", () => {
  if (!waitingForDownloadResponse) return;
  try {
    const text = downloadFrame.contentDocument?.body?.textContent?.trim();
    if (!text) return;
    const data = JSON.parse(text);
    if (data.error) {
      setStatus("Error");
      setMessage(data.error, true);
    }
  } catch {
    return;
  } finally {
    waitingForDownloadResponse = false;
    if (activeDownloadButton) {
      activeDownloadButton.disabled = false;
      activeDownloadButton.textContent = "Descargar";
      activeDownloadButton = null;
    }
  }
});
