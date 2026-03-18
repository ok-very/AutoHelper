/* Lists Health page */
(function () {
  "use strict";

  const API = "/artists";

  document.addEventListener("DOMContentLoaded", () => {
    reload();
    document.getElementById("btn-reload").addEventListener("click", reload);
  });

  async function reload() {
    await Promise.all([loadStats(), loadHealth()]);
  }

  // ------------------------------------------------------------------
  // Stats (reuses /artists/stats)
  // ------------------------------------------------------------------
  async function loadStats() {
    try {
      const r = await fetch(API + "/stats");
      const d = await r.json();
      document.getElementById("stats-section").style.display = "";
      document.getElementById("stat-total").textContent = d.total;
      document.getElementById("stat-avg").textContent = Math.round(d.avg_completeness * 100) + "%";
      document.getElementById("stat-review").textContent = d.needs_review || 0;

      const gapCount = d.total - (d.by_review_status?.approved || 0);
      document.getElementById("stat-gaps").textContent = gapCount;

      // Completeness chart
      const chart = document.getElementById("completeness-chart");
      const fields = d.completeness_by_field || {};
      const labels = { has_bio: "Bio", has_cv: "CV", has_tearsheet: "Tearsheet", has_contact: "Email", has_images: "Images" };
      chart.innerHTML = Object.entries(labels).map(([k, l]) => {
        const pct = Math.round((fields[k] || 0) * 100);
        return `<div class="chart-row"><span class="chart-label">${l}</span><div class="chart-bar-track"><div class="chart-bar-fill" style="width:${pct}%"></div></div><span class="chart-pct">${pct}%</span></div>`;
      }).join("");
    } catch (e) { console.error("Stats:", e); }
  }

  // ------------------------------------------------------------------
  // Health report
  // ------------------------------------------------------------------
  async function loadHealth() {
    try {
      const r = await fetch(API + "/health");
      const d = await r.json();

      renderRanking(d.ranking || []);
      renderGapAnalysis(d.gap_analysis || {});
      renderBroken(d.broken || []);
      renderEnrichment(d.enrichment || []);
      renderReviewQueue(d.review_queue || []);

      if (d.ranking) {
        const withGaps = d.ranking.filter(a => a.score < 1.0).length;
        document.getElementById("stat-gaps").textContent = withGaps;
      }
    } catch (e) {
      console.error("Health:", e);
    }
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------
  function renderRanking(ranking) {
    const tbody = document.getElementById("ranking-tbody");
    if (!ranking.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">No artists scanned yet</td></tr>';
      return;
    }
    tbody.innerHTML = ranking.map((a, i) => {
      const pct = Math.round(a.score * 100);
      const lvl = pct >= 80 ? "high" : pct >= 40 ? "mid" : "low";
      const cats = (a.categories || []).map(c => `<span class="badge badge-${c}">${cap(c)}</span>`).join("");
      const gaps = (a.gaps || []).map(g => `<span class="gap-pill">${esc(g)}</span>`).join("") || '<span style="color:var(--color-success);font-size:11px">Complete</span>';
      return `<tr>
        <td>${i + 1}</td>
        <td><a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(a.artist_id)}">${esc(a.display_name)}</a></td>
        <td>${cats}</td>
        <td class="score-cell"><span class="score-bar"><span class="score-fill score-${lvl}" style="width:${pct}%"></span></span><span class="score-pct">${pct}%</span></td>
        <td><div class="gap-pills">${gaps}</div></td>
      </tr>`;
    }).join("");
  }

  function renderGapAnalysis(gaps) {
    const el = document.getElementById("gap-analysis");
    const labels = { bio: "Bio", cv: "CV", tearsheet: "Tearsheet", email: "Email", phone: "Phone", website: "Website", images: "Images", pronouns: "Pronouns" };

    if (!Object.keys(gaps).length) {
      el.innerHTML = '<p class="empty">No data</p>';
      return;
    }

    el.innerHTML = Object.entries(labels).map(([key, label]) => {
      const data = gaps[key] || { missing: 0, total: 0 };
      const pct = data.total > 0 ? Math.round(data.missing / data.total * 100) : 0;
      return `<div class="gap-field-card">
        <h4>${label}</h4>
        <div class="gap-count">${data.missing}</div>
        <div class="gap-pct">${pct}% missing</div>
      </div>`;
    }).join("");
  }

  function renderBroken(broken) {
    const el = document.getElementById("broken-list");
    if (!broken.length) {
      el.innerHTML = '<p class="empty">No broken items</p>';
      return;
    }
    el.innerHTML = broken.map(b => `
      <div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:13px">
        <span style="flex:1">${esc(b.display_name)} <span style="color:var(--fg-disabled);font-size:11px">${esc(b.reason)}</span></span>
        <button class="btn btn-sm" onclick="rescan('${escA(b.artist_id)}')">Rescan</button>
      </div>
    `).join("");
  }

  function renderEnrichment(enrichment) {
    const el = document.getElementById("enrichment-list");
    if (!enrichment.length) {
      el.innerHTML = '<p class="empty">All artists well-enriched</p>';
      return;
    }
    el.innerHTML = enrichment.slice(0, 50).map(a => `
      <div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:13px">
        <a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(a.artist_id)}" style="flex:1">${esc(a.display_name)}</a>
        <div class="gap-pills">${(a.missing || []).map(g => `<span class="gap-pill">${esc(g)}</span>`).join("")}</div>
      </div>
    `).join("");
  }

  function renderReviewQueue(queue) {
    const el = document.getElementById("review-queue");
    if (!queue.length) {
      el.innerHTML = '<p class="empty">No items pending review</p>';
      return;
    }
    el.innerHTML = '<table class="ranking-table"><thead><tr><th>Artist</th><th>Status</th><th>Notes</th><th>Actions</th></tr></thead><tbody>' +
      queue.map(a => `<tr data-artist-id="${escA(a.artist_id)}">
        <td><a class="clickable-name" href="/artists-dashboard#${encodeURIComponent(a.artist_id)}">${esc(a.display_name)}</a></td>
        <td><span class="status-badge badge-review">${esc(a.review_status)}</span></td>
        <td style="font-size:12px;color:var(--fg-secondary)">${a.note_count} note(s)</td>
        <td style="white-space:nowrap">
          <button class="btn btn-sm btn-success" onclick="setReviewStatus('${escA(a.artist_id)}','approved')">Approve</button>
          <button class="btn btn-sm btn-warning" onclick="setReviewStatus('${escA(a.artist_id)}','flagged')">Flag</button>
          <button class="btn btn-sm btn-danger" onclick="setReviewStatus('${escA(a.artist_id)}','rejected')">Reject</button>
        </td>
      </tr>`).join("") +
      '</tbody></table>';
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------
  window.rescan = async function (artistId) {
    await fetch(API + "/" + artistId + "/rescan", { method: "POST" });
    reload();
  };

  window.setReviewStatus = async function (artistId, status) {
    await fetch(API + "/" + artistId + "/review", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    reload();
  };

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function esc(s) { if (!s) return ""; const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function escA(s) { return (s || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'"); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
})();
