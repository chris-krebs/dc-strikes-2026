/* Static site script: everything is read from /data at load time. No build step. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const getJSON = (u) => fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
  const getText = (u) => fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.text(); });
  const REDUCE = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const C = { // keep in sync with site.css / plot_ioda.py
    bg: "#0a0a0a", grid: "#262626", axis: "#3a3a3a", text: "#ededed", text2: "#9e9e9e", band: "#1e1e1e",
    yandex: "#86823f", vk: "#863f43", sber: "#4f7f6a", strike: "#863f43", strikeHi: "#c2575e", dcs: "#8d5a99", telecom: "#86823f",
  };

  // RFC 4180 CSV -> array of objects
  function parseCSV(text) {
    const rows = []; let row = [], f = "", q = false;
    text = text.replace(/^﻿/, "");
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
      else if (c === '"') q = true;
      else if (c === ",") { row.push(f); f = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); rows.push(row); row = []; f = ""; }
      else f += c;
    }
    if (f || row.length) { row.push(f); rows.push(row); }
    const head = rows.shift();
    return rows.filter((r) => r.some((x) => x !== "")).map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
  }

  // "url | url | text" -> links; plain text kept as text
  function sourceLinks(str) {
    const parts = Array.isArray(str) ? str : String(str || "").split("|");
    return parts.map((p) => p.trim()).filter(Boolean).map((p) => {
      if (/^https?:\/\//.test(p)) {
        let host = p; try { const u = new URL(p); host = u.hostname.replace(/^www\./, ""); if (host === "x.com") host = "x.com/" + u.pathname.split("/")[1]; } catch (e) {}
        return `<a href="${esc(p)}" rel="noopener" target="_blank">${esc(host)}</a>`;
      }
      return `<span>${esc(p)}</span>`;
    }).join(" ");
  }
  const gradeChip = (g) => g ? `<span class="grade g-${esc(g)}" title="Evidence grade ${esc(g)}">${esc(g)}</span>` : "";
  const fmtDate = (iso) => new Date(iso + (iso.length === 10 ? "T12:00:00Z" : "")).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  const utcStr = (t) => new Date(t).toISOString().slice(0, 16).replace("T", " ");

  // GitHub links derived from the Pages URL (user.github.io/repo)
  (function ghLinks() {
    const m = location.hostname.match(/^([^.]+)\.github\.io$/);
    const user = m && m[1], repo = location.pathname.split("/").filter(Boolean)[0];
    if (!user) return;
    document.querySelectorAll("[data-gh]").forEach((a) => { a.href = a.dataset.gh === "user" ? `https://github.com/${user}` : `https://github.com/${user}/${repo || ""}`; });
  })();

  // ================================================================ map (MapLibre)
  let map, strikeMarkers = {};
  const layerState = { struck: true, dcs: true, telecom: false };
  const GROUPS = {
    struck: ["struck-fill", "struck-line"],
    dcs: ["dcs-bld-fill", "dcs-bld-line", "dcs-bld-pt", "dcs-pdb"],
    telecom: ["telecom-pt"],
  };
  const raster = (tiles, attribution, maxzoom) => ({
    version: 8,
    sources: { base: { type: "raster", tiles, tileSize: 256, maxzoom, attribution } },
    layers: [{ id: "bg", type: "background", paint: { "background-color": C.bg } }, { id: "base", type: "raster", source: "base" }],
  });
  const BASES = {
    osm: async () => raster(["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', 19),
    satellite: async () => raster(["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      'Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community', 19),
    versatiles: async () => {
      const s = await getJSON("data/basemap/versatiles-protostar-dark.json");
      delete s.terrain; // keep the 2D map; overlays sit flat on the surface
      return s;
    },
  };
  let layerData;

  function addOverlays() {
    const d = layerData;
    const src = (id, data) => { if (!map.getSource(id)) map.addSource(id, { type: "geojson", data }); };
    src("struck", d.outlines); src("dc-bld", d.buildings); src("dc-bld-pt", d.centroids); src("dc-pdb", d.peeringdb); src("telecom", d.telecom);
    const add = (l) => { if (!map.getLayer(l.id)) map.addLayer(l); };
    add({ id: "telecom-pt", type: "circle", source: "telecom", paint: { "circle-radius": 5, "circle-color": C.telecom, "circle-opacity": .75 } });
    add({ id: "dcs-bld-fill", type: "fill", source: "dc-bld", minzoom: 11, paint: { "fill-color": C.dcs, "fill-opacity": .55 } });
    add({ id: "dcs-bld-line", type: "line", source: "dc-bld", minzoom: 11, paint: { "line-color": "#232323", "line-width": 1 } });
    add({ id: "dcs-bld-pt", type: "circle", source: "dc-bld-pt", maxzoom: 11, paint: { "circle-radius": 4, "circle-color": C.dcs, "circle-stroke-color": "#232323", "circle-stroke-width": .5 } });
    add({ id: "dcs-pdb", type: "circle", source: "dc-pdb", paint: { "circle-radius": 4, "circle-color": C.dcs, "circle-stroke-color": "#232323", "circle-stroke-width": .5 } });
    add({ id: "struck-fill", type: "fill", source: "struck", paint: { "fill-color": C.strike, "fill-opacity": .6 } });
    add({ id: "struck-line", type: "line", source: "struck", paint: { "line-color": "rgba(255,255,255,0.6)", "line-width": 1 } });
    applyVisibility();
  }
  function applyVisibility() {
    Object.entries(GROUPS).forEach(([g, ids]) => ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", layerState[g] ? "visible" : "none")));
    Object.values(strikeMarkers).forEach((m) => { m.getElement().style.display = layerState.struck ? "" : "none"; });
  }
  async function setBase(key) {
    const style = await BASES[key]();
    map.setStyle(style, { diff: false }); // overlays are re-added on "style.load" (see buildMap)
  }

  function popupHTML(p, kind) {
    if (kind === "struck") return `<h4>${esc(p.name)}</h4><span class="muted">Struck site, building outline</span>`;
    const name = p.name || "Unnamed data center";
    const extra = [p.operator, p.city].filter(Boolean).map(esc).join("<br>");
    const aka = (() => { try { const a = typeof p.aka === "string" ? JSON.parse(p.aka) : p.aka; return a && a.length ? `<br><span class="muted">Also: ${esc(a.join("; "))}</span>` : ""; } catch (e) { return ""; } })();
    return `<h4>${esc(name)}</h4>${extra}${aka}<br><span class="muted">${kind === "telecom" ? "Data center" : "Telecom infrastructure"}, ${esc(p.source)}</span>` +
      (p.website ? `<br><a href="${esc(p.website)}" target="_blank" rel="noopener">${esc(p.website.replace(/^https?:\/\//, ""))}</a>` : "");
  }

  async function buildMap(strikes, data) {
    layerData = data;
    $("[data-count=struck]").textContent = strikes.features.length;
    $("[data-count=dcs]").textContent = data.buildings.features.length + data.peeringdb.features.length;
    $("[data-count=telecom]").textContent = data.telecom.features.length;
    const base = $("input[name=base]:checked").value;
    map = new maplibregl.Map({
      container: "map", style: await BASES[base](), cooperativeGestures: true,
      center: [44, 56], zoom: 3.4, attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.on("style.load", () => { map.setProjection({ type: "globe" }); addOverlays(); });

    strikes.features.forEach((f) => {
      const p = f.properties, el = document.createElement("button");
      el.type = "button"; el.className = "strike-pin"; el.textContent = p.n; el.setAttribute("aria-label", `${p.n}. ${p.label}, ${p.operator}`);
      const pop = new maplibregl.Popup({ offset: 18 }).setHTML(`<h4>${p.n}. ${esc(p.label)} (${esc(p.operator)})</h4>${fmtDate(p.date)} 2026, ${esc(p.time_reported)}<br><a href="#strike-${p.id}">Details below</a>`);
      strikeMarkers[p.id] = new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).setPopup(pop).addTo(map);
    });

    const clickable = { "struck-fill": "struck", "dcs-bld-fill": "dcs", "dcs-bld-pt": "dcs", "dcs-pdb": "dcs", "telecom-pt": "telecom" };
    Object.entries(clickable).forEach(([id, kind]) => {
      map.on("click", id, (e) => new maplibregl.Popup({ offset: 6 }).setLngLat(e.lngLat).setHTML(popupHTML(e.features[0].properties, kind)).addTo(map));
      map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
    });

    const b = new maplibregl.LngLatBounds();
    strikes.features.forEach((f) => b.extend(f.geometry.coordinates));
    map.fitBounds(b, { padding: { top: 60, bottom: 60, left: window.innerWidth > 760 ? 260 : 40, right: 60 }, animate: false });

    $("#map-panel").addEventListener("change", (e) => {
      if (e.target.name === "base") setBase(e.target.value);
      if (e.target.name === "layer") { layerState[e.target.value] = e.target.checked; applyVisibility(); }
    });
  }
  function locate(id) {
    const m = strikeMarkers[id]; if (!m || !map) return;
    document.querySelectorAll(".timeline button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === id)));
    if (!layerState.struck) { layerState.struck = true; $("input[value=struck]").checked = true; applyVisibility(); }
    map[REDUCE ? "jumpTo" : "flyTo"]({ center: m.getLngLat(), zoom: 14.5, ...(REDUCE ? {} : { duration: 2200 }) });
    if (!m.getPopup().isOpen()) m.togglePopup();
  }

  // ================================================================ timeline
  function buildTimeline(strikes) {
    const ol = $("#timeline"), first = 7; // axis runs 7..18 Oct
    ol.innerHTML = strikes.features.map((f) => {
      const p = f.properties, day = +p.date.slice(8, 10), pos = (day - first) / 11 * 100, end = pos > 85;
      return `<li${end ? ' class="end"' : ` style="left:${pos.toFixed(2)}%"`}><button type="button" data-id="${p.id}" aria-pressed="false">
        <span class="t-n">${p.n}. ${fmtDate(p.date)}</span><span class="t-site">${esc(p.label)}</span><span class="t-op">${esc(p.operator)}</span></button></li>`;
    }).join("");
    ol.insertAdjacentHTML("afterend", `<div class="timeline-axis" aria-hidden="true"><span>7 Oct</span><span>18 Oct</span></div>`);
    ol.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) locate(b.dataset.id); });
  }

  // ================================================================ strike entries + imagery
  const RESULT_TEXT = { detection: "Thermal detection", consistent: "Change consistent with reports", none: "No detection", inconclusive: "Inconclusive", reference: "Before (reference)" };
  function buildStrikes(strikes, imagery) {
    const facts = (pairs) => pairs.filter(([, v]) => v && v !== "n/a" && v !== "unknown").map(([k, v, cls]) =>
      `<dt>${k}</dt><dd${cls ? ` class="${cls}"` : ""}>${esc(v)}</dd>`).join("");
    $("#strike-list").innerHTML = strikes.features.map((f) => {
      const p = f.properties, imgs = imagery[p.id] || [];
      const utc = p.time_utc ? `${p.time_utc.slice(11, 16)} UTC` : "";
      const links = [p.firms_link ? `<a href="${esc(p.firms_link)}" target="_blank" rel="noopener">FIRMS map</a>` : "",
        (p.x_posts || []).length ? `Posts on X: ${sourceLinks(p.x_posts)}` : "Posts on X: none found"].filter(Boolean).join(" ");
      return `<article class="strike" id="strike-${p.id}">
        <div class="strike-head">
          <span class="num" aria-hidden="true">${p.n}</span>
          <h3>${esc(p.label)}</h3>
          <p>${esc(p.operator)}, ${esc(p.site)}</p>
          <p class="when">${fmtDate(p.date)} 2026, ${esc(p.time_reported)}${utc ? `<br>${utc}` : ""}</p>
          <button type="button" class="locate" data-id="${p.id}">Show on map</button>
        </div>
        <div>
          <dl class="facts">${facts([
            ["Operator said", p.operator_statement, "quote"],
            ["Physical damage", p.physical_damage],
            ["Service effects", p.service_effects],
            ["Casualties", p.casualties],
            ["Capacity", p.power],
            ["Cloud zone", p.cloud_zone],
            ["Facility", p.location],
            ["Built", p.commissioned],
            ["On site", p.facility_notes],
            ["Conflicting figures", p.conflicts],
            ["Note", p.notes],
          ])}</dl>
          <p class="sources">Sources: ${sourceLinks(p.sources)}${p.primary_evidence ? ` <span>Primary evidence:</span> ${sourceLinks(p.primary_evidence)}` : ""}</p>
        </div>
        ${imgs.length ? `<div class="imagery">${imgs.map((im, i) => `<figure>
            <button type="button" data-site="${p.id}" data-i="${i}" aria-label="Enlarge: ${esc(im.title)}"><img src="${im.src}" width="${im.w}" height="${im.h}" loading="lazy" alt="${esc(im.title + ". " + im.caption)}"></button>
            <figcaption><b>${esc(im.title)}</b><span class="result ${im.result}">${RESULT_TEXT[im.result] || ""}</span><br>${esc(im.caption)}</figcaption>
          </figure>`).join("")}</div>` : ""}
        <p class="img-links">${links}</p>
      </article>`;
    }).join("");
    $("#strike-list").addEventListener("click", (e) => {
      const loc = e.target.closest("button.locate");
      if (loc) { $("#map").scrollIntoView({ behavior: REDUCE ? "auto" : "smooth", block: "center" }); locate(loc.dataset.id); return; }
      const b = e.target.closest(".imagery button");
      if (b) openLightbox(imagery[b.dataset.site][+b.dataset.i]);
    });
  }
  function openLightbox(im) {
    let d = $("dialog.lightbox");
    if (!d) {
      d = document.createElement("dialog"); d.className = "lightbox";
      d.innerHTML = `<button type="button">Close</button><img alt=""><p></p>`;
      d.querySelector("button").onclick = () => d.close();
      d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
      document.body.append(d);
    }
    d.querySelector("img").src = im.src; d.querySelector("img").alt = im.title;
    d.querySelector("p").textContent = `${im.title}. ${im.caption} Credit: ${im.credit}.`;
    d.showModal();
  }

  // ================================================================ IODA chart, styled after plot_ioda.py
  function buildIODA(data) {
    const el = $("#ioda-chart"), NS = "http://www.w3.org/2000/svg";
    const colour = { "Yandex Cloud": C.yandex, VKontakte: C.vk };
    const series = data.series.map((s) => ({ ...s, color: colour[s.label] || C.text,
      pts: s.points.map(([t, pct, n]) => ({ t: Date.parse(t), pct, n })) }));
    const valid = (s) => s.pts.filter((p) => p.pct !== null);
    const t0 = Math.min(...series.map((s) => s.pts[0].t)), t1 = Math.max(...series.map((s) => valid(s).at(-1).t));
    const bands = data.strike_windows.map((b) => ({ ...b, a: Date.parse(b.from), z: Date.parse(b.to) }));
    $("#chart-legend").innerHTML = series.map((s) => `<span style="--c:${s.color}">${esc(s.name)} (baseline ${Math.round(s.baseline)} /24s)</span>`).join("");
    $("#ioda-pulled").textContent = utcStr(Date.parse(data.pulled_utc)) + " UTC";
    $("#ioda-summary").textContent = `At the last reading (${utcStr(t1)} UTC), ` + series.map((s) => `${s.label} was at ${Math.round(valid(s).at(-1).pct)}% of its baseline`).join(" and ") + ".";

    const tip = document.createElement("div"); tip.className = "tip"; el.append(tip);
    function draw() {
      el.querySelector("svg")?.remove();
      const W = el.clientWidth, H = el.clientHeight, narrow = W < 600;
      const m = { t: 34, r: narrow ? 46 : 118, b: 26, l: narrow ? 40 : 58 };
      const x = (t) => m.l + (t - t0) / (t1 - t0) * (W - m.l - m.r);
      const y = (v) => m.t + (1 - v / 122) * (H - m.t - m.b);
      const svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      let h = "";
      bands.forEach((b) => {
        h += `<rect class="band" x="${x(b.a)}" y="${y(122)}" width="${Math.max(2, x(b.z) - x(b.a))}" height="${y(0) - y(122)}"/>`;
        if (!narrow) h += `<text class="band-label" x="${x(b.a) + 2}" y="${y(121) + 9}"><tspan>${esc(b.label)}</tspan><tspan x="${x(b.a) + 2}" dy="12">(${esc(b.op)})</tspan></text>`;
      });
      h += `<g class="grid">${[0, 20, 40, 60, 80, 100].map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`).join("")}</g>`;
      h += `<g class="axis">${[0, 20, 40, 60, 80, 100].map((v) => `<text x="${m.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join("")}`;
      h += `<line class="base" x1="${m.l}" x2="${m.l}" y1="${y(0)}" y2="${y(122)}"/><line class="base" x1="${m.l}" x2="${W - m.r}" y1="${y(0)}" y2="${y(0)}"/>`;
      for (let d = 6; d <= 19; d += narrow ? 2 : 1) {
        const t = Date.UTC(2026, 9, d); if (t > t1) break;
        h += `<text x="${x(t)}" y="${H - 6}" text-anchor="middle">${String(d).padStart(2, "0")} Oct</text>`;
      }
      if (!narrow) h += `<text class="y-title" transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">Responsive /24 blocks, % of 6–7 Oct median</text>`;
      h += `</g>`;
      series.forEach((s) => {
        let d = "", pen = false;
        s.pts.forEach((p) => { if (p.pct === null) { pen = false; return; } d += (pen ? "L" : "M") + x(p.t).toFixed(1) + "," + y(p.pct).toFixed(1); pen = true; });
        h += `<path class="line" stroke="${s.color}" d="${d}"/>`;
      });
      const ends = series.map((s) => ({ s, last: valid(s).at(-1) })).map((o) => ({ ...o, yy: y(o.last.pct) })).sort((a, b) => a.yy - b.yy);
      for (let i = 1; i < ends.length; i++) if (ends[i].yy - ends[i - 1].yy < 14) ends[i].yy = ends[i - 1].yy + 14;
      ends.forEach(({ s, last, yy }) => { h += `<text class="end-label" x="${x(last.t) + 6}" y="${yy + 4}">${narrow ? "" : esc(s.label) + " "}${Math.round(last.pct)}%</text>`; });
      h += `<line class="cross" y1="${y(122)}" y2="${y(0)}" x1="-10" x2="-10"/>`;
      series.forEach((s) => { h += `<circle class="dot" r="4" cx="-10" cy="-10" fill="${s.color}"/>`; });
      h += `<rect x="${m.l}" y="0" width="${W - m.l - m.r}" height="${H}" fill="transparent" class="hit"/>`;
      svg.innerHTML = h; el.prepend(svg);

      const cross = svg.querySelector(".cross"), dots = svg.querySelectorAll(".dot"), hit = svg.querySelector(".hit");
      const nearest = (s, t) => { let best = null; for (const p of s.pts) if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p; return best; };
      const move = (clientX) => {
        const r = svg.getBoundingClientRect(), t = t0 + (clientX - r.left - m.l) / (W - m.l - m.r) * (t1 - t0);
        const ps = series.map((s) => nearest(s, t)), xx = x(ps[0].t);
        cross.setAttribute("x1", xx); cross.setAttribute("x2", xx);
        dots.forEach((d, i) => { const ok = ps[i].pct !== null; d.setAttribute("cx", ok ? x(ps[i].t) : -10); d.setAttribute("cy", ok ? y(ps[i].pct) : -10); });
        const band = bands.find((b) => ps[0].t >= b.a && ps[0].t <= b.z);
        tip.innerHTML = `<b>${utcStr(ps[0].t)} UTC</b>${band ? `, ${esc(band.label)} strike window` : ""}<br>` +
          series.map((s, i) => `<span class="sw-line" style="background:${s.color}"></span>${esc(s.label)}: ` + (ps[i].pct === null ? "no data" : `<b>${ps[i].pct}%</b> (${Math.round(ps[i].n)} /24s)`)).join("<br>");
        tip.style.display = "block";
        tip.style.left = Math.min(Math.max(0, xx + 12), W - tip.offsetWidth) + "px"; tip.style.top = (m.t + 30) + "px";
      };
      hit.addEventListener("pointermove", (e) => move(e.clientX));
      hit.addEventListener("pointerleave", () => { tip.style.display = "none"; cross.setAttribute("x1", -10); cross.setAttribute("x2", -10); dots.forEach((d) => d.setAttribute("cx", -10)); });
    }
    draw();
    let rt; new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(draw, 120); }).observe(el);

    const byT = new Map();
    series.forEach((s, i) => s.pts.forEach((p) => { if (p.t % 3600e3 === 0) { const r = byT.get(p.t) || []; r[i] = p; byT.set(p.t, r); } }));
    $("#ioda-table").innerHTML = `<div class="table-scroll"><table class="data"><thead><tr><th>UTC</th>${series.map((s) => `<th>${esc(s.label)} % of baseline</th><th>/24s</th>`).join("")}</tr></thead><tbody>` +
      [...byT.entries()].sort((a, b) => a[0] - b[0]).map(([t, r]) => `<tr><td class="id">${utcStr(t)}</td>${series.map((s, i) => r[i] && r[i].pct !== null ? `<td>${r[i].pct}</td><td>${Math.round(r[i].n)}</td>` : "<td>no data</td><td></td>").join("")}</tr>`).join("") +
      `</tbody></table></div>`;
  }

  // ================================================================ Cloudflare Radar embeds (tabs, loaded on first view)
  function buildRadar(cfg) {
    const tabs = $("#radar-tabs"), panels = $("#radar-panels");
    tabs.innerHTML = cfg.groups.map((g, i) => `<button type="button" role="tab" id="tab-${g.id}" aria-controls="panel-${g.id}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">${esc(g.label)}</button>`).join("");
    panels.innerHTML = cfg.groups.map((g, i) => `<div class="radar-panel" role="tabpanel" id="panel-${g.id}" aria-labelledby="tab-${g.id}"${i ? " hidden" : ""}><p>${esc(g.note)}</p><div class="radar-grid"></div></div>`).join("");
    const fill = (g) => {
      const grid = $(`#panel-${g.id} .radar-grid`); if (grid.children.length) return;
      grid.innerHTML = g.embeds.map((e) => `<figure><iframe class="cf-radar-embed" src="${esc(e.src)}" height="${e.height}" title="Cloudflare Radar - ${esc(e.title)}" loading="lazy" scrolling="no"></iframe>
        <figcaption>Cloudflare, Inc. “${esc(e.title)}.” Cloudflare Radar, 2026, <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url.replace(/^https:\/\//, ""))}</a>. Accessed ${esc(cfg.accessed)}.</figcaption></figure>`).join("");
    };
    const select = (btn) => {
      tabs.querySelectorAll("button").forEach((b) => { const on = b === btn; b.setAttribute("aria-selected", on); b.tabIndex = on ? 0 : -1; $("#" + b.getAttribute("aria-controls")).hidden = !on; });
      fill(cfg.groups.find((g) => "tab-" + g.id === btn.id));
    };
    tabs.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) select(b); });
    tabs.addEventListener("keydown", (e) => {
      const bs = [...tabs.querySelectorAll("button")], i = bs.indexOf(document.activeElement);
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = bs[(i + (e.key === "ArrowRight" ? 1 : -1) + bs.length) % bs.length]; n.focus(); select(n); }
    });
    // load the first tab once the section comes near the viewport
    new IntersectionObserver((es, o) => { if (es[0].isIntersecting) { fill(cfg.groups[0]); o.disconnect(); } }, { rootMargin: "400px" }).observe($("#traffic"));
  }

  // ================================================================ media coverage (svEye)
  function buildMedia(media, strikes) {
    $("#media-source").textContent = media.source.replace("Semantic Visions svEye export, ", "export of ");
    const colour = { Yandex: C.yandex, Sberbank: C.sber, VK: C.vk };
    const days = media.days, n = days.length;
    const strikeDays = strikes.features.map((f) => days.indexOf(f.properties.date)).filter((i) => i >= 0);
    $("#media-chart").innerHTML = media.companies.map((c) => {
      const max = Math.max(...c.all, 1), W = 1000, H = 64, bw = W / n;
      const bars = c.all.map((v, i) => { const h = v / max * (H - 14); return `<rect x="${(i * bw + 1).toFixed(1)}" y="${(H - h).toFixed(1)}" width="${(bw - 2).toFixed(1)}" height="${h.toFixed(1)}" fill="${colour[c.name]}" rx="1"><title>${fmtDate(days[i])}: ${v} articles</title></rect>`; }).join("");
      const ticks = strikeDays.map((i) => `<line x1="${(i * bw + bw / 2).toFixed(1)}" x2="${(i * bw + bw / 2).toFixed(1)}" y1="${H + 1}" y2="${H + 6}" stroke="${C.strikeHi}" stroke-width="3"/>`).join("");
      const peak = c.all.indexOf(max);
      return `<div class="media-row"><span class="m-name">${esc(c.name)}</span><svg viewBox="0 0 ${W} ${H + 8}" preserveAspectRatio="none" role="img" aria-label="${esc(c.name)}: articles per day, peak ${max} on ${fmtDate(days[peak])}">${bars}${ticks}</svg><span class="m-total">${c.all.reduce((a, b) => a + b, 0)}<br><span class="muted">peak ${max}</span></span></div>`;
    }).join("") + `<div class="media-axis"><span></span><div><span>${fmtDate(days[0])}</span><span>${fmtDate(days.at(-1))}</span></div><span style="text-align:right">total</span></div>`;

    const RELEVANT = /drone|attack|strike|target|data cent|outage|disrupt|traffic|emergency|restor|force majeure|migrat|supercomputer|hardware|phishing|waive|compensation|backup|doomsday|connectivity|failure/i;
    const rows = media.stories.filter((s) => RELEVANT.test(s.title)).slice(0, 14);
    $("#t-stories").innerHTML = `<thead><tr><th>Started (UTC)</th><th>Entity</th><th>Story (machine-generated summary)</th><th>Articles</th><th>Sentiment</th></tr></thead><tbody>` +
      rows.map((s) => `<tr><td class="id">${utcStr(Date.parse(s.start))}</td><td>${esc(s.entity)}</td><td class="wide"><details><summary>${esc(s.title)}</summary><p class="muted">${esc(s.text)}</p></details></td><td>${s.documents}</td><td class="sentiment">${esc(s.sentiment)}</td></tr>`).join("") + `</tbody>`;
  }

  // ================================================================ tables
  const EVENT_LABEL = (k) => k.replace("Leningrad obl.", "Novosergievka (Leningrad obl.)");
  function buildDisruptions(rows) {
    const T = $("#t-disruptions"), fe = $("#f-event"), fg = $("#f-grade"), fp = $("#f-party");
    const uniq = (k) => [...new Set(rows.map((r) => r[k]).filter(Boolean))];
    uniq("strike_event").forEach((v) => fe.add(new Option(EVENT_LABEL(v), v)));
    uniq("evidence_grade").sort().forEach((v) => fg.add(new Option(v, v)));
    uniq("affected_party").sort().forEach((v) => fp.add(new Option(v, v)));
    $("#grade-key").innerHTML = ["A", "B", "C", "D"].map((g) => `<span>${gradeChip(g)} ${{ A: "operator or status page", B: "third-party measurement", C: "complaint spike", D: "unsourced media claim" }[g]}</span>`).join("") + ` <a href="#method">How grades work</a>`;
    const head = `<thead><tr><th>ID</th><th>Service</th><th>Affected</th><th>Reported disruption</th><th>When (MSK)</th><th>Last known status</th><th>Grade</th><th>Basis</th><th>Caveat</th><th>Sources</th></tr></thead>`;
    function render() {
      const sel = rows.filter((r) => (!fe.value || r.strike_event === fe.value) && (!fg.value || r.evidence_grade === fg.value) && (!fp.value || r.affected_party === fp.value));
      let body = "", cur = null;
      sel.forEach((r) => {
        if (r.strike_event !== cur) { cur = r.strike_event; body += `<tr class="group"><td colspan="10">${esc(EVENT_LABEL(cur))}</td></tr>`; }
        body += `<tr><td class="id">${esc(r.row_id)}</td><td class="mid">${esc(r.service)}<br><span class="muted">${esc(r.owner_operator)}</span></td><td>${esc(r.affected_party)}</td>
          <td class="wide">${esc(r.disruption)}</td><td>${esc(r.time_msk)}</td><td class="mid">${esc(r.last_known_status)}${r.status_date ? `<br><span class="muted">as of ${fmtDate(r.status_date)}</span>` : ""}</td>
          <td>${gradeChip(r.evidence_grade)}</td><td class="mid">${esc(r.evidence_basis)}<br><span class="muted">${esc(r.source_chain)}</span></td><td class="caveat">${esc(r.caveat)}</td><td>${sourceLinks(r.sources)}</td></tr>`;
      });
      T.innerHTML = head + `<tbody>${body || `<tr><td colspan="10">No rows match these filters. Set a filter back to “All”.</td></tr>`}</tbody>`;
      $("#f-count").textContent = `${sel.length} of ${rows.length} rows`;
    }
    [fe, fg, fp].forEach((s) => s.addEventListener("change", render));
    render();
  }
  function buildRecovery(rec, mig) {
    const tiers = {};
    rec.forEach((r) => { const t = r.recovery_tier.split(" ")[0]; if (/^T\d$/.test(t) && !tiers[t]) tiers[t] = r; });
    $("#tiers").innerHTML = Object.keys(tiers).sort().map((t) => `<div><b>${t}</b><span class="dur">${esc(tiers[t].typical_duration)}</span><span>${esc(tiers[t].tier_definition)}</span></div>`).join("");
    $("#t-recovery").innerHTML = `<thead><tr><th>ID</th><th>Facility</th><th>Component</th><th>Known damage</th><th>Tier</th><th>Status 19 Oct</th><th>Basis</th><th>Assessment</th><th>Sources</th></tr></thead><tbody>` +
      rec.map((r) => `<tr><td class="id">${esc(r.row_id)}</td><td class="mid">${esc(r.facility)}</td><td class="mid">${esc(r.component)}</td><td class="mid">${esc(r.known_damage)}</td><td>${esc(r.recovery_tier)}</td><td class="wide">${esc(r["status_2026-10-19"])}</td><td>${esc(r.basis)}</td><td>${esc(r.assessment_type)}</td><td>${sourceLinks(r.sources)}</td></tr>`).join("") + `</tbody>`;
    $("#t-migration").innerHTML = `<thead><tr><th>ID</th><th>Operator</th><th>Scenario</th><th>Evidence for</th><th>Against or unknown</th><th>What to watch</th><th>Assessment</th><th>Sources</th></tr></thead><tbody>` +
      mig.map((r) => `<tr><td class="id">${esc(r.scenario_id)}</td><td>${esc(r.owner_operator)}</td><td class="mid"><b>${esc(r.scenario)}</b><br>${esc(r.description)}</td><td class="wide">${esc(r.evidence_for)}</td><td class="mid">${esc(r.evidence_against_or_unknown)}</td><td class="mid">${esc(r.observable_indicators)}</td><td class="mid"><b>${esc(r.assessment)}</b><br><span class="muted">${esc(r.assessment_basis)}</span></td><td>${sourceLinks(r.sources)}</td></tr>`).join("") + `</tbody>`;
  }

  // ================================================================ boot
  const fail = (where) => (err) => { console.error(err); const el = $(where); if (el) el.insertAdjacentHTML("beforeend", `<p class="note">This part could not load (${esc(err.message)}). The files are in the data folder of the repository.</p>`); };
  const strikesP = getJSON("data/strikes.geojson");
  Promise.all([strikesP, getJSON("data/imagery.json")]).then(([s, im]) => { buildTimeline(s); buildStrikes(s, im); }).catch(fail("#strike-list"));
  Promise.all([strikesP, getJSON("data/struck_outlines.geojson"), getJSON("data/dc_buildings.geojson"), getJSON("data/dc_buildings_centroids.geojson"),
    getJSON("data/peeringdb_facilities.geojson"), getJSON("data/telecom_sites.geojson")])
    .then(([s, outlines, buildings, centroids, peeringdb, telecom]) => {
      if (!window.maplibregl) throw new Error("map library did not load");
      return buildMap(s, { outlines, buildings, centroids, peeringdb, telecom });
    }).catch(fail(".map-frame"));
  getJSON("data/ioda_reachability.json").then(buildIODA).catch(fail("#ioda-chart"));
  getJSON("data/cloudflare_embeds.json").then(buildRadar).catch(fail("#traffic"));
  Promise.all([getJSON("data/media_coverage.json"), strikesP]).then(([m, s]) => buildMedia(m, s)).catch(fail("#media"));
  getText("data/service_disruptions.csv").then((t) => buildDisruptions(parseCSV(t))).catch(fail("#disruptions"));
  Promise.all([getText("data/recovery_tiers.csv"), getText("data/migration_scenarios.csv")]).then(([a, b]) => buildRecovery(parseCSV(a), parseCSV(b))).catch(fail("#recovery"));
  getJSON("data/build.json").then((b) => { $("#built").textContent = b.built_utc.replace("T", " ").replace("Z", "") + " UTC"; }).catch(() => {});
})();
