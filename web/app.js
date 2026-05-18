const linkForm = document.querySelector("#linkForm");
const downloadForm = document.querySelector("#downloadForm");
const urlInput = document.querySelector("#urlInput");
const pasteButton = document.querySelector("#pasteButton");
const loadButton = document.querySelector("#loadButton");
const appStatus = document.querySelector("#appStatus");
const workspace = document.querySelector("#workspace");
const message = document.querySelector("#message");
const videoTitle = document.querySelector("#videoTitle");
const durationLabel = document.querySelector("#durationLabel");
const thumbnail = document.querySelector("#thumbnail");
const videoPlayer = document.querySelector("#videoPlayer");
const previewLoader = document.querySelector("#previewLoader");
const videoStage = document.querySelector("#videoStage");
const qualitySelect = document.querySelector("#qualitySelect");
const tokenInput = document.querySelector("#tokenInput");
const startInput = document.querySelector("#startInput");
const endInput = document.querySelector("#endInput");
const fullButton = document.querySelector("#fullButton");
const trimHint = document.querySelector("#trimHint");
const downloadButton = document.querySelector("#downloadButton");
const customControls = document.querySelector("#customControls");
const playPauseButton = document.querySelector("#playPauseButton");
const muteButton = document.querySelector("#muteButton");
const seekSlider = document.querySelector("#seekSlider");
const volumeSlider = document.querySelector("#volumeSlider");
const timeReadout = document.querySelector("#timeReadout");

let currentVideo = null;
let previewTimer = null;

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

function updatePlayerControls() {
  playPauseButton.textContent = videoPlayer.paused ? "Play" : "Pause";
  muteButton.textContent = videoPlayer.muted || videoPlayer.volume === 0 ? "Muted" : "Vol";
  const duration = Number.isFinite(videoPlayer.duration) ? videoPlayer.duration : currentVideo?.duration || 0;
  const current = Number.isFinite(videoPlayer.currentTime) ? videoPlayer.currentTime : 0;
  seekSlider.value = duration ? String(Math.round((current / duration) * 1000)) : "0";
  timeReadout.textContent = `${secondsToTime(current)} / ${secondsToTime(duration) || "0:00"}`;
}

function showVideo(data) {
  currentVideo = data;
  workspace.hidden = false;
  const previewWidth = Number(data.previewWidth) || 16;
  const previewHeight = Number(data.previewHeight) || 9;
  videoStage.style.aspectRatio = `${previewWidth} / ${previewHeight}`;
  videoStage.classList.toggle("is-vertical", previewHeight > previewWidth);
  tokenInput.value = data.token;
  videoTitle.textContent = data.title;
  durationLabel.textContent = data.durationLabel || "";
  startInput.value = "";
  endInput.value = data.duration ? secondsToTime(data.duration) : "";

  videoPlayer.hidden = true;
  videoPlayer.removeAttribute("src");
  videoPlayer.removeAttribute("poster");
  videoPlayer.load();
  customControls.hidden = true;
  seekSlider.value = "0";
  timeReadout.textContent = `0:00 / ${data.duration ? secondsToTime(data.duration) : "0:00"}`;
  thumbnail.hidden = !data.thumbnail;
  if (data.thumbnail) {
    thumbnail.src = data.thumbnail;
    videoPlayer.poster = data.thumbnail;
  }
  previewLoader.hidden = false;
  previewLoader.textContent = "Preparando vista previa...";

  qualitySelect.innerHTML = "";
  const best = new Option("Mejor calidad disponible", "bestvideo+bestaudio/best");
  qualitySelect.append(best);
  data.formats.forEach((format) => {
    qualitySelect.append(new Option(format.label, format.id));
  });

  if (data.canTrim) {
    startInput.disabled = false;
    endInput.disabled = false;
    trimHint.textContent = "Usa 1:23 o 00:01:23. Dejalo vacio para descargar completo.";
  } else {
    startInput.disabled = true;
    endInput.disabled = true;
    trimHint.textContent = "El recorte necesita ffmpeg. En este equipo la app descargara el video completo.";
  }
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

async function pollPreview(token) {
  clearInterval(previewTimer);
  previewTimer = setInterval(async () => {
    try {
      const response = await fetch(`/api/preview-status?token=${encodeURIComponent(token)}`);
      const data = await response.json();
      if (data.status === "ready") {
        clearInterval(previewTimer);
        const separator = data.url.includes("?") ? "&" : "?";
        videoPlayer.src = `${data.url}${separator}preview=${Date.now()}`;
        videoPlayer.hidden = false;
        thumbnail.hidden = false;
        previewLoader.hidden = true;
        customControls.hidden = false;
        updatePlayerControls();
        videoPlayer.addEventListener(
          "loadeddata",
          () => {
            thumbnail.hidden = true;
            updatePlayerControls();
          },
          { once: true },
        );
        videoPlayer.addEventListener(
          "playing",
          () => {
            thumbnail.hidden = true;
          },
          { once: true },
        );
        setStatus("Vista previa lista");
      }
      if (data.status === "error") {
        clearInterval(previewTimer);
        previewLoader.textContent = "Vista previa no disponible";
        setStatus("Listo");
      }
    } catch {
      clearInterval(previewTimer);
      previewLoader.textContent = "Vista previa no disponible";
      setStatus("Listo");
    }
  }, 1200);
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
    const resolverNote = data.resolver === "x2twitter" ? " Video restringido resuelto con URLs directas de media." : "";
    setMessage(`Elige calidad y rango. La descarga se guardara donde tu navegador guarde descargas.${resolverNote}`);
    await api("/api/preview", { token: data.token });
    pollPreview(data.token);
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

playPauseButton.addEventListener("click", async () => {
  try {
    if (videoPlayer.paused) {
      await videoPlayer.play();
    } else {
      videoPlayer.pause();
    }
  } catch {
    setMessage("La vista previa todavia no esta lista para reproducirse. Intenta de nuevo en unos segundos.", true);
  }
  updatePlayerControls();
});

muteButton.addEventListener("click", () => {
  videoPlayer.muted = !videoPlayer.muted;
  updatePlayerControls();
});

volumeSlider.addEventListener("input", () => {
  videoPlayer.volume = Number(volumeSlider.value);
  videoPlayer.muted = videoPlayer.volume === 0;
  updatePlayerControls();
});

seekSlider.addEventListener("input", () => {
  const duration = Number.isFinite(videoPlayer.duration) ? videoPlayer.duration : 0;
  if (duration) videoPlayer.currentTime = (Number(seekSlider.value) / 1000) * duration;
  updatePlayerControls();
});

videoPlayer.addEventListener("click", () => playPauseButton.click());
videoPlayer.addEventListener("play", updatePlayerControls);
videoPlayer.addEventListener("pause", updatePlayerControls);
videoPlayer.addEventListener("timeupdate", updatePlayerControls);
videoPlayer.addEventListener("durationchange", updatePlayerControls);
videoPlayer.addEventListener("volumechange", updatePlayerControls);
videoPlayer.addEventListener("error", () => {
  setMessage("El navegador no pudo reproducir la vista previa. La descarga puede funcionar igual.", true);
});

fullButton.addEventListener("click", () => {
  startInput.value = "";
  endInput.value = currentVideo?.duration ? secondsToTime(currentVideo.duration) : "";
});

downloadForm.addEventListener("submit", () => {
  downloadButton.disabled = true;
  downloadButton.textContent = "Enviando...";
  setStatus("Descargando");
  setMessage("Descarga enviada al navegador. Si el video requiere recorte o merge, puede tardar un poco en aparecer.");
  setTimeout(() => {
    downloadButton.disabled = false;
    downloadButton.textContent = "Descargar";
    setStatus("Listo");
  }, 2500);
});
