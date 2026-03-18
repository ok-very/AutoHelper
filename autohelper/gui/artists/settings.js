/* Artist Settings page */
(function () {
  "use strict";

  const API = "/artists";
  const CONFIG_API = "/config";
  let fullLexicon = {};
  let currentSection = "categories";

  function showFeedback(id, msg, isErr) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.className = "save-feedback " + (isErr ? "save-err" : "save-ok");
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadConfig();
    loadLexicon();
    checkActiveScan();

    document.getElementById("btn-save-config").addEventListener("click", saveConfig);
    document.getElementById("btn-browse-root").addEventListener("click", () => browseForPath("cfg-storage-root"));
    document.getElementById("btn-browse-gt").addEventListener("click", () => browseForPath("cfg-ground-truth"));
    document.getElementById("btn-scan").addEventListener("click", triggerScan);
    document.getElementById("btn-scan-stop").addEventListener("click", stopScan);
    document.getElementById("btn-save-lexicon").addEventListener("click", saveLexicon);
    document.getElementById("btn-reset-lexicon").addEventListener("click", resetLexicon);
    document.getElementById("btn-export-lexicon").addEventListener("click", exportLexicon);
    document.getElementById("btn-import-lexicon").addEventListener("change", importLexicon);

    // Tab switching
    document.querySelectorAll(".lexicon-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        // Save current edits back before switching
        saveCurrentEditsToMemory();
        currentSection = tab.dataset.section;
        document.querySelectorAll(".lexicon-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        renderLexiconSection();
      });
    });
  });

  // ------------------------------------------------------------------
  // Config (settings)
  // ------------------------------------------------------------------
  async function loadConfig() {
    try {
      const cr = await fetch(CONFIG_API);
      if (!cr.ok) throw new Error("HTTP " + cr.status);
      const cfg = await cr.json();

      document.getElementById("cfg-storage-root").value = cfg.artist_storage_root || "";
      document.getElementById("cfg-ground-truth").value = cfg.artist_ground_truth_csv || "";
      document.getElementById("cfg-scan-enabled").checked = !!cfg.artist_scan_enabled;
      document.getElementById("cfg-scan-on-change").checked = !!cfg.artist_scan_on_change;
    } catch (e) {
      console.error("Load config:", e);
      showFeedback("config-feedback", "\u2717 Could not load config", true);
    }
  }

  async function browseForPath(inputId) {
    const input = document.getElementById(inputId);
    const btn = input.parentElement.querySelector("button");
    btn.disabled = true;
    btn.textContent = "\u2026";
    try {
      let path = null;
      if (window.electronAPI?.selectFolder) {
        path = await window.electronAPI.selectFolder();
      } else {
        const r = await fetch("/config/select-folder", { method: "POST" });
        const d = await r.json();
        path = d.path;
      }
      if (path) input.value = path;
    } catch (e) {
      console.error("Browse:", e);
    }
    btn.disabled = false;
    btn.textContent = "Browse";
  }

  async function saveConfig() {
    const btn = document.getElementById("btn-save-config");
    const fb = document.getElementById("config-feedback");
    btn.disabled = true;
    fb.textContent = "Saving\u2026";
    fb.className = "save-feedback";

    try {
      const r = await fetch(CONFIG_API, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          artist_storage_root: document.getElementById("cfg-storage-root").value.trim(),
          artist_ground_truth_csv: document.getElementById("cfg-ground-truth").value.trim(),
          artist_scan_enabled: document.getElementById("cfg-scan-enabled").checked,
          artist_scan_on_change: document.getElementById("cfg-scan-on-change").checked,
        }),
      });
      if (r.ok) {
        fb.textContent = "\u2713 Saved";
        fb.className = "save-feedback save-ok";
      } else {
        fb.textContent = "\u2717 Error";
        fb.className = "save-feedback save-err";
      }
    } catch (e) {
      fb.textContent = "\u2717 Network error";
      fb.className = "save-feedback save-err";
    }
    btn.disabled = false;
  }

  // ------------------------------------------------------------------
  // Lexicon
  // ------------------------------------------------------------------
  async function loadLexicon() {
    try {
      const r = await fetch(API + "/lexicon");
      if (!r.ok) throw new Error("HTTP " + r.status);
      fullLexicon = await r.json();
      renderLexiconSection();
    } catch (e) {
      console.error("Load lexicon:", e);
      showFeedback("lexicon-feedback", "\u2717 Failed to load lexicon", true);
    }
  }

  function renderLexiconSection() {
    const editor = document.getElementById("lexicon-editor");
    editor.classList.remove("invalid");

    if (currentSection === "full") {
      editor.value = JSON.stringify(fullLexicon, null, 2);
    } else {
      const section = fullLexicon[currentSection];
      editor.value = section !== undefined ? JSON.stringify(section, null, 2) : "{}";
    }
  }

  function saveCurrentEditsToMemory() {
    const editor = document.getElementById("lexicon-editor");
    try {
      const parsed = JSON.parse(editor.value);
      if (currentSection === "full") {
        fullLexicon = parsed;
      } else {
        fullLexicon[currentSection] = parsed;
      }
      editor.classList.remove("invalid");
    } catch (e) {
      // Don't update if invalid JSON
      editor.classList.add("invalid");
    }
  }

  async function saveLexicon() {
    saveCurrentEditsToMemory();
    const fb = document.getElementById("lexicon-feedback");
    const btn = document.getElementById("btn-save-lexicon");
    btn.disabled = true;
    fb.textContent = "Saving\u2026";
    fb.className = "save-feedback";

    try {
      const r = await fetch(API + "/lexicon", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fullLexicon),
      });
      if (r.ok) {
        fb.textContent = "\u2713 Saved";
        fb.className = "save-feedback save-ok";
      } else {
        const d = await r.json().catch(() => ({}));
        fb.textContent = "\u2717 " + (d.detail || "Error");
        fb.className = "save-feedback save-err";
      }
    } catch (e) {
      fb.textContent = "\u2717 Network error";
      fb.className = "save-feedback save-err";
    }
    btn.disabled = false;
  }

  async function resetLexicon() {
    if (!confirm("Reset lexicon to defaults? Current edits will be lost.")) return;
    const fb = document.getElementById("lexicon-feedback");
    try {
      // Save empty to trigger reset, then reload
      const r = await fetch(API + "/lexicon");
      fullLexicon = await r.json();
      renderLexiconSection();
      fb.textContent = "Reloaded from disk";
      fb.className = "save-feedback save-ok";
    } catch (e) {
      fb.textContent = "\u2717 Error";
      fb.className = "save-feedback save-err";
    }
  }

  function exportLexicon() {
    saveCurrentEditsToMemory();
    const blob = new Blob([JSON.stringify(fullLexicon, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "artist_lexicon.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function importLexicon(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        fullLexicon = JSON.parse(reader.result);
        renderLexiconSection();
        document.getElementById("lexicon-feedback").textContent = "Imported \u2014 click Save to persist";
        document.getElementById("lexicon-feedback").className = "save-feedback save-ok";
      } catch (err) {
        document.getElementById("lexicon-feedback").textContent = "\u2717 Invalid JSON file";
        document.getElementById("lexicon-feedback").className = "save-feedback save-err";
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  // ------------------------------------------------------------------
  // Scan
  // ------------------------------------------------------------------
  let scanEventSource = null;

  async function triggerScan() {
    const btnScan = document.getElementById("btn-scan");
    const btnStop = document.getElementById("btn-scan-stop");
    const terminal = document.getElementById("scan-terminal");
    const status = document.getElementById("scan-status");

    btnScan.disabled = true;
    btnStop.disabled = false;
    status.textContent = "Starting\u2026";
    terminal.innerHTML = "";
    terminal.style.display = "block";

    try {
      const r = await fetch(API + "/scan", { method: "POST" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        status.textContent = d.detail || "Error";
        btnScan.disabled = false;
        btnStop.disabled = true;
        return;
      }
    } catch (e) {
      status.textContent = "Network error";
      btnScan.disabled = false;
      btnStop.disabled = true;
      return;
    }

    status.textContent = "Scanning\u2026";
    connectScanLog();
  }

  function connectScanLog() {
    if (scanEventSource) scanEventSource.close();

    const terminal = document.getElementById("scan-terminal");
    scanEventSource = new EventSource(API + "/scan/log");

    scanEventSource.onmessage = (e) => {
      if (e.data === "[done]") {
        scanEventSource.close();
        scanEventSource = null;
        onScanFinished();
        return;
      }
      const line = document.createElement("div");
      line.className = "scan-line";
      line.textContent = e.data;
      terminal.appendChild(line);
      terminal.scrollTop = terminal.scrollHeight;
    };

    scanEventSource.onerror = () => {
      scanEventSource.close();
      scanEventSource = null;
      onScanFinished();
    };
  }

  async function onScanFinished() {
    const btnScan = document.getElementById("btn-scan");
    const btnStop = document.getElementById("btn-scan-stop");
    const status = document.getElementById("scan-status");
    const info = document.getElementById("scan-info");

    btnScan.disabled = false;
    btnStop.disabled = true;

    try {
      const r = await fetch(API + "/scan/status");
      const d = await r.json();
      if (d.last_run) {
        const s = d.last_run.stats;
        const st = d.last_run.status;
        if (st === "completed") {
          status.textContent = `Done: ${s?.artists || 0} artists`;
        } else {
          status.textContent = st.charAt(0).toUpperCase() + st.slice(1);
        }
        info.textContent = d.last_run.finished_at
          ? `Finished: ${d.last_run.finished_at}` : "";
      } else {
        status.textContent = "No scans yet";
      }
    } catch (e) {
      status.textContent = "Unable to load status";
    }
  }

  async function stopScan() {
    const btnStop = document.getElementById("btn-scan-stop");
    btnStop.disabled = true;
    document.getElementById("scan-status").textContent = "Stopping\u2026";
    try {
      await fetch(API + "/scan/stop", { method: "POST" });
    } catch (e) {
      console.error("Stop scan:", e);
    }
  }

  // Check if a scan is already running on page load
  async function checkActiveScan() {
    try {
      const r = await fetch(API + "/scan/status");
      const d = await r.json();
      if (d.is_scanning) {
        document.getElementById("btn-scan").disabled = true;
        document.getElementById("btn-scan-stop").disabled = false;
        document.getElementById("scan-status").textContent = "Scanning\u2026";
        document.getElementById("scan-terminal").style.display = "block";
        connectScanLog();
      } else if (d.last_run) {
        const s = d.last_run.stats;
        const st = d.last_run.status;
        document.getElementById("scan-status").textContent = st === "completed"
          ? `Last: ${s?.artists || 0} artists` : `Last: ${st}`;
        document.getElementById("scan-info").textContent = d.last_run.finished_at
          ? `Finished: ${d.last_run.finished_at}` : "";
      }
    } catch (e) { /* ignore */ }
  }
})();
