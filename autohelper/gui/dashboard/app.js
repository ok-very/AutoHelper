/* AutoHelper Dashboard — vanilla JS client for config + contacts API */

const API = "";  // Same origin

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status}`);
  return res.json();
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

let _toastTimer = null;
function toast(msg, type) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast visible " + type;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = "toast"; }, 3000);
}

function fmtTime(iso) {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return d.toLocaleString();
}

// ---------------------------------------------------------------------------
// Service Status
// ---------------------------------------------------------------------------

async function loadStatus() {
  try {
    const [health, status] = await Promise.all([
      api("GET", "/health"),
      api("GET", "/status"),
    ]);

    const rows = [
      ["Service", health.status === "ok" ? "ok" : "error",
       health.status === "ok" ? "Running" : "Error"],
      ["Mode", "ok", health.mode || "\u2014"],
      ["Database", status.db_reachable ? "ok" : "error",
       status.db_reachable ? "Connected" : "Unreachable"],
      ["Migrations", "ok", (status.migrations?.applied_count ?? 0) + " applied"],
    ];

    const container = $("#status-rows");
    container.innerHTML = rows.map(([label, dot, value]) =>
      `<div class="status-row">
        <span class="label"><span class="status-dot ${dot}"></span>${label}</span>
        <span class="value">${value}</span>
      </div>`
    ).join("");
  } catch (e) {
    $("#status-rows").innerHTML =
      `<div class="status-row">
        <span class="label"><span class="status-dot error"></span>Service</span>
        <span class="value">Unreachable</span>
      </div>`;
  }
}

// ---------------------------------------------------------------------------
// Schema-Driven Settings
// ---------------------------------------------------------------------------

let _config = {};
let _schema = null;

async function loadSchemaAndConfig() {
  try {
    const [schema, config] = await Promise.all([
      api("GET", "/config/schema"),
      api("GET", "/config"),
    ]);
    _schema = schema;
    _config = config;
    renderSettingsSections(schema, config);
    populatePairingStatus();
  } catch (e) {
    toast("Failed to load config", "error");
  }
}

function renderSettingsSections(schema, config) {
  const container = $("#settings-sections");
  container.innerHTML = "";

  for (const section of schema.sections) {
    const sectionEl = document.createElement("section");
    if (section.admin_only) sectionEl.classList.add("admin-only");

    const h2 = document.createElement("h2");
    h2.textContent = section.label;
    if (section.admin_only) {
      const badge = document.createElement("span");
      badge.className = "admin-badge";
      badge.textContent = "Admin";
      h2.appendChild(badge);
    }
    sectionEl.appendChild(h2);

    const body = document.createElement("div");
    body.className = "section-body";

    // Group fields by row_group
    const rendered = new Set();
    for (const field of section.fields) {
      if (rendered.has(field.key)) continue;

      if (field.row_group) {
        const group = section.fields.filter(f => f.row_group === field.row_group);
        const row = document.createElement("div");
        row.className = "field-row";
        for (const gf of group) {
          row.appendChild(renderField(gf, config[gf.key]));
          rendered.add(gf.key);
        }
        body.appendChild(row);
      } else {
        body.appendChild(renderField(field, config[field.key]));
        rendered.add(field.key);
      }
    }

    // Save button + schema-driven action buttons
    const btnRow = document.createElement("div");
    btnRow.className = "button-row";
    const btn = document.createElement("button");
    btn.className = "primary";
    btn.textContent = "Save";
    btn.addEventListener("click", () => saveSection(section));
    btnRow.appendChild(btn);

    if (section.actions) {
      for (const action of section.actions) {
        const actionBtn = document.createElement("button");
        actionBtn.id = action.id;
        actionBtn.textContent = action.label;
        actionBtn.addEventListener("click", () => invokeAction(action));
        btnRow.appendChild(actionBtn);
      }
    }

    body.appendChild(btnRow);

    // Schema-driven status areas
    if (section.actions) {
      for (const action of section.actions) {
        if (action.status_key) {
          const statusEl = document.createElement("div");
          statusEl.id = action.status_key;
          statusEl.style.cssText = "margin-top:8px;font-size:13px";
          body.appendChild(statusEl);
        }
      }
    }

    sectionEl.appendChild(body);
    container.appendChild(sectionEl);
  }

  // Apply depends_on visibility
  updateDependsOn();
}

function renderField(field, value) {
  const wrapper = document.createElement("div");

  if (field.type === "bool") {
    wrapper.className = "toggle";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = "cfg-" + field.key;
    input.checked = !!value;
    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.textContent = field.label;
    wrapper.appendChild(input);
    wrapper.appendChild(label);

    // Bool fields that other fields depend on: update visibility on change
    input.addEventListener("change", updateDependsOn);
  } else {
    wrapper.className = "field";
    const label = document.createElement("label");
    label.htmlFor = "cfg-" + field.key;
    label.textContent = field.label;
    wrapper.appendChild(label);

    let input;

    switch (field.type) {
      case "int": {
        input = document.createElement("input");
        input.type = "number";
        input.id = "cfg-" + field.key;
        input.value = value ?? field.default ?? "";
        if (field.min != null) input.min = field.min;
        if (field.max != null) input.max = field.max;
        break;
      }
      case "select": {
        input = document.createElement("select");
        input.id = "cfg-" + field.key;
        for (const opt of (field.options || [])) {
          const option = document.createElement("option");
          option.value = opt;
          option.textContent = opt;
          if (opt === (value ?? field.default)) option.selected = true;
          input.appendChild(option);
        }
        break;
      }
      case "string_list": {
        input = document.createElement("textarea");
        input.id = "cfg-" + field.key;
        input.rows = 3;
        input.value = Array.isArray(value) ? value.join("\n") : (value || "");
        if (field.placeholder) input.placeholder = field.placeholder;
        break;
      }
      case "tag_list": {
        input = document.createElement("input");
        input.type = "text";
        input.id = "cfg-" + field.key;
        input.value = Array.isArray(value) ? value.join(", ") : (value || "");
        if (field.placeholder) input.placeholder = field.placeholder;
        break;
      }
      case "text": {
        input = document.createElement("textarea");
        input.id = "cfg-" + field.key;
        input.rows = 4;
        input.value = value ?? field.default ?? "";
        if (field.placeholder) input.placeholder = field.placeholder;
        break;
      }
      case "password": {
        input = document.createElement("input");
        input.type = "password";
        input.id = "cfg-" + field.key;
        input.value = value ?? field.default ?? "";
        if (field.placeholder) input.placeholder = field.placeholder;
        input.autocomplete = "off";
        break;
      }
      default: {
        // "string"
        input = document.createElement("input");
        input.type = "text";
        input.id = "cfg-" + field.key;
        input.value = value ?? field.default ?? "";
        if (field.placeholder) input.placeholder = field.placeholder;
        break;
      }
    }

    wrapper.appendChild(input);
  }

  // depends_on attribute for visibility toggling
  if (field.depends_on) {
    wrapper.dataset.dependsOn = field.depends_on;
  }

  return wrapper;
}

function updateDependsOn() {
  const dependents = document.querySelectorAll("[data-depends-on]");
  for (const el of dependents) {
    const dep = el.dataset.dependsOn;
    const toggle = document.getElementById("cfg-" + dep);
    if (toggle) {
      el.style.display = toggle.checked ? "" : "none";
    }
  }
}

function readFieldValue(field) {
  const el = document.getElementById("cfg-" + field.key);
  if (!el) return field.default;

  switch (field.type) {
    case "bool":
      return el.checked;
    case "int": {
      const n = parseInt(el.value, 10);
      return Number.isNaN(n) ? field.default : n;
    }
    case "string_list": {
      const raw = el.value.trim();
      return raw ? raw.split("\n").map(s => s.trim()).filter(Boolean) : [];
    }
    case "tag_list": {
      const raw = el.value.trim();
      return raw ? raw.split(",").map(s => s.trim()).filter(Boolean) : [];
    }
    case "select":
      return el.value;
    default:
      return el.value.trim();
  }
}

async function saveSection(section) {
  const patch = {};
  for (const field of section.fields) {
    patch[field.key] = readFieldValue(field);
  }

  try {
    _config = await api("PUT", "/config", patch);
    toast(section.label + " saved", "success");
  } catch (e) {
    toast("Failed to save " + section.label.toLowerCase(), "error");
  }
}

// ---------------------------------------------------------------------------
// Contact Sync Status
// ---------------------------------------------------------------------------

async function loadContactStatus() {
  try {
    const status = await api("GET", "/contacts/status");
    const rows = [
      ["Enabled", status.enabled ? "ok" : "warn",
       status.enabled ? "Yes" : "No"],
      ["Last Sync", "ok", fmtTime(status.last_sync)],
      ["Next Sync", "ok", fmtTime(status.next_sync)],
      ["Last Result", status.last_status === "failed" ? "error" : "ok",
       status.last_status || "\u2014"],
    ];

    $("#contact-status-rows").innerHTML = rows.map(([label, dot, value]) =>
      `<div class="status-row">
        <span class="label"><span class="status-dot ${dot}"></span>${label}</span>
        <span class="value">${value}</span>
      </div>`
    ).join("");
  } catch {
    $("#contact-status-rows").innerHTML =
      `<div class="status-row">
        <span class="label">Status</span>
        <span class="value empty">Module not available</span>
      </div>`;
  }
}

async function loadContactHistory() {
  try {
    const data = await api("GET", "/contacts/history");
    const rows = data.entries || [];

    if (rows.length === 0) {
      $("#contact-history-body").innerHTML =
        `<tr><td colspan="5" class="empty">No sync history</td></tr>`;
      return;
    }

    $("#contact-history-body").innerHTML = rows.map(r =>
      `<tr>
        <td>${fmtTime(r.started_at)}</td>
        <td>${r.status}</td>
        <td>${r.created ?? 0}</td>
        <td>${r.updated ?? 0}</td>
        <td>${r.deleted ?? 0}</td>
      </tr>`
    ).join("");
  } catch {
    $("#contact-history-body").innerHTML =
      `<tr><td colspan="5" class="empty">Unavailable</td></tr>`;
  }
}

async function triggerManualSync() {
  const btn = $("#btn-manual-sync");
  btn.disabled = true;
  btn.textContent = "Syncing...";

  try {
    const result = await api("POST", "/contacts/sync");
    toast(result.message || "Sync triggered", "success");
    await loadContactStatus();
    await loadContactHistory();
  } catch (e) {
    toast("Sync failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Sync Now";
  }
}

// ---------------------------------------------------------------------------
// Schema-Driven Actions
// ---------------------------------------------------------------------------

async function invokeAction(action) {
  const btn = document.getElementById(action.id);
  const statusEl = action.status_key ? document.getElementById(action.status_key) : null;
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Working\u2026";
  if (statusEl) statusEl.textContent = "";

  try {
    const result = await api("POST", action.endpoint);

    if (statusEl) {
      if (result.connected === true) {
        statusEl.innerHTML = '<span style="color:var(--green,#4caf50)">\u2713 Connected</span>' +
          (result.message ? ' \u2014 ' + escapeHtml(result.message) : '');
      } else if (result.connected === false) {
        statusEl.innerHTML = '<span style="color:var(--red,#f44336)">\u2717 ' + escapeHtml(result.message || "Failed") + '</span>';
      } else if (result.message) {
        statusEl.innerHTML = escapeHtml(result.message);
      }
    } else {
      toast(result.message || "Done", "success");
    }
  } catch (e) {
    if (statusEl) {
      statusEl.innerHTML = '<span style="color:var(--red,#f44336)">\u2717 ' + escapeHtml(e.message) + '</span>';
    } else {
      toast(e.message, "error");
    }
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }
}

// ---------------------------------------------------------------------------
// Console Log Viewer
// ---------------------------------------------------------------------------

function appendLogLine(entry) {
  const el = $("#console-log");
  const line = document.createElement("div");
  line.className = "log-line";

  const ts = new Date(entry.ts * 1000).toLocaleTimeString();
  line.innerHTML =
    `<span class="ts">${ts}</span> ` +
    `<span class="lvl-${entry.level}">[${entry.level}]</span> ` +
    `<span class="msg">${escapeHtml(entry.msg)}</span>`;

  el.appendChild(line);

  // Auto-scroll if near bottom
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  if (atBottom) el.scrollTop = el.scrollHeight;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function loadInitialLogs() {
  try {
    const data = await api("GET", "/logs");
    for (const entry of (data.entries || [])) {
      appendLogLine(entry);
    }
    // Scroll to bottom
    const el = $("#console-log");
    el.scrollTop = el.scrollHeight;
  } catch { /* ignore */ }
}

function connectLogStream() {
  const es = new EventSource(API + "/logs/stream");
  es.onmessage = (evt) => {
    try {
      const entry = JSON.parse(evt.data);
      appendLogLine(entry);
    } catch { /* ignore */ }
  };
  es.onerror = () => {
    // Reconnect after a delay
    es.close();
    setTimeout(connectLogStream, 5000);
  };
}

// ---------------------------------------------------------------------------
// Pairing
// ---------------------------------------------------------------------------

function populatePairingStatus() {
  const key = _config.autoart_link_key;
  const paired = !!key;
  $("#pairing-status").textContent = paired ? "Paired" : "Not paired";
  $("#pairing-dot").className = "status-dot " + (paired ? "ok" : "warn");
  $("#btn-unpair").style.display = paired ? "" : "none";
  // Pair button visible only when not paired and frontend URL is configured
  const hasFrontend = _config.autoart_frontend_url || _config.autoart_api_url;
  $("#btn-pair").style.display = (!paired && hasFrontend) ? "" : "none";
}

async function doPair() {
  const code = prompt("Enter 6-character pairing code:");
  if (!code || code.length !== 6) return;

  try {
    // Redeem pairing code via backend
    const apiUrl = _config.autoart_api_url || "http://localhost:3001";
    const res = await fetch(apiUrl + "/api/pair/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code.trim() }),
    });
    if (!res.ok) throw new Error("Invalid code or expired");
    const data = await res.json();

    // Store key
    _config = await api("PUT", "/config", { autoart_link_key: data.key });
    populatePairingStatus();
    toast("Paired successfully", "success");
  } catch (e) {
    toast("Pairing failed: " + e.message, "error");
  }
}

async function doUnpair() {
  if (!confirm("Unpair from AutoArt backend?")) return;

  try {
    // Notify backend (best-effort)
    const apiUrl = _config.autoart_api_url || "http://localhost:3001";
    const key = _config.autoart_link_key;
    if (key) {
      fetch(apiUrl + "/api/autohelper/unpair", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          "x-autohelper-key": key,
        },
      }).catch(() => {});
    }

    // Clear local key
    _config = await api("PUT", "/config", { autoart_link_key: "" });
    populatePairingStatus();
    toast("Unpaired", "success");
  } catch (e) {
    toast("Unpair failed: " + e.message, "error");
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  // Load all data
  loadStatus();
  loadSchemaAndConfig();
  loadContactStatus();
  loadContactHistory();

  // Console
  loadInitialLogs();
  connectLogStream();

  // Contact sync actions
  $("#btn-manual-sync").addEventListener("click", triggerManualSync);

  // Pairing
  $("#btn-pair").addEventListener("click", doPair);
  $("#btn-unpair").addEventListener("click", doUnpair);

  // Refresh status every 30s
  setInterval(() => {
    loadStatus();
    loadContactStatus();
  }, 30000);
});
