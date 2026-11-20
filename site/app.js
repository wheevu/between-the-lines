const TAB_LABELS = {
  "ko-vi-scale-clean": ["01", "Scale Equivalence"],
  "fund-allocation-drift": ["02", "Fund Drift"],
  "modality-unanchored-quote": ["03", "Hedged Quote"],
  "redemption-clause-diff": ["04", "Clause Diff"],
  "cross-script-wire-clustering": ["05", "Wire Lineage"],
  "deduped-passage-ranking": ["06", "Passage Rank"],
};

const state = {
  data: null,
  activeId: null,
  focused: null,
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

function annotate(text, items) {
  let html = esc(text);
  for (const item of items) {
    const safe = esc(item.phrase);
    if (!safe || !html.includes(safe)) continue;
    const spot = state.focused === item.index ? " is-spotlight" : "";
    const num = item.num ? `<span class="callout-num">[${item.num}]</span>` : "";
    html = html.replace(safe, `<span class="${item.cls}${spot}">${safe}${num}</span>`);
  }
  return html;
}

function renderTabs() {
  const cases = state.data?.cases || [];
  const current = activeCase();
  if (current) state.activeId = current.id;

  document.getElementById("tabs").innerHTML = cases
    .map((item, idx) => {
      const [num, label] = TAB_LABELS[item.id] || [String(idx + 1).padStart(2, "0"), item.title];
      const selected = current && item.id === current.id;
      return `<button class="tab-btn" type="button" role="tab" data-case-id="${esc(item.id)}" aria-selected="${selected}">
        <span class="tab-num">${esc(num)}</span>
        <span class="tab-dot ${esc(item.tone)}"></span>
        <span>${esc(label)}</span>
      </button>`;
    })
    .join("");
}

function buildTranslationMarks(item) {
  const pair = item.output.pairs[0];
  if (pair.flags.length === 0) {
    return {
      src: (item.highlights?.source || []).map((p) => ({ phrase: p, cls: "mark-clean" })),
      tgt: (item.highlights?.translation || []).map((p) => ({ phrase: p, cls: "mark-clean" })),
    };
  }
  const src = [];
  const tgt = [];
  pair.flags.forEach((flag, idx) => {
    const n = idx + 1;
    if (flag.category === "number") {
      src.push({ phrase: item.highlights?.source?.[1] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
      tgt.push({ phrase: item.highlights?.translation?.[0] || flag.translation_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "negation") {
      src.push({ phrase: item.highlights?.source?.[0] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "legal_state_shift") {
      src.push({ phrase: item.highlights?.source?.[2] || flag.source_quote, cls: "mark-alert", num: n, index: idx });
      tgt.push({ phrase: item.highlights?.translation?.[1] || flag.translation_quote, cls: "mark-alert", num: n, index: idx });
    } else if (flag.category === "modality_shift") {
      src.push({ phrase: item.highlights?.source?.[0] || flag.source_quote, cls: "mark-ochre", num: n, index: idx });
      tgt.push({ phrase: item.highlights?.translation?.[0] || flag.translation_quote, cls: "mark-ochre", num: n, index: idx });
    }
  });
  return { src, tgt };
}

function renderTranslation(item) {
  const pair = item.output.pairs[0];
  const marks = buildTranslationMarks(item);
  const quoteLine =
    item.input.source_quote || item.input.translation_quote
      ? `<div class="quote-line">Checked quotes: "${esc(item.input.source_quote)}" -> "${esc(item.input.translation_quote)}"</div>`
      : "";

  const srcMeta = `${pair.source_modality}${pair.source_legal_state ? ` · ${pair.source_legal_state}` : ""}`;
  const tgtMeta = `${pair.translation_modality}${pair.translation_legal_state ? ` · ${pair.translation_legal_state}` : ""}`;

  return `
    <div class="passage-block">
      <div class="passage-label"><span>Source (${esc(pair.source_language)})</span><span>${esc(srcMeta)}</span></div>
      <p class="passage-serif">${annotate(item.input.source_text, marks.src)}</p>
    </div>
    <div class="passage-block">
      <div class="passage-label"><span>Translation (${esc(pair.target_language)})</span><span>${esc(tgtMeta)}</span></div>
      <p class="passage-serif">${annotate(item.input.translation_text, marks.tgt)}</p>
    </div>
    ${quoteLine}
  `;
}

function renderDiff(item) {
  const out = item.output;
  const redline =
    `Investors may <span class="mark-del${state.focused === 2 ? " is-spotlight" : ""}">not</span> ` +
    `redeem shares <span class="mark-del${state.focused === 1 ? " is-spotlight" : ""}">before March 15, 2026</span> ` +
    `<span class="mark-add${state.focused === 1 ? " is-spotlight" : ""}">after April 1, 2026</span>. ` +
    `The minimum commitment is <span class="mark-del${state.focused === 0 ? " is-spotlight" : ""}">$250,000</span> ` +
    `<span class="mark-add${state.focused === 0 ? " is-spotlight" : ""}">$500,000</span>, and the fee waiver ` +
    `<span class="mark-del${state.focused === 3 ? " is-spotlight" : ""}">remains under review</span> ` +
    `<span class="mark-add${state.focused === 3 ? " is-spotlight" : ""}">is approved</span>.`;

  const beforeMarked = annotate(item.input.before_text, [
    { phrase: "not", cls: "mark-del", num: 3, index: 2 },
    { phrase: "March 15, 2026", cls: "mark-del", num: 2, index: 1 },
    { phrase: "$250,000", cls: "mark-del", num: 1, index: 0 },
    { phrase: "remains under review", cls: "mark-del", num: 4, index: 3 },
  ]);
  const afterMarked = annotate(item.input.after_text, [
    { phrase: "April 1, 2026", cls: "mark-add", num: 2, index: 1 },
    { phrase: "$500,000", cls: "mark-add", num: 1, index: 0 },
    { phrase: "approved", cls: "mark-add", num: 4, index: 3 },
  ]);

  const content =
    state.diffMode === "redline"
      ? `<div class="passage-block">
          <div class="passage-label"><span>Combined redline</span><span>removed · added</span></div>
          <p class="passage-serif">${redline}</p>
        </div>`
      : `<div class="passage-block">
          <div class="passage-label"><span>Version 1</span><span>${esc(out.before_sha256.slice(0, 10))}</span></div>
          <p class="passage-serif">${beforeMarked}</p>
        </div>
        <div class="passage-block">
          <div class="passage-label"><span>Version 2</span><span>${esc(out.after_sha256.slice(0, 10))}</span></div>
          <p class="passage-serif">${afterMarked}</p>
        </div>`;

  return `
    <div class="diff-bar">
      <div class="mode-switch">
        <button class="mode-btn" type="button" data-diff-mode="redline" aria-pressed="${state.diffMode === "redline"}">Redline</button>
        <button class="mode-btn" type="button" data-diff-mode="paired" aria-pressed="${state.diffMode === "paired"}">Side-by-Side</button>
      </div>
      <span class="sha-line">${esc(out.before_sha256.slice(0, 8))} -> ${esc(out.after_sha256.slice(0, 8))}</span>
    </div>
    ${content}
  `;
}

function renderLineage(item) {
  const out = item.output;
  const wires = item.input.items
    .map(
      (w) => `<div class="wire-item">
        <div class="item-head"><strong>${esc(w.publisher)}</strong><span>${esc(w.credited_origin)}</span></div>
        <p class="item-body">${esc(w.excerpt)}</p>
      </div>`
    )
    .join("");

  const clusters = out.clusters
    .map(
      (cl) => `<div class="cluster-item ${cl.member_ids.length > 1 ? "shared" : ""}">
        <div class="item-head">
          <strong>${esc(cl.canonical_origin)}</strong>
          <span>${cl.member_ids.length} source(s) · ${esc(cl.basis)}</span>
        </div>
        <div class="item-head" style="margin:0;">
          <span>${esc(cl.languages.join(", "))}</span>
          <span>${esc(cl.origins_seen.join(" / "))}</span>
        </div>
      </div>`
    )
    .join("");

  return `
    <div class="stack">
      <div class="wire-grid">${wires}</div>
      <div class="collapse-note">Collapsed ${out.source_count} inputs -> ${out.independent_lineage_count} independent lineages</div>
      ${clusters}
    </div>
  `;
}

function renderRanking(item) {
  const out = item.output;
  const ranked = out.excerpts
    .map(
      (ex, i) => `<div class="excerpt-item">
        <div class="item-head">
          <strong>#${i + 1} ${esc(ex.title)} (${esc(ex.publisher)})</strong>
          <span>${ex.relevance.toFixed(2)} ${esc(ex.scoring_method)} · chars ${ex.char_start}-${ex.char_end}</span>
        </div>
        <p class="item-body">${esc(ex.excerpt)}</p>
      </div>`
    )
    .join("");

  const mirror = item.input.documents[1];
  return `
    <div class="stack">
      <div class="passage-block" style="padding-top:0;">
        <div class="passage-label"><span>Claim</span><span>${out.documents_processed} docs -> ${out.excerpts.length} excerpts</span></div>
        <p class="passage-serif">${esc(out.claim)}</p>
      </div>
      ${ranked}
      <div class="excerpt-item deduped">
        <div class="item-head"><strong>${esc(mirror.title)} (${esc(mirror.publisher)})</strong><span>duplicate skipped</span></div>
        <p class="item-body">${esc(mirror.text)}</p>
      </div>
    </div>
  `;
}

function renderMargin(item) {
  const verdict = document.getElementById("verdict");
  verdict.textContent = `${item.badge} · ${item.tool}`;
  verdict.className = `verdict ${item.tone === "alert" ? "alert" : ""}`;

  const notesEl = document.getElementById("notes");
  if (item.tool === "check_translation") {
    const pair = item.output.pairs[0];
    if (pair.flags.length === 0) {
      notesEl.innerHTML = `<div class="note clean">
        <div class="note-title"><span>SCALE MATCH</span><span class="note-conf">0 flags</span></div>
        <p>Both phrases normalize to ${esc(JSON.stringify(pair.source_numbers))}.</p>
      </div>`;
      return;
    }
    notesEl.innerHTML = pair.flags
      .map((f, idx) => {
        const cls = f.category === "modality_shift" ? "ochre" : "";
        return `<button class="note ${cls}" type="button" data-flag-idx="${idx}" aria-pressed="${state.focused === idx}">
          <div class="note-title"><span>[${idx + 1}] ${esc(f.category.toUpperCase())}</span><span class="note-conf">${esc(f.confidence)}</span></div>
          <p>${esc(f.explanation)}</p>
          <div class="note-meta">${esc(f.source_quote ?? "null")} -> ${esc(f.translation_quote ?? "null")}</div>
        </button>`;
      })
      .join("");
    return;
  }

  if (item.tool === "diff_editions") {
    notesEl.innerHTML = item.output.changes
      .map(
        (ch, idx) => `<button class="note" type="button" data-flag-idx="${idx}" aria-pressed="${state.focused === idx}">
          <div class="note-title"><span>[${idx + 1}] ${esc(ch.category.toUpperCase())}</span></div>
          <div class="note-meta" style="margin-top:0;">− ${esc(ch.removed.join(", ") || "none")}<br>+ ${esc(ch.added.join(", ") || "none")}</div>
        </button>`
      )
      .join("");
    return;
  }

  if (item.tool === "cluster_origins") {
    const out = item.output;
    notesEl.innerHTML = `<div class="note clean">
      <div class="note-title"><span>SYNDICATION COLLAPSED</span><span class="note-conf">${out.syndication_collapsed} merged</span></div>
      <p>3 cross-language wire articles resolved to 1 canonical WMO origin, leaving 2 independent lineages.</p>
    </div>`;
    return;
  }

  const out = item.output;
  notesEl.innerHTML = `<div class="note clean">
    <div class="note-title"><span>CANDIDATE PACKET</span><span class="note-conf">unverified</span></div>
    <p>Deduplicated identical text and emitted ${out.excerpts.length} offset-grounded excerpts (top score ${out.excerpts[0].relevance.toFixed(2)}).</p>
  </div>`;
}

function renderActive() {
  const item = activeCase();
  if (!item) return;

  document.getElementById("case-heading").textContent = item.title;
  const el = document.getElementById("manuscript");
  if (item.tool === "check_translation") el.innerHTML = renderTranslation(item);
  else if (item.tool === "diff_editions") el.innerHTML = renderDiff(item);
  else if (item.tool === "cluster_origins") el.innerHTML = renderLineage(item);
  else el.innerHTML = renderRanking(item);

  renderMargin(item);
  document.getElementById("cli-command").textContent = `$ ${item.command}`;
  document.getElementById("json-output").textContent = JSON.stringify(item.output, null, 2);
}

function selectCase(id) {
  state.activeId = id;
  state.focused = null;
  window.history.replaceState(null, "", `#case=${encodeURIComponent(id)}`);
  renderTabs();
  renderActive();
}

function step(delta) {
  const cases = state.data?.cases || [];
  const current = activeCase();
  if (!current) return;
  const idx = cases.findIndex((c) => c.id === current.id);
  if (cases[idx + delta]) selectCase(cases[idx + delta].id);
}

function wireEvents() {
  document.getElementById("tabs").addEventListener("click", (e) => {
    const btn = e.target.closest(".tab-btn");
    if (btn?.dataset.caseId) selectCase(btn.dataset.caseId);
  });

  document.getElementById("notes").addEventListener("click", (e) => {
    const note = e.target.closest(".note[data-flag-idx]");
    if (!note) return;
    const idx = Number(note.dataset.flagIdx);
    state.focused = state.focused === idx ? null : idx;
    renderActive();
  });

  document.getElementById("manuscript").addEventListener("click", (e) => {
    const btn = e.target.closest(".mode-btn[data-diff-mode]");
    if (btn) {
      state.diffMode = btn.dataset.diffMode;
      renderActive();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      step(-1);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      step(1);
    }
  });
}

async function init() {
  const resp = await fetch("./data/cases.json");
  if (!resp.ok) {
    document.getElementById("case-heading").textContent = "Failed to load cases.";
    return;
  }
  state.data = await resp.json();
  const match = window.location.hash.match(/case=([^&]+)/);
  if (match) state.activeId = decodeURIComponent(match[1]);
  renderTabs();
  renderActive();
  wireEvents();
}

init();
