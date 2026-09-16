"use strict";

/**
 * Netcare Help Assistant front end.
 *
 * Interface strings, wake words and language metadata are fetched from /config
 * so a wording change is a JSON edit on the server, not a JavaScript change.
 * Speech recognition and speech synthesis use the browser's own APIs; no audio
 * is sent to the Flask application.
 */

const state = {
  sessionId: localStorage.getItem("netcare_chat_session") || null,
  lang: localStorage.getItem("netcare_lang") || "en",
  sizeIndex: Number(localStorage.getItem("netcare_size") || 0),
  voiceMode: true,
  speakAloud: localStorage.getItem("netcare_speak") !== "off",
  location: null,
  config: null
};

const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const typing = document.getElementById("typing");
const menuButton = document.getElementById("menuButton");
const restartButton = document.getElementById("restartButton");
const speechHelp = document.getElementById("speechHelp");
const languageSelect = document.getElementById("languageSelect");
const nearMeButton = document.getElementById("nearMeButton");
const speakToggle = document.getElementById("speakToggle");
const sizeToggle = document.getElementById("sizeToggle");
const themeToggle = document.getElementById("themeToggle");
const stopSpeakButton = document.getElementById("stopSpeakButton");

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const SIZES = ["normal", "large", "xlarge"];

let recognition = null;
let recognitionRunning = false;
let waitingForCommand = false;
let voiceSessionActive = false;
let speaking = false;
let recognitionRestartTimer = null;
let speechSupported = Boolean(SpeechRecognition);
let warnedAboutVoice = false;

/* ------------------------------------------------------------------ helpers */

function ui() {
  return (state.config && state.config.ui && state.config.ui[state.lang]) || {};
}

function langMeta() {
  const list = (state.config && state.config.languages) || [];
  return list.find((entry) => entry.code === state.lang) || { stt: "en-ZA", tts_prefix: "en", html_lang: "en-ZA" };
}

function setSpeechStatus(message) {
  speechHelp.textContent = message || "";
}

function normalizeSpeech(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s'-]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function wakeWords() {
  const all = (state.config && state.config.wake_words) || {};
  return all[state.lang] || all.en || [];
}

function stopWords() {
  const all = (state.config && state.config.stop_words) || {};
  return all[state.lang] || all.en || [];
}

function findTrigger(text) {
  const normalized = normalizeSpeech(text);
  for (const trigger of wakeWords()) {
    if (normalized === trigger) return { matched: true, command: "" };
    if (normalized.startsWith(`${trigger} `)) {
      return { matched: true, command: normalized.slice(trigger.length).trim() };
    }
  }
  return { matched: false, command: "" };
}

function isStopPhrase(text) {
  return stopWords().includes(normalizeSpeech(text));
}

/* ------------------------------------------------------- interface language */

function applyInterfaceLanguage() {
  const strings = ui();
  const meta = langMeta();
  const root = document.getElementById("rootHtml");

  root.setAttribute("lang", meta.html_lang || "en-ZA");
  setText("skipLink", strings.input_label);
  setText("eyebrow", strings.eyebrow);
  setText("pageTitle", strings.title);
  setText("noticeTitle", strings.notice_title);
  setText("noticeBody", strings.notice_body);
  setText("menuButton", strings.menu);
  setText("restartButton", strings.restart);
  setText("sendButton", strings.send);
  setText("inputLabel", strings.input_label);
  setText("languageLabel", strings.language);
  setText("typingLabel", strings.typing);
  setText("nearMeButton", strings.near_me);
  setText("speakToggle", strings.read_aloud);
  setText("stopSpeakButton", strings.stop_speaking);
  setText("emergencyBtn", strings.emergency_btn);

  const lead = document.getElementById("emergencyLead");
  if (lead && strings.emergency_lead) lead.textContent = strings.emergency_lead;

  input.placeholder = strings.placeholder || "";
  input.setAttribute("aria-label", strings.input_label || "");
  updateSizeLabel();
  updateThemeLabel();
  speakToggle.setAttribute("aria-pressed", String(state.speakAloud));
  if (recognition) recognition.lang = meta.stt || "en-ZA";
  warnedAboutVoice = false;
  setSpeechStatus(speechSupported ? strings.voice_ready : strings.voice_unsupported);
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node && value) node.textContent = value;
}

function updateSizeLabel() {
  const strings = ui();
  const names = strings.sizes || ["normal", "large", "extra large"];
  document.body.dataset.size = SIZES[state.sizeIndex];
  sizeToggle.textContent = `${strings.text_size || "Text size"}: ${names[state.sizeIndex]}`;
}

function isDark() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function updateThemeLabel() {
  const strings = ui();
  themeToggle.textContent = isDark() ? (strings.to_light || "Switch to light") : (strings.to_dark || "Switch to dark");
}

/* -------------------------------------------------------------- transcript */

function addMessage(role, text, quickReplies = [], links = [], facilities = []) {
  const row = document.createElement("div");
  row.className = `row ${role}`;

  const content = document.createElement("div");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  content.appendChild(bubble);

  facilities.forEach((facility) => content.appendChild(facilityCard(facility)));

  if (quickReplies.length || links.length) {
    const actions = document.createElement("div");
    actions.className = "actions";

    quickReplies.forEach((reply) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "action-btn";
      button.textContent = reply.label;
      button.addEventListener("click", () => sendMessage(reply.value, false));
      actions.appendChild(button);
    });

    links.forEach((link) => {
      const anchor = document.createElement("a");
      anchor.className = "link-btn";
      anchor.href = link.url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = link.label;
      actions.appendChild(anchor);
    });

    content.appendChild(actions);
  }

  row.appendChild(content);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function facilityCard(facility) {
  const strings = ui();
  const card = document.createElement("div");
  card.className = "facility";

  const name = document.createElement("h3");
  name.textContent = facility.name;
  card.appendChild(name);

  const address = document.createElement("p");
  address.textContent = facility.address;
  card.appendChild(address);

  const meta = document.createElement("p");
  meta.className = "facility-meta";
  meta.textContent = [facility.kind, facility.phone].filter(Boolean).join(" · ");
  if (facility.distance_km !== null && facility.distance_km !== undefined) {
    const distance = document.createElement("span");
    distance.className = "distance";
    distance.textContent = ` · ${facility.distance_km} km`;
    meta.appendChild(distance);
  }
  card.appendChild(meta);

  const row = document.createElement("div");
  row.className = "facility-actions";

  const call = document.createElement("a");
  call.className = "facility-btn primary";
  call.href = facility.tel_url;
  call.textContent = `${strings.call || "Call"} ${facility.phone}`;
  row.appendChild(call);

  const map = document.createElement("a");
  map.className = "facility-btn";
  map.href = facility.map_url;
  map.target = "_blank";
  map.rel = "noopener noreferrer";
  map.textContent = strings.directions || "Directions";
  row.appendChild(map);

  card.appendChild(row);
  return card;
}

function setTyping(show) {
  typing.classList.toggle("hidden", !show);
}

/* ------------------------------------------------------------------ speech */

function pickVoice(prefix) {
  const voices = window.speechSynthesis?.getVoices() || [];
  return (
    voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith(`${prefix}-`)) ||
    voices.find((voice) => voice.lang && voice.lang.toLowerCase() === prefix) ||
    null
  );
}

function speakResponse(text, autoOpenUrl = null) {
  const strings = ui();

  if (!("speechSynthesis" in window)) {
    setSpeechStatus(strings.voice_unsupported || "");
    if (autoOpenUrl) window.location.href = autoOpenUrl;
    scheduleRecognitionRestart();
    return;
  }

  speaking = true;
  stopRecognition();
  window.speechSynthesis.cancel();

  const meta = langMeta();
  const utterance = new SpeechSynthesisUtterance(String(text || "").replace(/https?:\/\/\S+/g, ""));
  let voice = pickVoice(meta.tts_prefix || "en");
  if (!voice) {
    // Most devices ship no Afrikaans, isiZulu or Sesotho voice. Say so once,
    // then read in English rather than mangling the words with an English engine.
    voice = pickVoice("en-za") || pickVoice("en");
    if (state.lang !== "en" && !warnedAboutVoice) {
      warnedAboutVoice = true;
      setSpeechStatus(strings.no_voice_for_lang || "");
    }
  }
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  } else {
    utterance.lang = meta.html_lang || "en-ZA";
  }
  utterance.rate = 0.95;

  stopSpeakButton.hidden = false;

  utterance.onstart = () => setSpeechStatus(strings.voice_speaking || "");
  utterance.onerror = () => {
    speaking = false;
    stopSpeakButton.hidden = true;
    if (autoOpenUrl) window.location.href = autoOpenUrl;
    scheduleRecognitionRestart();
  };
  utterance.onend = () => {
    speaking = false;
    stopSpeakButton.hidden = true;
    if (autoOpenUrl) {
      window.location.href = autoOpenUrl;
      return;
    }
    setSpeechStatus(voiceSessionActive ? strings.voice_listening : strings.voice_wake);
    scheduleRecognitionRestart();
  };

  window.speechSynthesis.speak(utterance);
}

/* ------------------------------------------------------------- recognition */

function stopRecognition() {
  if (!recognition || !recognitionRunning) return;
  try {
    recognition.stop();
  } catch (error) {
    // Recognition may already be stopping; no action is required.
  }
}

function scheduleRecognitionRestart(delay = 350) {
  if (!state.voiceMode || !speechSupported || speaking) return;
  window.clearTimeout(recognitionRestartTimer);
  recognitionRestartTimer = window.setTimeout(startWakeListening, delay);
}

function startWakeListening() {
  if (!recognition || !state.voiceMode || speaking || recognitionRunning) return;
  try {
    recognition.start();
  } catch (error) {
    scheduleRecognitionRestart(700);
  }
}

function configureVoiceRecognition() {
  if (!SpeechRecognition) {
    speechSupported = false;
    state.voiceMode = false;
    setSpeechStatus(ui().voice_unsupported || "");
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = langMeta().stt || "en-ZA";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    recognitionRunning = true;
    setSpeechStatus(voiceSessionActive ? ui().voice_listening : ui().voice_wake);
  };

  recognition.onresult = (event) => {
    const transcript = event.results?.[event.results.length - 1]?.[0]?.transcript?.trim() || "";
    if (!transcript) return;

    if (voiceSessionActive) {
      if (isStopPhrase(transcript)) {
        voiceSessionActive = false;
        setSpeechStatus(ui().voice_wake || "");
        scheduleRecognitionRestart();
        return;
      }
      input.value = transcript.slice(0, 2000);
      sendMessage(transcript, true);
      return;
    }

    const triggerResult = findTrigger(transcript);
    if (!triggerResult.matched) {
      setSpeechStatus(ui().voice_wake || "");
      return;
    }

    voiceSessionActive = true;

    if (triggerResult.command) {
      input.value = triggerResult.command.slice(0, 2000);
      sendMessage(triggerResult.command, true);
      return;
    }

    waitingForCommand = true;
    stopRecognition();
    speakResponse(ui().voice_listening || "I am listening.");
  };

  recognition.onerror = (event) => {
    const strings = ui();
    const messages = {
      "not-allowed": strings.voice_unsupported,
      "service-not-allowed": strings.voice_unsupported,
      "no-speech": strings.voice_wake,
      "audio-capture": strings.voice_unsupported,
      network: strings.voice_unsupported
    };
    setSpeechStatus(messages[event.error] || strings.voice_wake || "");
  };

  recognition.onend = () => {
    recognitionRunning = false;
    if (!speaking && state.voiceMode) {
      scheduleRecognitionRestart(voiceSessionActive || waitingForCommand ? 100 : 350);
    }
  };
}

/* --------------------------------------------------------------- messaging */

async function sendMessage(message, fromVoice = false) {
  const value = String(message || "").trim();
  if (!value) return;

  stopRecognition();
  addMessage("user", value);
  input.value = "";
  setTyping(true);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: value,
        session_id: state.sessionId,
        lang: state.lang,
        location: state.location
      })
    });

    const data = await response.json();
    state.sessionId = data.session_id || state.sessionId;
    localStorage.setItem("netcare_chat_session", state.sessionId || "");

    const replyText = data.message || ui().no_match || "";
    addMessage("bot", replyText, data.quick_replies || [], data.links || [], data.facilities || []);

    const spoken = data.speech || replyText;
    if (fromVoice || state.speakAloud) {
      speakResponse(spoken, data.auto_open_url || null);
    } else if (!speaking) {
      setSpeechStatus(ui().voice_wake || "");
      scheduleRecognitionRestart();
    }
  } catch (error) {
    const replyText = "I could not connect to the Netcare help service. Please try again, or contact Netcare directly.";
    addMessage("bot", replyText, [], [
      { label: "Netcare Contact Us", url: "https://www.netcare.co.za/Contact-us" }
    ]);
    if (fromVoice) speakResponse(replyText);
  } finally {
    setTyping(false);
  }
}

/* ---------------------------------------------------------------- location */

function requestLocation(thenAsk = true) {
  const strings = ui();
  if (!navigator.geolocation) {
    addMessage("bot", strings.loc_fail || "");
    return;
  }
  setSpeechStatus(strings.locating || "");
  navigator.geolocation.getCurrentPosition(
    (position) => {
      // Held in memory for this page view only, and sent with the request that
      // needs it. Nothing is stored in localStorage or logged by the server.
      state.location = { lat: position.coords.latitude, lng: position.coords.longitude };
      setSpeechStatus("");
      if (thenAsk) sendMessage(nearMeQuery(), false);
    },
    (error) => {
      const message = error.code === 1 ? strings.loc_denied : strings.loc_fail;
      setSpeechStatus("");
      addMessage("bot", message || "");
      if (state.speakAloud) speakResponse(message || "");
    },
    { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 }
  );
}

function nearMeQuery() {
  const replies = ui().quick_replies || [];
  const nearReply = replies.find((reply) => /near|naby|eduze|haufi/i.test(reply.value));
  return nearReply ? nearReply.value : "hospitals near me";
}

/* ------------------------------------------------------------------ wiring */

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value, false);
});

menuButton.addEventListener("click", () => sendMessage("menu", false));

restartButton.addEventListener("click", () => {
  localStorage.removeItem("netcare_chat_session");
  state.sessionId = null;
  waitingForCommand = false;
  voiceSessionActive = false;
  window.speechSynthesis?.cancel();
  speaking = false;
  chat.innerHTML = "";
  greet();
  startWakeListening();
});

nearMeButton.addEventListener("click", () => {
  if (state.location) sendMessage(nearMeQuery(), false);
  else requestLocation(true);
});

speakToggle.addEventListener("click", () => {
  state.speakAloud = !state.speakAloud;
  speakToggle.setAttribute("aria-pressed", String(state.speakAloud));
  localStorage.setItem("netcare_speak", state.speakAloud ? "on" : "off");
  if (!state.speakAloud) {
    window.speechSynthesis?.cancel();
    stopSpeakButton.hidden = true;
  }
});

stopSpeakButton.addEventListener("click", () => {
  window.speechSynthesis?.cancel();
  stopSpeakButton.hidden = true;
});

sizeToggle.addEventListener("click", () => {
  state.sizeIndex = (state.sizeIndex + 1) % SIZES.length;
  localStorage.setItem("netcare_size", String(state.sizeIndex));
  updateSizeLabel();
});

themeToggle.addEventListener("click", () => {
  const next = isDark() ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("netcare_theme", next);
  updateThemeLabel();
});

languageSelect.addEventListener("change", (event) => {
  state.lang = event.target.value;
  localStorage.setItem("netcare_lang", state.lang);
  voiceSessionActive = false;
  window.speechSynthesis?.cancel();
  stopSpeakButton.hidden = true;
  chat.innerHTML = "";
  applyInterfaceLanguage();
  greet();
});

function greet() {
  const strings = ui();
  addMessage("bot", strings.welcome || "", strings.quick_replies || []);
}

/* -------------------------------------------------------------------- boot */

async function boot() {
  try {
    const response = await fetch("/config");
    state.config = await response.json();
  } catch (error) {
    state.config = { ui: {}, languages: [], wake_words: {}, stop_words: {} };
  }

  const languages = state.config.languages || [];
  if (!languages.some((entry) => entry.code === state.lang)) {
    state.lang = state.config.default_language || "en";
  }
  languageSelect.innerHTML = "";
  languages.forEach((entry) => {
    const option = document.createElement("option");
    option.value = entry.code;
    option.textContent = entry.label;
    languageSelect.appendChild(option);
  });
  languageSelect.value = state.lang;

  const savedTheme = localStorage.getItem("netcare_theme");
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);

  configureVoiceRecognition();
  applyInterfaceLanguage();
  greet();

  if (speechSupported) window.setTimeout(startWakeListening, 900);
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = () => {};
}

window.addEventListener("focus", () => {
  if (!speaking && speechSupported) scheduleRecognitionRestart(300);
});

boot();
