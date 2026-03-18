/* Reconciliation panel — standalone page at /artists-recon, also usable embedded */
(function () {
  "use strict";

  const API = "/artists";
  let reconData = {};
  let adminFiles = [];
  let activeTab = "orphan_eois";

  // ------------------------------------------------------------------
  // Public interface
  // ------------------------------------------------------------------

  window.Recon = { init, load, _action: reconAction, _merge: mergeValues };

  function init() {
    document.querySelectorAll(".recon-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        activeTab = tab.dataset.recon;
        document.querySelectorAll(".recon-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        render();
      });
    });
  }

  async function load() {
    try {
      const [reconRes, adminRes] = await Promise.all([
        fetch(API + "/reconciliation"),
        fetch(API + "/admin-files"),
      ]);
      reconData = await reconRes.json();
      adminFiles = await adminRes.json();
      updateCounts();
      render();
    } catch (e) {
      console.error("Reconciliation:", e);
      document.getElementById("recon-content").innerHTML =
        '<p class="empty">Failed to load reconciliation data</p>';
    }
  }

  // ------------------------------------------------------------------
  // Tab counts
  // ------------------------------------------------------------------

  function updateCounts() {
    const counts = {
      "recon-count-eois":      "orphan_eois",
      "recon-count-proposals":  "orphan_proposals",
      "recon-count-stalled":    "stalled_projects",
      "recon-count-fuzzy":      "fuzzy_matches",
      "recon-count-panels":     "panel_gaps",
      "recon-count-dupes":      "duplicate_artists",
      "recon-count-affs":       "affiliation_variants",
      "recon-count-ids":        "identity_inconsistencies",
      "recon-count-aliases":    "alias_conflicts",
      "recon-count-locs":       "location_variants",
    };
    for (const [elId, key] of Object.entries(counts)) {
      const el = document.getElementById(elId);
      if (el) el.textContent = (reconData[key] || []).length;
    }
    // Unattributed files count
    const unEl = document.getElementById("recon-count-unattributed");
    if (unEl) unEl.textContent = adminFiles.length;
  }

  // ------------------------------------------------------------------
  // Render active tab
  // ------------------------------------------------------------------

  const renderers = {
    orphan_eois:               renderOrphanEois,
    orphan_proposals:          renderOrphanProposals,
    stalled_projects:          renderStalled,
    fuzzy_matches:             renderFuzzy,
    panel_gaps:                renderPanelGaps,
    duplicate_artists:         renderDuplicates,
    affiliation_variants:      renderVariants("merge_affiliation"),
    identity_inconsistencies:  renderVariants("merge_identity"),
    location_variants:         renderVariants("merge_location"),
    alias_conflicts:           renderAliasConflicts,
    unattributed_files:        renderUnattributed,
  };

  function render() {
    const el = document.getElementById("recon-content");

    if (activeTab === "unattributed_files") {
      el.innerHTML = renderUnattributed(adminFiles);
      return;
    }

    const items = reconData[activeTab] || [];

    if (!items.length) {
      el.innerHTML = '<p class="empty">No items</p>';
      return;
    }

    const fn = renderers[activeTab];
    if (fn) {
      el.innerHTML = fn(items);
    } else {
      el.innerHTML = '<p class="empty">Unknown tab</p>';
    }
  }

  // ------------------------------------------------------------------
  // Engagement renderers
  // ------------------------------------------------------------------

  function renderOrphanEois(items) {
    return items.map(item => `
      <div class="recon-item">
        ${artistLink(item)}
        <span class="recon-meta">${esc(item.project_name)}</span>
        <button class="btn btn-sm btn-primary" onclick="Recon._action('link_eoi','${escA(item.artist_id)}','${escA(item.project_name)}')">Link</button>
        <button class="btn btn-sm" onclick="Recon._action('dismiss','${escA(item.artist_id)}','')">Dismiss</button>
      </div>
    `).join("");
  }

  function renderOrphanProposals(items) {
    return items.map(item => `
      <div class="recon-item">
        ${artistLink(item)}
        <span class="recon-meta">${esc(item.project_name)}${item.developer ? " — " + esc(item.developer) : ""}</span>
        <button class="btn btn-sm btn-primary" onclick="Recon._action('link_eoi','${escA(item.artist_id)}','${escA(item.project_name)}')">Link</button>
        <button class="btn btn-sm" onclick="Recon._action('dismiss','${escA(item.artist_id)}','')">Dismiss</button>
      </div>
    `).join("");
  }

  function renderStalled(items) {
    return items.map(item => `
      <div class="recon-item">
        ${artistLink(item)}
        <span class="recon-meta">${esc(item.project_name)} [${esc(item.status)}]</span>
        <button class="btn btn-sm btn-primary" onclick="Recon._action('advance_status','${escA(item.artist_id)}','',${item.project_index},'completed')">Complete</button>
        <button class="btn btn-sm" onclick="Recon._action('dismiss','${escA(item.artist_id)}','')">Dismiss</button>
      </div>
    `).join("");
  }

  function renderFuzzy(items) {
    return items.map(item => `
      <div class="recon-item">
        ${artistLink(item)}
        <span class="recon-meta">${esc(item.source_name)} &rarr; ${esc(item.match_name)}</span>
        <span class="recon-match-score">${Math.round(item.score * 100)}%</span>
        <button class="btn btn-sm btn-primary" onclick="Recon._action('link_eoi','${escA(item.artist_id)}','${escA(item.source_name)}')">Link</button>
        <button class="btn btn-sm" onclick="Recon._action('dismiss','${escA(item.artist_id)}','')">Dismiss</button>
      </div>
    `).join("");
  }

  function renderPanelGaps(items) {
    return items.map(item => `
      <div class="recon-item">
        ${artistLink(item)}
        <span class="recon-meta">${item.panel_count} panel(s), no projects</span>
      </div>
    `).join("");
  }

  // ------------------------------------------------------------------
  // Data quality renderers
  // ------------------------------------------------------------------

  function renderDuplicates(items) {
    return items.map(item => `
      <div class="recon-item">
        <a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(item.artist_id_a)}">${esc(item.name_a)}</a>
        <span class="recon-meta">&harr;</span>
        <a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(item.artist_id_b)}">${esc(item.name_b)}</a>
        <span class="recon-match-score">${Math.round(item.score * 100)}%</span>
      </div>
    `).join("");
  }

  function renderVariants(actionType) {
    return function (items) {
      return items.map(item => `
        <div class="recon-item">
          <span class="recon-name">${esc(item.value_a)} <span style="color:var(--fg-disabled);font-size:11px">(${item.count_a})</span></span>
          <span class="recon-meta">&harr;</span>
          <span class="recon-name">${esc(item.value_b)} <span style="color:var(--fg-disabled);font-size:11px">(${item.count_b})</span></span>
          <span class="recon-match-score">${Math.round(item.score * 100)}%</span>
          <button class="btn btn-sm btn-primary" onclick="Recon._merge('${actionType}','${escA(item.value_b)}','${escA(item.value_a)}')">Keep "${esc(item.value_a)}"</button>
          <button class="btn btn-sm" onclick="Recon._merge('${actionType}','${escA(item.value_a)}','${escA(item.value_b)}')">Keep "${esc(item.value_b)}"</button>
          <button class="btn btn-sm" onclick="Recon._action('dismiss','','')">Dismiss</button>
        </div>
      `).join("");
    };
  }

  function renderAliasConflicts(items) {
    return items.map(item => `
      <div class="recon-item">
        <span class="recon-name" style="font-weight:600">${esc(item.shared_name)}</span>
        <span class="recon-meta">shared by: ${item.artists.map(a =>
          `<a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(a.artist_id)}">${esc(a.display_name)}</a> (${esc(a.type)})`
        ).join(", ")}</span>
      </div>
    `).join("");
  }

  // ------------------------------------------------------------------
  // Unattributed files renderer
  // ------------------------------------------------------------------

  function renderUnattributed(items) {
    if (!items || !items.length) {
      return '<p class="empty">No unattributed files</p>';
    }

    return `
      <table class="ranking-table">
        <thead>
          <tr>
            <th>File</th>
            <th>Folder</th>
            <th>Category</th>
            <th>Type</th>
            <th>Candidate</th>
            <th>Score</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(f => `
            <tr>
              <td title="${esc(f.file_path)}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.file_name)}</td>
              <td>${esc(f.folder_name)}</td>
              <td><span class="badge badge-${f.category}">${cap(f.category)}</span></td>
              <td style="font-size:11px">${esc(f.file_type)}</td>
              <td>${f.candidate_display_name
                ? `<a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(f.candidate_artist_id)}">${esc(f.candidate_display_name)}</a>`
                : '<span style="color:var(--fg-disabled)">None</span>'
              }</td>
              <td>${f.match_score ? Math.round(f.match_score * 100) + '%' : '—'}</td>
              <td style="white-space:nowrap">
                ${f.candidate_artist_id
                  ? `<button class="btn btn-sm btn-primary" onclick="attributeFile('${escA(f.file_id)}','${escA(f.candidate_artist_id)}')">Accept</button>`
                  : ''
                }
                <button class="btn btn-sm" onclick="attributeFileSearch('${escA(f.file_id)}')">Search</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  async function reconAction(action, artistId, projectName, projectIndex, newStatus) {
    const body = { action, artist_id: artistId };
    if (projectName) body.project_name = projectName;
    if (projectName) body.eoi_name = projectName;
    if (projectIndex !== undefined) body.project_index = projectIndex;
    if (newStatus) body.new_status = newStatus;

    await fetch(API + "/reconciliation/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    load();
  }

  async function mergeValues(action, oldValue, newValue) {
    await fetch(API + "/reconciliation/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, old_value: oldValue, new_value: newValue }),
    });
    load();
  }

  // Attribution actions (global scope for onclick)
  window.attributeFile = async function (fileId, artistId) {
    await fetch(API + "/admin-files/" + encodeURIComponent(fileId) + "/attribute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artist_id: artistId }),
    });
    load();
  };

  window.attributeFileSearch = async function (fileId) {
    const query = prompt("Search for artist name:");
    if (!query) return;

    const res = await fetch(API + "?q=" + encodeURIComponent(query) + "&limit=10");
    const artists = await res.json();

    if (!artists.length) {
      alert("No artists found for: " + query);
      return;
    }

    // Show simple selection
    const choices = artists.map((a, i) => `${i + 1}. ${a.display_name} (${a.artist_id})`).join("\n");
    const pick = prompt("Select artist:\n" + choices + "\n\nEnter number:");
    if (!pick) return;

    const idx = parseInt(pick, 10) - 1;
    if (idx >= 0 && idx < artists.length) {
      await window.attributeFile(fileId, artists[idx].artist_id);
    }
  };

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  function artistLink(item) {
    return `<span class="recon-name"><a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(item.artist_id)}">${esc(item.display_name)}</a></span>`;
  }

  function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function escA(s) {
    return (s || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  function cap(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }
})();
