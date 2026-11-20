const state = {
  data: null,
  filter: "all",
  activeId: null,
};

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function highlightText(text, terms, cls) {
  let html = escapeHtml(text);
  for (const term of terms || []) {
    const safe = escapeHtml(term);
    if (!safe) continue;
    html = html.replace(safe, `<mark class="${cls}">${safe}</mark>`);
  }
  return html;
}

function visibleCases() {
  if (!state.data) return [];
  if (state.filter === "all") return state.data.cases;
  return state.data.cases.filter((c) => c.category === state.filter);
}

function activeCase() {
  const list = visibleCases();
  return list.find((c) => c.id === state.activeId) || list[0] || null;
}

function renderHarnesses() {
  const ul = document.getElementById("harness-list");
  const harnesses = state.data?.harnesses || {};
  const labels = {
    opencode_mcp: "OpenCode MCP",
    t3_antigravity_mcp: "T3 Antigravity MCP",
    agy_cli_mcp: "Antigravity CLI MCP",
    codex_mcp: "Codex MCP",
    shared_skill: "Shared Skill",
  };
  ul.innerHTML = Object.entries(labels)
    .map(([key, label]) => {
      const ok = Boolean(harnesses[key]);
      return `<li class="harness-item">
        <span>${escapeHtml(label)}</span>
        <span class="mini-status ${ok ? "clean" : "alert"}">${ok ? "connected" : "missing"}</span>
      </li>`;
    })
    .join("");
}

function renderCaseList() {
  const list = visibleCases();
  const current = activeCase();
  if (current) state.activeId = current.id;

  const container = document.getElementById("case-list");
  container.innerHTML = list
    .map((item) => {
      const isCurrent = current && item.id === current.id;
      return `<li>
        <button class="case-btn" type="button" data-case-id="${escapeHtml(item.id)}" aria-current="${isCurrent ? "true" : "false"}">
          <span class="case-btn-top">
            <span class="case-btn-title">${escapeHtml(item.title)}</span>
            <span class="mini-status ${escapeHtml(item.tone)}">${escapeHtml(item.badge)}</span>
          </span>
          <span class="case-btn-sub">${escapeHtml(item.subtitle)}</span>
        </button>
      </li>`;
    })
    .join("");

  const index = current ? list.findIndex((c) => c.id === current.id) : -1;
  document.getElementById("step-counter").textContent =
    index >= 0 ? `${index + 1} / ${list.length}` : "0 / 0";
  document.getElementById("prev-button").disabled = index <= 0;
  document.getElementById("next-button").disabled = index < 0 || index >= list.length - 1;
}

function renderTranslationStage(item) {
  const pair = item.output.pairs[0];
  const hlClass = item.tone === "clean" ? "hl-clean" : "hl-alert";
  const srcHtml = highlightText(item.input.source_text, item.highlights?.source, hlClass);
  const tgtHtml = highlightText(item.input.translation_text, item.highlights?.translation, hlClass);

  const quoteBlock =
    item.input.source_quote || item.input.translation_quote
      ? `<div class="quote-check-row">
          <span>source_quote: "${escapeHtml(item.input.source_quote || "")}"</span>
          <span>translation_quote: "${escapeHtml(item.input.translation_quote || "")}"</span>
        </div>`
      : "";

  const flagsHtml =
    pair.flags.length === 0
      ? `<div class="clean-callout">
          status: clean · source_numbers=${JSON.stringify(pair.source_numbers)} == translation_numbers=${JSON.stringify(pair.translation_numbers)} · flags=[]
        </div>`
      : `<p class="section-subhead">Detected drift flags (${pair.flags.length})</p>
        <div class="flag-list">
          ${pair.flags
            .map(
              (flag) => `<div class="flag-card">
                <span class="flag-pill">${escapeHtml(flag.category)} · ${escapeHtml(flag.confidence)}</span>
                <div class="flag-text">
                  <div>${escapeHtml(flag.explanation)}</div>
                  <div class="flag-detail">source: ${escapeHtml(flag.source_quote ?? "null")} | translation: ${escapeHtml(flag.translation_quote ?? "null")}</div>
                </div>
              </div>`
            )
            .join("")}
        </div>`;

  return `
    <div class="compare-grid">
      <div class="text-box">
        <div class="text-box-head">
          <span>Source</span>
          <span>${escapeHtml(pair.source_language)} · ${escapeHtml(pair.source_modality)}${pair.source_legal_state ? ` · ${escapeHtml(pair.source_legal_state)}` : ""}</span>
        </div>
        <p class="text-body">${srcHtml}</p>
        ${quoteBlock}
      </div>
      <div class="text-box">
        <div class="text-box-head">
          <span>Translation</span>
          <span>${escapeHtml(pair.target_language)} · ${escapeHtml(pair.translation_modality)}${pair.translation_legal_state ? ` · ${escapeHtml(pair.translation_legal_state)}` : ""}</span>
        </div>
        <p class="text-body">${tgtHtml}</p>
      </div>
    </div>
    ${flagsHtml}
  `;
}

function renderDiffStage(item) {
  const out = item.output;
  const beforeHtml = highlightText(item.input.before_text, item.highlights?.before, "hl-alert");
  const afterHtml = highlightText(item.input.after_text, item.highlights?.after, "hl-clean");

  const buckets = out.changes
    .map(
      (ch) => `<div class="bucket-card">
        <h3>${escapeHtml(ch.category)}</h3>
        <div class="bucket-line del">- ${escapeHtml(ch.removed.join(", ") || "(none)")}</div>
        <div class="bucket-line add">+ ${escapeHtml(ch.added.join(", ") || "(none)")}</div>
      </div>`
    )
    .join("");

  return `
    <div class="compare-grid">
      <div class="text-box">
        <div class="text-box-head">
          <span>Before (v1)</span>
          <span>sha256: ${escapeHtml(out.before_sha256.slice(0, 10))}…</span>
        </div>
        <p class="text-body">${beforeHtml}</p>
      </div>
      <div class="text-box">
        <div class="text-box-head">
          <span>After (v2)</span>
          <span>sha256: ${escapeHtml(out.after_sha256.slice(0, 10))}…</span>
        </div>
        <p class="text-body">${afterHtml}</p>
      </div>
    </div>
    <p class="section-subhead">Classified changes (${out.changes.length} categories)</p>
    <div class="bucket-grid">${buckets}</div>
  `;
}

function renderLineageStage(item) {
  const out = item.output;
  const inputHtml = item.input.items
    .map(
      (src) => `<span class="meta-chip">${escapeHtml(src.publisher)} (${escapeHtml(src.credited_origin)})</span>`
    )
    .join("");

  const clustersHtml = out.clusters
    .map(
      (cluster) => `<div class="cluster-card ${cluster.member_ids.length > 1 ? "shared" : ""}">
        <div class="cluster-top">
          <span class="cluster-title">${escapeHtml(cluster.canonical_origin)}</span>
          <span class="mini-status ${cluster.member_ids.length > 1 ? "clean" : "alert"}">
            ${escapeHtml(cluster.member_ids.length)} source(s) · ${escapeHtml(cluster.basis)}
          </span>
        </div>
        <div class="meta-chips">
          <span class="meta-chip">independence: ${escapeHtml(cluster.independence_hint)}</span>
          <span class="meta-chip">languages: ${escapeHtml(cluster.languages.join(", "))}</span>
          <span class="meta-chip">aliases: ${escapeHtml(cluster.origins_seen.join(" / "))}</span>
        </div>
      </div>`
    )
    .join("");

  return `
    <div class="text-box">
      <div class="text-box-head">
        <span>Input wire &amp; local items (${out.source_count})</span>
        <span>syndication collapsed: ${out.syndication_collapsed}</span>
      </div>
      <div class="meta-chips">${inputHtml}</div>
    </div>
    <p class="section-subhead">Resolved independent lineages (${out.independent_lineage_count})</p>
    <div class="cluster-list">${clustersHtml}</div>
  `;
}

function renderRankingStage(item) {
  const out = item.output;
  const excerptsHtml = out.excerpts
    .map(
      (ex) => `<div class="excerpt-card">
        <div class="excerpt-top">
          <span class="excerpt-title">${escapeHtml(ex.title)} · ${escapeHtml(ex.publisher)}</span>
          <span class="score-bar-wrap">
            <span class="score-bar"><span class="score-fill" style="width:${Math.round(ex.relevance * 100)}%"></span></span>
            <span>${ex.relevance.toFixed(2)} (${escapeHtml(ex.scoring_method)})</span>
          </span>
        </div>
        <p class="text-body">${escapeHtml(ex.excerpt)}</p>
        <div class="meta-chips">
          <span class="meta-chip">chars ${ex.char_start}-${ex.char_end}</span>
          <span class="meta-chip">${escapeHtml(ex.cluster_id)}</span>
          <span class="meta-chip">ledger status: candidate</span>
        </div>
      </div>`
    )
    .join("");

  return `
    <div class="text-box">
      <div class="text-box-head">
        <span>Claim under review</span>
        <span>${out.documents_processed} input docs -> ${out.excerpts.length} unique excerpts</span>
      </div>
      <p class="text-body">${escapeHtml(out.claim)}</p>
    </div>
    <p class="section-subhead">Ranked candidate evidence</p>
    <div class="excerpt-list">${excerptsHtml}</div>
  `;
}

function renderStage() {
  const item = activeCase();
  if (!item) return;

  document.getElementById("tool-tag").textContent = `btl · ${item.tool}`;
  document.getElementById("case-title").textContent = item.title;
  document.getElementById("case-summary").textContent = item.summary;

  const badge = document.getElementById("outcome-badge");
  badge.textContent = item.badge;
  badge.className = `outcome-badge ${item.tone}`;

  const body = document.getElementById("stage-body");
  if (item.tool === "check_translation") {
    body.innerHTML = renderTranslationStage(item);
  } else if (item.tool === "diff_editions") {
    body.innerHTML = renderDiffStage(item);
  } else if (item.tool === "cluster_origins") {
    body.innerHTML = renderLineageStage(item);
  } else {
    body.innerHTML = renderRankingStage(item);
  }

  document.getElementById("cli-command").textContent = item.command;
  document.getElementById("json-output").textContent = JSON.stringify(item.output, null, 2);
}

function selectCase(caseId) {
  state.activeId = caseId;
  window.history.replaceState(null, "", `#case=${encodeURIComponent(caseId)}`);
  renderCaseList();
  renderStage();
}

function stepCase(delta) {
  const list = visibleCases();
  const current = activeCase();
  if (!current || list.length === 0) return;
  const idx = list.findIndex((c) => c.id === current.id);
  const next = list[idx + delta];
  if (next) selectCase(next.id);
}

function wireEvents() {
  document.querySelectorAll(".filter-button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter || "all";
      document.querySelectorAll(".filter-button").forEach((b) => {
        b.setAttribute("aria-pressed", b === btn ? "true" : "false");
      });
      const list = visibleCases();
      if (list.length > 0 && !list.some((c) => c.id === state.activeId)) {
        state.activeId = list[0].id;
      }
      renderCaseList();
      renderStage();
    });
  });

  document.getElementById("case-list").addEventListener("click", (event) => {
    const btn = event.target.closest(".case-btn");
    if (btn?.dataset.caseId) selectCase(btn.dataset.caseId);
  });

  document.getElementById("prev-button").addEventListener("click", () => stepCase(-1));
  document.getElementById("next-button").addEventListener("click", () => stepCase(1));

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      stepCase(-1);
    } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      stepCase(1);
    }
  });
}

async function init() {
  const resp = await fetch("./data/cases.json");
  if (!resp.ok) {
    document.getElementById("case-title").textContent = "Failed to load recorded cases.";
    return;
  }
  state.data = await resp.json();
  const hashMatch = window.location.hash.match(/case=([^&]+)/);
  if (hashMatch) {
    state.activeId = decodeURIComponent(hashMatch[1]);
  }
  renderHarnesses();
  renderCaseList();
  renderStage();
  wireEvents();
}

init();
