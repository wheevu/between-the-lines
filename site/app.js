const TAB_SHORT = {
  "ko-vi-scale-clean": ["01", "KO -> VI Scale"],
  "fund-allocation-drift": ["02", "Fund Drift"],
  "modality-unanchored-quote": ["03", "Hedged Quote"],
  "redemption-clause-diff": ["04", "Clause Diff"],
  "cross-script-wire-clustering": ["05", "Wire Lineage"],
  "deduped-passage-ranking": ["06", "Evidence Rank"],
};

const state = {
  data: null,
  activeId: null,
  focusedFlag: null,
  diffMode: "redline",
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function activeCase() {
  const cases = state.data?.cases || [];
  return cases.find((c) => c.id === state.activeId) || cases[0] || null;
}

function annotatePhrases(text, items) {
  let html = esc(text);
  for (const item of items) {
    const safe = esc(item.phrase);
    if (!safe || !html.includes(safe)) continue;
    const spot = state.focusedFlag === item.index ? " is-spotlight" : "";
    const badge = item.num
      ? `<span class="callout-num ${item.tone || ""}">${item.num}</span>`
      : "";
    html = html.replace(
      safe,
      `<span class="${item.cls}${spot}" data-flag-index="${item.index ?? ""}">${safe}${badge}</span>`
    );
  }
  return html;
}

function renderTabs() {
  const cases = state.data?.cases || [];
  const current = activeCase();
  if (current) state.activeId = current.id;

  const tabsEl = document.getElementById("dossier-tabs");
  tabsEl.innerHTML = cases
    .map((item, idx) => {
      const [num, shortLabel] = TAB_SHORT[item.id] || [String(idx + 1).padStart(2, "0"), item.title];
      const selected = current && item.id === current.id;
      return `<button
        class="dossier-tab"
        type="button"
        role="tab"
        data-case-id="${esc(item.id)}"
        aria-selected="${selected ? "true" : "false"}"
      >
        <span class="tab-top">
          <span class="tab-num">${esc(num)}</span>
          <span class="tab-dot ${esc(item.tone)}" title="${esc(item.badge)}"></span>
        </span>
        <span class="tab-label">${esc(shortLabel)}</span>
      </button>`;
    })
    .join("");

  const index = current ? cases.findIndex((c) => c.id === current.id) : -1;
  document.getElementById("nav-pos").textContent =
    index >= 0 ? `${String(index + 1).padStart(2, "0")} / ${String(cases.length).padStart(2, "0")}` : "00 / 00";
  document.getElementById("prev-btn").disabled = index <= 0;
  document.getElementById("next-btn").disabled = index < 0 || index >= cases.length - 1;
}

function renderHarnesses() {
  const harnesses = state.data?.harnesses || {};
  const labels = {
    opencode_mcp: "OpenCode MCP",
    t3_antigravity_mcp: "T3 Antigravity",
    agy_cli_mcp: "Antigravity CLI",
    codex_mcp: "Codex MCP",
  };
  document.getElementById("harness-grid").innerHTML = Object.entries(labels)
    .map(([key, label]) => {
      const ok = Boolean(harnesses[key]);
      return `<li><span>${esc(label)}</span><span class="harness-ok">${ok ? "connected" : "off"}</span></li>`;
    })
    .join("");
}

function buildTranslationAnnotations(item) {
  const pair = item.output.pairs[0];
  if (pair.flags.length === 0) {
    return {
      srcItems: (item.highlights?.source || []).map((p) => ({
        phrase: p,
        cls: "mark-clean",
        tone: "clean",
        num: "✓",
        index: 0,
      })),
      tgtItems: (item.highlights?.translation || []).map((p) => ({
        phrase: p,
        cls: "mark-clean",
        tone: "clean",
        num: "✓",
        index: 0,
      })),
    };
  }

  const srcItems = [];
  const tgtItems = [];
  pair.flags.forEach((flag, idx) => {
    const n = idx + 1;
    if (flag.category === "number") {
      srcItems.push({ phrase: item.highlights?.source?.[1] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
      tgtItems.push({ phrase: item.highlights?.translation?.[0] || flag.translation_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "negation") {
      srcItems.push({ phrase: item.highlights?.source?.[0] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "legal_state_shift") {
      srcItems.push({ phrase: item.highlights?.source?.[2] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
      tgtItems.push({ phrase: item.highlights?.translation?.[1] || flag.translation_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "modality_shift") {
      srcItems.push({ phrase: item.highlights?.source?.[0] || flag.source_quote, cls: "mark-ochre", tone: "ochre", num: n, index: idx });
      tgtItems.push({ phrase: item.highlights?.translation?.[0] || flag.translation_quote, cls: "mark-ochre", tone: "ochre", num: n, index: idx });
    }
  });
  return { srcItems, tgtItems };
}

function renderTranslationSheet(item) {
  const pair = item.output.pairs[0];
  const { srcItems, tgtItems } = buildTranslationAnnotations(item);
  const srcHtml = annotatePhrases(item.input.source_text, srcItems);
  const tgtHtml = annotatePhrases(item.input.translation_text, tgtItems);

  const quoteBar =
    item.input.source_quote || item.input.translation_quote
      ? `<div class="quote-bar">
          <span>Supplied source_quote: <b>"${esc(item.input.source_quote)}"</b></span>
          <span>Supplied translation_quote: <b>"${esc(item.input.translation_quote)}"</b></span>
        </div>`
      : "";

  const srcLegal = pair.source_legal_state ? ` · ${pair.source_legal_state}` : "";
  const tgtLegal = pair.translation_legal_state ? ` · ${pair.translation_legal_state}` : "";

  return `
    <div class="interlinear-stack">
      <div class="passage-block">
        <div class="passage-label">
          <span>Source (${esc(pair.source_language)})</span>
          <span>modality: ${esc(pair.source_modality)}${esc(srcLegal)}</span>
        </div>
        <p class="passage-serif">${srcHtml}</p>
      </div>
      <div class="passage-block">
        <div class="passage-label">
          <span>Translation (${esc(pair.target_language)})</span>
          <span>modality: ${esc(pair.translation_modality)}${esc(tgtLegal)}</span>
        </div>
        <p class="passage-serif">${tgtHtml}</p>
      </div>
    </div>
    ${quoteBar}
  `;
}

function renderDiffSheet(item) {
  const out = item.output;
  const beforeSha = out.before_sha256.slice(0, 12);
  const afterSha = out.after_sha256.slice(0, 12);

  const redlineSentence =
    `Investors may <span class="mark-del${state.focusedFlag === 2 ? " is-spotlight" : ""}">not</span> ` +
    `redeem shares <span class="mark-del${state.focusedFlag === 1 ? " is-spotlight" : ""}">before March 15, 2026</span> ` +
    `<span class="mark-add${state.focusedFlag === 1 ? " is-spotlight" : ""}">after April 1, 2026</span>. ` +
    `The minimum commitment is <span class="mark-del${state.focusedFlag === 0 ? " is-spotlight" : ""}">$250,000</span> ` +
    `<span class="mark-add${state.focusedFlag === 0 ? " is-spotlight" : ""}">$500,000</span>, and the fee waiver ` +
    `<span class="mark-del${state.focusedFlag === 3 ? " is-spotlight" : ""}">remains under review</span> ` +
    `<span class="mark-add${state.focusedFlag === 3 ? " is-spotlight" : ""}">is approved</span>.`;

  const beforeMarked = annotatePhrases(item.input.before_text, [
    { phrase: "not", cls: "mark-del", num: 3, index: 2 },
    { phrase: "March 15, 2026", cls: "mark-del", num: 2, index: 1 },
    { phrase: "$250,000", cls: "mark-del", num: 1, index: 0 },
    { phrase: "remains under review", cls: "mark-del", num: 4, index: 3 },
  ]);
  const afterMarked = annotatePhrases(item.input.after_text, [
    { phrase: "April 1, 2026", cls: "mark-add", tone: "clean", num: 2, index: 1 },
    { phrase: "$500,000", cls: "mark-add", tone: "clean", num: 1, index: 0 },
    { phrase: "approved", cls: "mark-add", tone: "clean", num: 4, index: 3 },
  ]);

  const body =
    state.diffMode === "redline"
      ? `<div class="passage-block">
          <div class="passage-label">
            <span>Combined Redline Markup</span>
            <span>crimson = removed · cobalt = added</span>
          </div>
          <p class="passage-serif">${redlineSentence}</p>
        </div>`
      : `<div class="interlinear-stack">
          <div class="passage-block">
            <div class="passage-label"><span>Version 1 (Before)</span><span>sha256: ${esc(beforeSha)}</span></div>
            <p class="passage-serif">${beforeMarked}</p>
          </div>
          <div class="passage-block">
            <div class="passage-label"><span>Version 2 (After)</span><span>sha256: ${esc(afterSha)}</span></div>
            <p class="passage-serif">${afterMarked}</p>
          </div>
        </div>`;

  return `
    <div class="diff-mode-row">
      <div class="mode-switch" role="group" aria-label="Revision view mode">
        <button class="mode-btn" type="button" data-diff-mode="redline" aria-pressed="${state.diffMode === "redline"}">Redline View</button>
        <button class="mode-btn" type="button" data-diff-mode="paired" aria-pressed="${state.diffMode === "paired"}">Side-by-Side</button>
      </div>
      <span class="sha-line">v1 ${esc(beforeSha)} -> v2 ${esc(afterSha)}</span>
    </div>
    ${body}
  `;
}

function renderLineageSheet(item) {
  const out = item.output;
  const wires = item.input.items
    .map(
      (w) => `<div class="wire-card">
        <div class="wire-card-head"><span>${esc(w.publisher)}</span><span>origin: ${esc(w.credited_origin)}</span></div>
        <p>${esc(w.excerpt)}</p>
      </div>`
    )
    .join("");

  const clusters = out.clusters
    .map((cl) => {
      const isShared = cl.member_ids.length > 1;
      return `<div class="cluster-box ${isShared ? "" : "solo"}">
        <div class="cluster-box-top">
          <span class="cluster-name">${esc(cl.canonical_origin)}</span>
          <span class="cluster-meta">${cl.member_ids.length} source(s) · basis: ${esc(cl.basis)}</span>
        </div>
        <div class="cluster-meta">
          languages: ${esc(cl.languages.join(", "))} · aliases seen: ${esc(cl.origins_seen.join(" / "))}
        </div>
      </div>`;
    })
    .join("");

  return `
    <div class="lineage-flow">
      <div class="wire-grid">${wires}</div>
      <div class="lineage-arrow">Collapsed ${out.source_count} inputs into ${out.independent_lineage_count} independent lineages</div>
      <div class="cluster-row">${clusters}</div>
    </div>
  `;
}

function renderRankingSheet(item) {
  const out = item.output;
  const rankedHtml = out.excerpts
    .map(
      (ex, idx) => `<div class="excerpt-row">
        <div class="excerpt-head">
          <span>#${idx + 1} · ${esc(ex.title)} (${esc(ex.publisher)})</span>
          <span class="excerpt-score">
            <span class="meter"><span class="meter-fill" style="width:${Math.round(ex.relevance * 100)}%"></span></span>
            <span>${ex.relevance.toFixed(2)} ${esc(ex.scoring_method)}</span>
          </span>
        </div>
        <p class="excerpt-quote">${esc(ex.excerpt)}</p>
        <div class="excerpt-foot">
          <span>chars ${ex.char_start}-${ex.char_end}</span>
          <span>${esc(ex.cluster_id)}</span>
          <span>ledger status: candidate</span>
        </div>
      </div>`
    )
    .join("");

  const dedupedDoc = item.input.documents[1];
  return `
    <div class="claim-banner">
      <span class="margin-eyebrow">Claim Under Review</span>
      <p>${esc(out.claim)}</p>
    </div>
    <div class="excerpt-stack">
      ${rankedHtml}
      <div class="excerpt-row deduped">
        <div class="excerpt-head">
          <span>Collapsed Duplicate · ${esc(dedupedDoc.title)} (${esc(dedupedDoc.publisher)})</span>
          <span class="excerpt-score">near-duplicate skipped</span>
        </div>
        <p class="excerpt-quote">${esc(dedupedDoc.text)}</p>
      </div>
    </div>
  `;
}

function renderMargin(item) {
  const stamp = document.getElementById("verdict-stamp");
  stamp.textContent = item.badge;
  stamp.className = `verdict-stamp ${item.tone === "alert" ? "alert" : ""}`;

  const notesEl = document.getElementById("margin-notes");
  if (item.tool === "check_translation") {
    const pair = item.output.pairs[0];
    if (pair.flags.length === 0) {
      notesEl.innerHTML = `<div class="note-card clean">
        <div class="note-head">
          <span class="note-cat">✓ SCALE MATCH VERIFIED</span>
          <span class="note-conf">0 flags</span>
        </div>
        <p class="note-body">Normalized both phrases to identical Decimal values without raising a false cross-script alarm.</p>
        <div class="note-kv">source_numbers: ${esc(JSON.stringify(pair.source_numbers))}<br>target_numbers: ${esc(JSON.stringify(pair.translation_numbers))}</div>
      </div>`;
      return;
    }

    notesEl.innerHTML =
      `<p class="margin-hint">Click a margin note to highlight the matching span on the sheet.</p>` +
      pair.flags
        .map((flag, idx) => {
          const isOchre = flag.category === "modality_shift";
          const pressed = state.focusedFlag === idx;
          return `<button class="note-card ${isOchre ? "ochre" : ""}" type="button" data-flag-idx="${idx}" aria-pressed="${pressed}">
            <div class="note-head">
              <span class="note-cat">[${idx + 1}] ${esc(flag.category.toUpperCase())}</span>
              <span class="note-conf">confidence: ${esc(flag.confidence)}</span>
            </div>
            <p class="note-body">${esc(flag.explanation)}</p>
            <div class="note-kv">src: ${esc(flag.source_quote ?? "null")}<br>tgt: ${esc(flag.translation_quote ?? "null")}</div>
          </button>`;
        })
        .join("");
    return;
  }

  if (item.tool === "diff_editions") {
    notesEl.innerHTML =
      `<p class="margin-hint">Click any change bucket to spotlight it in the markup.</p>` +
      item.output.changes
        .map((ch, idx) => {
          const pressed = state.focusedFlag === idx;
          return `<button class="note-card" type="button" data-flag-idx="${idx}" aria-pressed="${pressed}">
            <div class="note-head">
              <span class="note-cat">[${idx + 1}] ${esc(ch.category.toUpperCase())}</span>
              <span class="note-conf">${ch.removed.length + ch.added.length} token(s)</span>
            </div>
            <div class="note-kv" style="border-top:none;padding-top:0;margin-top:0;">
              − ${esc(ch.removed.join(", ") || "none")}<br>
              + ${esc(ch.added.join(", ") || "none")}
            </div>
          </button>`;
        })
        .join("");
    return;
  }

  if (item.tool === "cluster_origins") {
    const out = item.output;
    notesEl.innerHTML = `
      <div class="note-card clean">
        <div class="note-head"><span class="note-cat">SYNDICATION COLLAPSED</span><span class="note-conf">${out.syndication_collapsed} merged</span></div>
        <p class="note-body">Prevented 3 translations of the same WMO wire report from inflating source count from 1 to 3.</p>
      </div>
      <div class="note-card clean">
        <div class="note-head"><span class="note-cat">LEDGER EMISSION</span><span class="note-conf">${out.research_ledger_origins.length} records</span></div>
        <p class="note-body">Emits <code>resolved-shared</code> links pointing back to canonical origin <code>src-1</code>.</p>
      </div>
    `;
    return;
  }

  const out = item.output;
  notesEl.innerHTML = `
    <div class="note-card clean">
      <div class="note-head"><span class="note-cat">PROVENANCE PACKET</span><span class="note-conf">candidate-only</span></div>
      <p class="note-body">Processed ${out.documents_processed} documents, deduplicated identical mirror text, and capped per-publisher results.</p>
      <div class="note-kv">top score: ${out.excerpts[0].relevance.toFixed(2)} (${esc(out.excerpts[0].scoring_method)})<br>status: candidate (never pre-verified)</div>
    </div>
  `;
}

function renderActiveCase() {
  const item = activeCase();
  if (!item) return;

  document.getElementById("tool-badge").textContent = `btl · ${item.tool}`;
  document.getElementById("case-heading").textContent = item.title;
  document.getElementById("case-dek").textContent = item.summary;

  const sheet = document.getElementById("manuscript-sheet");
  if (item.tool === "check_translation") {
    sheet.innerHTML = renderTranslationSheet(item);
  } else if (item.tool === "diff_editions") {
    sheet.innerHTML = renderDiffSheet(item);
  } else if (item.tool === "cluster_origins") {
    sheet.innerHTML = renderLineageSheet(item);
  } else {
    sheet.innerHTML = renderRankingSheet(item);
  }

  renderMargin(item);
  document.getElementById("drawer-cmd-preview").textContent = item.command;
  document.getElementById("cli-command").textContent = item.command;
  document.getElementById("json-output").textContent = JSON.stringify(item.output, null, 2);
}

function selectCase(caseId) {
  state.activeId = caseId;
  state.focusedFlag = null;
  window.history.replaceState(null, "", `#case=${encodeURIComponent(caseId)}`);
  renderTabs();
  renderActiveCase();
}

function stepCase(delta) {
  const cases = state.data?.cases || [];
  const current = activeCase();
  if (!current) return;
  const idx = cases.findIndex((c) => c.id === current.id);
  const next = cases[idx + delta];
  if (next) selectCase(next.id);
}

function wireEvents() {
  document.getElementById("dossier-tabs").addEventListener("click", (event) => {
    const btn = event.target.closest(".dossier-tab");
    if (btn?.dataset.caseId) selectCase(btn.dataset.caseId);
  });

  document.getElementById("prev-btn").addEventListener("click", () => stepCase(-1));
  document.getElementById("next-btn").addEventListener("click", () => stepCase(1));

  document.getElementById("margin-notes").addEventListener("click", (event) => {
    const card = event.target.closest(".note-card[data-flag-idx]");
    if (!card) return;
    const idx = Number(card.dataset.flagIdx);
    state.focusedFlag = state.focusedFlag === idx ? null : idx;
    renderActiveCase();
  });

  document.getElementById("manuscript-sheet").addEventListener("click", (event) => {
    const modeBtn = event.target.closest(".mode-btn[data-diff-mode]");
    if (modeBtn) {
      state.diffMode = modeBtn.dataset.diffMode;
      renderActiveCase();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepCase(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      stepCase(1);
    }
  });
}

async function init() {
  const resp = await fetch("./data/cases.json");
  if (!resp.ok) {
    document.getElementById("case-heading").textContent = "Failed to load recorded cases.";
    return;
  }
  state.data = await resp.json();
  const match = window.location.hash.match(/case=([^&]+)/);
  if (match) state.activeId = decodeURIComponent(match[1]);
  renderHarnesses();
  renderTabs();
  renderActiveCase();
  wireEvents();
}

init();
