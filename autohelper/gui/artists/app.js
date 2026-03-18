/* Artist Directory — focused browsing with prefix search + pill filters */
(function () {
  "use strict";

  const API = "/artists";
  let allArtists = [];
  let filtered = [];
  let selectedId = null;
  let sortKey = "display_name";
  let sortDir = 1;
  let currentDetail = null;

  // Active pill filters
  let activeCategories = new Set();
  let activeIdentities = new Set();

  // Identity terms that match the "Indigenous" pill
  const INDIGENOUS_TERMS = ["indigenous", "first nations", "métis", "metis", "inuit", "two-spirit"];

  // Lucide icon SVGs (inline)
  const ICO = {
    file:     '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>',
    fileText: '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    image:    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>',
    mail:     '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>',
    clipboard:'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>',
    sheet:    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/></svg>',
    folder:   '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
    send:     '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 3 3 9-3 9 19-9Z"/><path d="M6 12h16"/></svg>',
    compass:  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>',
  };

  // ---------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    buildPills();
    reload();

    const db = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
    document.getElementById("search").addEventListener("input", db(applyFilters, 250));
    document.getElementById("btn-clear-filters").addEventListener("click", clearFilters);
    document.getElementById("btn-reload").addEventListener("click", reload);
    document.getElementById("detail-close").addEventListener("click", closeDetail);
    document.getElementById("detail-overlay").addEventListener("click", closeDetail);

    // Column sorting
    document.querySelectorAll("th.sortable").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (sortKey === key) { sortDir *= -1; } else { sortKey = key; sortDir = 1; }
        applyFilters();
      });
    });

    // Deep-link: open artist from URL hash
    if (location.hash) {
      const id = decodeURIComponent(location.hash.slice(1));
      if (id) setTimeout(() => openDetail(id), 500);
    }
  });

  // ---------------------------------------------------------------
  // Pill filters
  // ---------------------------------------------------------------
  function buildPills() {
    const catContainer = document.getElementById("category-pills");
    const pills = [
      { key: "indigenous", label: "Indigenous", type: "identity" },
      { key: "public", label: "Public Art", type: "category" },
      { key: "private", label: "Private Art", type: "category" },
      { key: "corporate", label: "Corporate Art", type: "category" },
    ];
    catContainer.innerHTML = pills.map(p =>
      `<button class="pill" data-key="${p.key}" data-filter-type="${p.type}">${p.label}</button>`
    ).join("");
    catContainer.querySelectorAll(".pill").forEach(p => {
      p.addEventListener("click", () => {
        const key = p.dataset.key;
        const filterType = p.dataset.filterType;
        const store = filterType === "identity" ? activeIdentities : activeCategories;
        if (store.has(key)) {
          store.delete(key);
          p.classList.remove("active", "active-" + key);
        } else {
          store.add(key);
          p.classList.add("active", "active-" + key);
        }
        applyFilters();
      });
    });
  }

  // ---------------------------------------------------------------
  // Data
  // ---------------------------------------------------------------
  async function reload() {
    await loadArtists();
    if (selectedId) openDetail(selectedId);
  }

  async function loadArtists() {
    try {
      const r = await fetch(API + "?limit=5000");
      const data = await r.json();
      allArtists = Array.isArray(data) ? data : [];
      allArtists.forEach(a => {
        a.gap_count = [a.has_bio, a.has_cv, a.has_tearsheet, a.has_contact, a.has_images].filter(x => !x).length;
        a._all_identity = [...(a.nations || []), ...(a.identity_tags || [])];
        a.primary_identity = a._all_identity[0] || "";
      });
      // NOTE: nations = nation affiliations extracted by backend, identity_tags = identities list
      applyFilters();
    } catch (e) { console.error("Artists:", e); }
  }

  // ---------------------------------------------------------------
  // Prefix-aware search parser
  // ---------------------------------------------------------------
  function parseSearch(raw) {
    const filters = { text: [], identity: [], project: [], city: [], category: [], scoreOp: null, scoreVal: null };
    const tokens = raw.match(/(?:[^\s"]+|"[^"]*")+/g) || [];

    for (const tok of tokens) {
      const lower = tok.toLowerCase();
      if (lower.startsWith("identity:")) {
        filters.identity.push(tok.slice(9).replace(/"/g, ""));
      } else if (lower.startsWith("project:")) {
        filters.project.push(tok.slice(8).replace(/"/g, ""));
      } else if (lower.startsWith("city:")) {
        filters.city.push(tok.slice(5).replace(/"/g, ""));
      } else if (lower.startsWith("category:")) {
        filters.category.push(tok.slice(9).replace(/"/g, ""));
      } else if (lower.startsWith("score:")) {
        const expr = tok.slice(6);
        const m = expr.match(/^([<>]=?)(\d+)$/);
        if (m) { filters.scoreOp = m[1]; filters.scoreVal = parseInt(m[2], 10); }
      } else {
        filters.text.push(lower.replace(/"/g, ""));
      }
    }
    return filters;
  }

  // ---------------------------------------------------------------
  // Filtering + sorting
  // ---------------------------------------------------------------
  function applyFilters() {
    const raw = document.getElementById("search").value.trim();
    const pf = parseSearch(raw);

    filtered = allArtists.filter(a => {
      // Text match (fuzzy name + identity)
      if (pf.text.length) {
        const name = a.display_name.toLowerCase();
        const allId = a._all_identity.map(t => t.toLowerCase()).join(" ");
        if (!pf.text.every(t => name.includes(t) || allId.includes(t))) return false;
      }

      // Identity prefix
      if (pf.identity.length) {
        const allId = a._all_identity.map(t => t.toLowerCase());
        if (!pf.identity.every(f => allId.some(t => t.includes(f.toLowerCase())))) return false;
      }

      // Project prefix — search engagement projects
      // For now filter client-side on display_name (full project search needs manifest)
      if (pf.project.length) {
        // We don't have project data in the list view, so pass through
        // (will be filtered when we have enriched list data)
      }

      // City prefix
      if (pf.city.length) {
        const allId = a._all_identity.map(t => t.toLowerCase());
        if (!pf.city.every(c => allId.some(t => t.includes(c.toLowerCase())))) return false;
      }

      // Category prefix from search
      if (pf.category.length) {
        const cats = (a.categories || []).map(c => c.toLowerCase());
        if (!pf.category.every(c => cats.some(cat => cat.includes(c.toLowerCase())))) return false;
      }

      // Score filter
      if (pf.scoreOp && pf.scoreVal !== null) {
        const pct = Math.round(a.completeness * 100);
        if (pf.scoreOp === "<" && pct >= pf.scoreVal) return false;
        if (pf.scoreOp === "<=" && pct > pf.scoreVal) return false;
        if (pf.scoreOp === ">" && pct <= pf.scoreVal) return false;
        if (pf.scoreOp === ">=" && pct < pf.scoreVal) return false;
      }

      // Pill filters: category
      if (activeCategories.size > 0) {
        if (!(a.categories || []).some(c => activeCategories.has(c))) return false;
      }

      // Pill filters: identity (e.g. indigenous)
      if (activeIdentities.size > 0) {
        const allId = a._all_identity.map(t => t.toLowerCase());
        if (activeIdentities.has("indigenous")) {
          if (!INDIGENOUS_TERMS.some(term => allId.some(t => t.includes(term)))) return false;
        }
      }

      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (typeof va === "string") return va.localeCompare(vb) * sortDir;
      return ((va || 0) - (vb || 0)) * sortDir;
    });

    // Update sort icons
    document.querySelectorAll("th.sortable .sort-icon").forEach(el => {
      const key = el.parentElement.dataset.sort;
      if (key === sortKey) {
        el.className = "sort-icon active";
        el.textContent = sortDir === 1 ? "\u2191" : "\u2193";
      } else {
        el.className = "sort-icon";
        el.textContent = "\u21C5";
      }
    });

    document.getElementById("result-count").textContent = filtered.length + " artist" + (filtered.length !== 1 ? "s" : "");
    renderTable();
  }

  function clearFilters() {
    document.getElementById("search").value = "";
    activeCategories.clear();
    activeIdentities.clear();
    document.querySelectorAll(".pill").forEach(p => p.classList.remove("active", "active-indigenous", "active-public", "active-private", "active-corporate"));
    applyFilters();
  }

  // ---------------------------------------------------------------
  // Table rendering
  // ---------------------------------------------------------------
  function renderTable() {
    const tbody = document.getElementById("artist-tbody");
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No artists match your search.</td></tr>';
      return;
    }
    tbody.innerHTML = filtered.map(a => {
      const pct = Math.round(a.completeness * 100);
      const lvl = pct >= 80 ? "high" : pct >= 40 ? "mid" : "low";
      const cats = (a.categories || []).map(c => `<span class="badge badge-${c}">${cap(c)}</span>`).join("");
      const identityPills = a._all_identity.map(t => {
        const isNation = (a.nations || []).includes(t);
        return `<span class="identity-tag ${isNation ? 'identity-nation' : 'identity-tag-self'}">${esc(t)}</span>`;
      }).join("");
      const gaps = a.gap_count > 0
        ? gapList(a).map(g => `<span class="gap-pill">${g}</span>`).join("")
        : '<span style="color:var(--color-success);font-size:11px">Complete</span>';

      return `<tr data-id="${a.artist_id}" class="${a.artist_id === selectedId ? 'selected' : ''}">
        <td>${esc(a.display_name)}</td>
        <td>${cats}</td>
        <td><div class="identity-tags">${identityPills}</div></td>
        <td class="score-cell"><span class="score-bar"><span class="score-fill score-${lvl}" style="width:${pct}%"></span></span><span class="score-pct">${pct}%</span></td>
        <td><div class="gap-pills">${gaps}</div></td>
        <td><div class="data-icons">${dataIcons(a)}</div></td>
      </tr>`;
    }).join("");

    tbody.querySelectorAll("tr[data-id]").forEach(tr =>
      tr.addEventListener("click", () => openDetail(tr.dataset.id))
    );
  }

  function gapList(a) {
    const g = [];
    if (!a.has_bio) g.push("Bio");
    if (!a.has_cv) g.push("CV");
    if (!a.has_tearsheet) g.push("Tearsheet");
    if (!a.has_contact) g.push("Email");
    if (!a.has_images) g.push("Images");
    return g;
  }

  function dataIcons(a) {
    return [
      [ICO.fileText, a.has_bio, "Bio"],
      [ICO.clipboard, a.has_cv, "CV"],
      [ICO.sheet, a.has_tearsheet, "Tearsheet"],
      [ICO.mail, a.has_contact, "Contact"],
      [ICO.image, a.has_images, "Images"],
    ].map(([ico, has, title]) =>
      `<span class="data-icon ${has ? 'has' : 'missing'}" title="${title}">${ico}</span>`
    ).join("");
  }

  // ---------------------------------------------------------------
  // Detail panel
  // ---------------------------------------------------------------
  async function openDetail(artistId) {
    selectedId = artistId;
    location.hash = encodeURIComponent(artistId);
    renderTable();
    document.getElementById("detail-overlay").classList.remove("hidden");
    document.getElementById("detail-panel").classList.remove("hidden");
    document.getElementById("detail-body").innerHTML = '<p class="empty">Loading\u2026</p>';

    try {
      const [mRes, bRes] = await Promise.all([
        fetch(API + "/" + artistId),
        fetch(API + "/" + artistId + "/bio-content"),
      ]);
      currentDetail = await mRes.json();
      const bioData = await bRes.json();
      document.getElementById("detail-title").textContent = (currentDetail.identity || {}).display_name || artistId;
      renderDetail(currentDetail, bioData.content);
    } catch (e) {
      document.getElementById("detail-body").innerHTML = '<p style="color:var(--color-error)">Failed to load.</p>';
    }
  }

  function closeDetail() {
    selectedId = null;
    currentDetail = null;
    location.hash = "";
    document.getElementById("detail-overlay").classList.add("hidden");
    document.getElementById("detail-panel").classList.add("hidden");
    renderTable();
  }

  function renderDetail(m, bioText) {
    const id = m.identity || {};
    const tags = id.identity_tags || {};
    const contact = m.contact || {};
    const docs = m.documents || {};
    const eng = m.engagement || {};
    const img = m.images || {};
    const comp = m.completeness || {};
    const ai = m.ai_enrichment;
    const notes = m._review_notes || [];
    const fls = m.folder_locations || [];

    let h = "";

    // Completeness bar
    const pct = Math.round(comp.score * 100);
    const lvl = pct >= 80 ? "high" : pct >= 40 ? "mid" : "low";
    h += `<div class="detail-section">
      <div class="detail-score-bar"><div class="detail-score-fill score-${lvl}" style="width:${pct}%"></div></div>
      <div class="gap-pills">${(comp.gaps || []).map(g => `<span class="gap-pill">${esc(g)}</span>`).join("") || '<span style="color:var(--color-success);font-size:12px">All fields complete</span>'}</div>
    </div>`;

    // Review notes
    if (notes.length) {
      h += `<div class="detail-section"><h3>Review Notes</h3>`;
      notes.forEach((n, i) => {
        h += `<div class="review-note"><span>${esc(n)}</span><button class="btn btn-sm" onclick="resolveNote('${escA(m.artist_id)}',${i})">Resolve</button></div>`;
      });
      h += `</div>`;
    }

    // AI enrichment
    if (ai) {
      h += `<div class="detail-section ai-section"><h3>AI Enrichment
        <span class="ai-confidence ai-${ai.confidence || 'med'}">${cap(ai.confidence || "medium")}</span>
        <span class="ai-model">${esc(ai.model || "")}</span></h3>`;
      if (ai.bio_summary) h += `<div class="ai-text">${esc(ai.bio_summary)}</div>`;
      if (ai.medium) h += `<div style="font-size:13px;margin:4px 0"><strong>Medium:</strong> ${esc(ai.medium)}</div>`;
      if (ai.website) h += `<div style="font-size:13px"><strong>Website:</strong> <a href="${esc(ai.website)}" target="_blank" style="color:var(--accent)">${esc(ai.website)}</a></div>`;
      h += `<div class="ai-disclaimer">AI-generated \u2014 verify before publishing</div></div>`;
    }

    // Identity (editable)
    h += `<div class="detail-section"><h3>Identity</h3>`;
    h += editRow("Name", "edit-display-name", id.display_name || "", "text");
    h += editRow("Pronouns", "edit-pronouns", id.pronouns || "", "text", "e.g. she/her", !id.pronouns);
    h += `<div class="edit-row"><span class="edit-label">Career Stage</span><select class="edit-input" id="edit-career-stage">
      <option value="">—</option>
      <option value="emerging"${id.career_stage === "emerging" ? " selected" : ""}>Emerging</option>
      <option value="mid-career"${id.career_stage === "mid-career" ? " selected" : ""}>Mid-career</option>
      <option value="established"${id.career_stage === "established" ? " selected" : ""}>Established</option>
    </select></div>`;

    // Typed names (traditional, pseudonym, studio, trade)
    const namesByType = {};
    (id.names || []).forEach(n => { (namesByType[n.type] = namesByType[n.type] || []).push(n.name); });
    if (namesByType.traditional) h += `<div class="edit-row"><span class="edit-label">Traditional</span><span style="font-size:13px">${namesByType.traditional.map(esc).join(", ")}</span></div>`;
    if (namesByType.pseudonym) h += `<div class="edit-row"><span class="edit-label">Also</span><span style="font-size:13px;color:var(--fg-secondary)">${namesByType.pseudonym.map(esc).join(", ")}</span></div>`;
    if (namesByType.studio) h += `<div class="edit-row"><span class="edit-label">Studio</span><span style="font-size:13px;color:var(--fg-secondary)">${namesByType.studio.map(esc).join(", ")}</span></div>`;
    if (namesByType.trade) h += `<div class="edit-row"><span class="edit-label">Trade</span><span style="font-size:13px;color:var(--fg-secondary)">${namesByType.trade.map(esc).join(", ")}</span></div>`;

    // Affiliations by type
    const affsByType = {};
    (tags.affiliations || []).forEach(a => { (affsByType[a.type] = affsByType[a.type] || []).push(a.name); });
    if (affsByType.nation) h += `<div class="edit-row"><span class="edit-label">Nations</span><span style="font-size:13px">${affsByType.nation.map(esc).join(", ")}</span></div>`;
    if (affsByType.collective) h += `<div class="edit-row"><span class="edit-label">Members</span><span style="font-size:13px;color:var(--fg-secondary)">${affsByType.collective.map(esc).join(", ")}</span></div>`;
    if (affsByType.duo_partner) h += `<div class="edit-row"><span class="edit-label">Duo</span><span style="font-size:13px;color:var(--fg-secondary)">${affsByType.duo_partner.map(esc).join(", ")}</span></div>`;
    const otherAffs = Object.entries(affsByType).filter(([t]) => !["nation","collective","duo_partner"].includes(t));
    otherAffs.forEach(([type, names]) => {
      h += `<div class="edit-row"><span class="edit-label">${cap(type.replace(/_/g," "))}</span><span style="font-size:13px;color:var(--fg-secondary)">${names.map(esc).join(", ")}</span></div>`;
    });

    // Locations by type
    const locsByType = {};
    (tags.locations || []).forEach(l => { (locsByType[l.type] = locsByType[l.type] || []).push(l.place); });

    h += `<div class="detail-tags">
      ${(affsByType.nation || []).map(n => `<span class="detail-tag identity-nation">${esc(n)}</span>`).join("")}
      ${Object.entries(locsByType).map(([type, places]) => places.map(p => `<span class="detail-tag location-tag location-${type}">${esc(p)}</span>`).join("")).join("")}
      ${(tags.identities || []).map(l => `<span class="detail-tag identity-tag-self">${esc(l)}</span>`).join("")}
    </div></div>`;

    // Contact (editable)
    h += `<div class="detail-section"><h3>Contact</h3>`;
    h += editRow("Email", "edit-email", contact.email || "", "email", "artist@example.com", !contact.email);
    h += editRow("Phone", "edit-phone", contact.phone || "", "text", "(604) 555-0100", !contact.phone);
    h += editRow("Website", "edit-website", contact.website || "", "url", "https://\u2026", !contact.website);
    h += `<div style="margin-top:4px"><span class="edit-label" style="display:block;margin-bottom:2px">Notes</span><textarea class="edit-input edit-textarea" id="edit-notes" placeholder="Any notes\u2026">${esc(contact.notes || "")}</textarea></div>`;
    h += `</div>`;

    // Folder locations with cascade links
    if (fls.length) {
      h += `<div class="detail-section"><h3>Folders (${fls.length})</h3>`;
      fls.forEach(fl => {
        h += `<div class="folder-row">
          <span class="badge badge-${fl.category}">${cap(fl.category)}</span>
          ${fl.nation ? `<span class="identity-tag identity-nation">${esc(fl.nation)}</span>` : ""}
          ${fl.is_primary ? '<span class="folder-primary">(primary)</span>' : ""}
          <span class="folder-path">${esc(fl.folder_path)}</span>
          <button class="btn btn-sm btn-ghost" onclick="openFolderPath('${escA(fl.folder_path)}')" title="Open in Explorer">${ICO.folder}</button>
        </div>`;
      });
      h += `</div>`;
    }

    // Documents
    h += renderDocSection("Bios", docs.bios, bioText);
    h += renderDocSection("CVs", docs.cvs);
    h += renderDocSection("Tearsheets", docs.tearsheets);
    h += renderDocSection("Project Lists", docs.project_lists);

    // EOIs
    if (eng.eois?.length) {
      h += `<div class="detail-section"><h3>EOIs (${eng.eois.length})</h3>`;
      eng.eois.forEach(e => {
        h += `<div class="engage-item"><span class="doc-tag">EOI</span><span class="doc-link" onclick="openFile('${escA(e.file_path || "")}')">${esc(e.project_name || basename(e.file_path) || "Unknown")}</span></div>`;
      });
      h += `</div>`;
    }

    // Concept Proposals
    if (eng.concept_proposals?.length) {
      h += `<div class="detail-section"><h3>Concept Proposals (${eng.concept_proposals.length})</h3>`;
      eng.concept_proposals.forEach(p => {
        const parts = [p.project_name, p.developer].filter(Boolean);
        h += `<div class="engage-item">${p.date ? `<span class="doc-tag">${p.date}</span>` : '<span class="doc-tag">?</span>'}<span class="doc-link" onclick="openFile('${escA(p.file_path || "")}')">${esc(parts.join(" \u2014 ") || basename(p.file_path) || "Unknown")}</span></div>`;
      });
      h += `</div>`;
    }

    // Panel History
    h += `<div class="detail-section"><h3>Panel History</h3>`;
    h += `<div style="font-size:13px;margin-bottom:4px"><strong>${eng.panel_count || 0}</strong> appearances</div>`;
    if (eng.panel_history?.length) {
      eng.panel_history.forEach(p => {
        const roleLabel = p.role && p.role !== "selection_panel" ? ` <span class="doc-tag">${esc(p.role.replace(/_/g," "))}</span>` : "";
        h += `<div class="engage-item"><span class="doc-tag">${esc(p.date || "?")}</span><span style="font-size:13px">${esc(p.project || "")}</span>${roleLabel}</div>`;
      });
    }
    h += `<div id="panel-form-area"></div>`;
    h += `<button class="btn btn-sm" onclick="toggleForm('panel')">+ Add Panel Entry</button>`;
    h += `</div>`;

    // Public Art Projects (pipeline)
    const statusColors = { submitted: "var(--fg-secondary)", longlisted: "var(--color-warning)", shortlisted: "var(--accent)", awarded: "var(--color-success)", completed: "var(--cat-indigenous)" };
    h += `<div class="detail-section"><h3>Public Art Projects</h3>`;
    if (eng.public_art_projects?.length) {
      eng.public_art_projects.forEach(p => {
        const parts = [p.year, p.developer, p.project_name].filter(Boolean);
        const statusStyle = `color:${statusColors[p.status] || "var(--fg-secondary)"}`;
        h += `<div class="engage-item"><span style="font-size:13px">${esc(parts.join(" \u2014 "))}</span>${p.status ? ` <span class="doc-tag" style="${statusStyle}">${esc(p.status)}</span>` : ""}</div>`;
      });
    }
    h += `<div id="project-form-area"></div>`;
    h += `<button class="btn btn-sm" onclick="toggleForm('project')">+ Add Project</button>`;
    h += `</div>`;

    // Images
    h += `<div class="detail-section"><h3>Images</h3>`;
    h += `<div style="font-size:13px">${img.count || 0} image(s)</div>`;
    if ((img.folder_paths || []).length) {
      h += `<div class="doc-link" onclick="openFolder('${escA(m.artist_id)}')">${ICO.folder} Open image folder</div>`;
    }
    h += `</div>`;

    // Save bar + actions
    h += `<div class="save-bar">
      <button class="btn btn-primary" id="btn-save" onclick="saveChanges('${escA(m.artist_id)}')">Save Changes</button>
      <span id="save-feedback" class="save-feedback"></span>
    </div>`;

    // Actions row
    h += `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
      <span style="flex:1"></span>
      <button class="btn btn-sm" onclick="openFolder('${escA(m.artist_id)}')">${ICO.folder} Open Folder</button>
      <button class="btn btn-sm" onclick="rescanArtist('${escA(m.artist_id)}')">Rescan</button>
    </div>`;

    document.getElementById("detail-body").innerHTML = h;
  }

  function renderDocSection(title, docs, bioText) {
    if (!docs?.length) return "";
    let h = `<div class="detail-section"><h3>${title} (${docs.length})</h3>`;
    docs.forEach(d => {
      const name = basename(d.file_path) || "Unknown";
      const tag = d.is_current ? '<span class="doc-tag current">current</span>' : '<span class="doc-tag old">old</span>';
      h += `<div class="doc-link ${d.is_current ? 'current' : ''}" onclick="openFile('${escA(d.file_path || "")}')" title="${esc(d.file_path || "")}">${tag} ${esc(name)}${d.date ? " (" + d.date + ")" : ""}</div>`;
    });
    if (title === "Bios" && bioText) {
      h += `<div class="bio-content">${esc(bioText)}</div>`;
    }
    h += `</div>`;
    return h;
  }

  function editRow(label, inputId, value, type, placeholder, isMissing) {
    const cls = isMissing ? "edit-input missing-highlight" : "edit-input";
    return `<div class="edit-row"><span class="edit-label">${label}</span><input class="${cls}" id="${inputId}" type="${type || "text"}" value="${escA(value)}" placeholder="${placeholder || ""}"></div>`;
  }

  // ---------------------------------------------------------------
  // Global actions
  // ---------------------------------------------------------------
  window.openFile = function (path) {
    if (!path) return;
    fetch(API + "/open-file?path=" + encodeURIComponent(path));
  };

  window.openFolder = function (artistId) {
    fetch(API + "/" + artistId + "/open-folder");
  };

  window.openFolderPath = function (path) {
    if (!path) return;
    // Use the open-file endpoint for folders too — it opens explorer
    fetch(API + "/open-file?path=" + encodeURIComponent(path));
  };

  window.rescanArtist = async function (artistId) {
    await fetch(API + "/" + artistId + "/rescan", { method: "POST" });
    loadArtists();
    if (selectedId === artistId) openDetail(artistId);
  };

  window.resolveNote = async function (artistId, index) {
    await fetch(API + "/" + artistId + "/resolve-note", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index }),
    });
    if (selectedId === artistId) openDetail(artistId);
  };

  window.saveChanges = async function (artistId) {
    const btn = document.getElementById("btn-save");
    const fb = document.getElementById("save-feedback");
    btn.disabled = true;
    fb.textContent = "Saving\u2026";
    fb.className = "save-feedback";

    const data = {
      identity: {
        display_name: val("edit-display-name"),
        pronouns: val("edit-pronouns") || null,
        career_stage: val("edit-career-stage") || null,
      },
      contact: {
        email: val("edit-email") || null,
        phone: val("edit-phone") || null,
        website: val("edit-website") || null,
        notes: val("edit-notes") || null,
      },
    };

    try {
      const r = await fetch(API + "/" + artistId + "/manifest", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (r.ok) {
        fb.textContent = "\u2713 Saved";
        fb.className = "save-feedback save-ok";
        loadArtists();
      } else {
        fb.textContent = "\u2717 Error";
        fb.className = "save-feedback save-err";
      }
    } catch (e) {
      fb.textContent = "\u2717 Network error";
      fb.className = "save-feedback save-err";
    }
    btn.disabled = false;
  };

  window.toggleForm = function (type) {
    const area = document.getElementById(type + "-form-area");
    if (area.innerHTML) { area.innerHTML = ""; return; }
    if (type === "panel") {
      area.innerHTML = `<div class="inline-form">
        <input type="date" id="new-panel-date">
        <input type="text" id="new-panel-project" placeholder="Project name" style="flex:1">
        <select id="new-panel-role" style="padding:4px 6px;font-size:13px;border:1px solid var(--border);border-radius:2px">
          <option value="selection_panel">Selection Panel</option>
          <option value="community_advisor">Community Advisor</option>
          <option value="cultural_advisor">Cultural Advisor</option>
          <option value="juror">Juror</option>
        </select>
        <button class="btn btn-sm btn-primary" onclick="submitPanel()">Add</button>
        <button class="btn btn-sm" onclick="toggleForm('panel')">Cancel</button>
      </div>`;
    } else {
      area.innerHTML = `<div class="inline-form" style="flex-direction:column;align-items:stretch">
        <div style="display:flex;gap:6px"><input type="text" id="new-proj-name" placeholder="Project name*" style="flex:1"><input type="text" id="new-proj-dev" placeholder="Developer" style="flex:1"></div>
        <div style="display:flex;gap:6px">
          <input type="text" id="new-proj-year" placeholder="Year" style="width:70px">
          <input type="text" id="new-proj-role" placeholder="Role" style="flex:1">
          <select id="new-proj-status" style="flex:1;padding:4px 6px;font-size:13px;border:1px solid var(--border);border-radius:2px">
            <option value="submitted">Submitted</option>
            <option value="longlisted">Longlisted</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="awarded">Awarded</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div style="display:flex;gap:6px"><button class="btn btn-sm btn-primary" onclick="submitProject()">Add</button><button class="btn btn-sm" onclick="toggleForm('project')">Cancel</button></div>
      </div>`;
    }
  };

  window.submitPanel = async function () {
    if (!selectedId) return;
    await fetch(API + "/" + selectedId + "/panel", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: val("new-panel-date"), project: val("new-panel-project"), role: val("new-panel-role") || "selection_panel" }),
    });
    openDetail(selectedId);
  };

  window.submitProject = async function () {
    const name = val("new-proj-name");
    if (!name) return;
    await fetch(API + "/" + selectedId + "/project", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: name,
        developer: val("new-proj-dev") || null,
        year: val("new-proj-year") || null,
        role: val("new-proj-role") || null,
        status: val("new-proj-status") || "submitted",
      }),
    });
    openDetail(selectedId);
  };

  // ---------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------
  function esc(s) { if (!s) return ""; const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function escA(s) { return (s || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'"); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
  function basename(p) { return p ? p.split(/[/\\]/).pop() : ""; }
  function val(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }
})();
