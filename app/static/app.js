"use strict";
L.drawLocal.draw.handlers.rectangle.tooltip.start =
  "Klik og træk for at tegne rammen.";
L.drawLocal.draw.handlers.simpleshape.tooltip.end = "Slip for at gemme rammen.";
L.drawLocal.edit.handlers.edit.tooltip.text =
  "Træk i midten for at flytte eller i hjørnerne for at ændre rammen.";
L.drawLocal.edit.handlers.edit.tooltip.subtext = "Klik på Gem ramme bagefter.";
const $ = (id) => document.getElementById(id);
let bbox = [573235, 6222400, 576535, 6226600],
  map,
  rect,
  group,
  profiles = [],
  sources = [],
  previewKey = "",
  previewRevision = 0,
  timer,
  estimateValid = false,
  revision = 0;
function updateStart() {
  $("start").disabled = !estimateValid || !$("checked").checked ||
    previewKey !== JSON.stringify({bbox,source_profile:$("sourceProfile").value}) || !!editor;
}
function duration(seconds) {
  if (seconds < 60) return "under 1 min";
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
  return `${(seconds / 3600).toLocaleString("da", {maximumFractionDigits:1})} timer`;
}
function message(s) {
  $("message").textContent = s;
  clearTimeout(timer);
  timer = setTimeout(() => ($("message").textContent = ""), 10000);
}
async function api(path, data) {
  const r = await fetch("/api/" + path, {
    method: data === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", "X-Plotter-Request": "1" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!r.ok) {
    let s;
    try {
      s = (await r.json()).detail;
    } catch {
      s = "Serveren kunne ikke svare.";
    }
    throw Error(s);
  }
  return r.headers.get("Content-Type")?.includes("image/")
    ? r.blob()
    : r.json();
}
function job() {
  return {
    bbox: bbox.slice(),
    source_profile: $("sourceProfile").value || "dmp_1954",
    paper: $("paper").value,
    orientation: $("orientation").value,
    dpi: $("dpi").value === "full" ? "full" : Number($("dpi").value),
    meters_per_pixel: Number($("gsd").value),
    margin_mm: Number($("margin").value),
    title: $("title").value,
  };
}
function currentSource() {
  return sources.find(s => s.id === $("sourceProfile").value) || sources[0] ||
    {id:"dmp_1954",period:"1954",label:"DDO 1954"};
}
function sourceOptions() {
  const s=currentSource(), gs=$("gsd");
  gs.replaceChildren();
  for (const value of s.meters_per_pixel || [0.25,0.5,1]) {
    const o=document.createElement("option");
    o.value=String(value);
    o.textContent=value.toLocaleString("da")+" meter";
    gs.append(o);
  }
  gs.value=String(s.default_mpp || .25);
  $("sourceHelp").textContent=s.period+" · "+s.provider+
    (s.available ? " · Kontrollér udgaveår og faktisk dækning." : " · "+s.reason);
  if (s.license_url) {
    const link=document.createElement("a");
    link.href=s.license_url; link.textContent=" · Licens";
    link.target="_blank"; link.rel="noopener";
    $("sourceHelp").append(link);
  }
}
function invalidate() {
  ++previewRevision;
  previewKey = "";
  $("checked").checked = false;
  $("start").disabled = true;
  $("previewBox").replaceChildren(
    Object.assign(document.createElement("span"), {
      textContent: "Kilde eller område er ændret — hent et nyt prøvebillede",
    }),
  );
}
function dpiOptions(native) {
  const select=$("dpi"), previous=select.value;
  select.replaceChildren();
  const full=document.createElement("option");full.value="full";
  full.textContent=`Fuld kildeopløsning · ${native.toLocaleString("da",{maximumFractionDigits:1})} DPI`;
  select.append(full);
  for(let dpi=(Math.ceil(native/50)-1)*50;dpi>=50;dpi-=50) {
    const o=document.createElement("option");o.value=String(dpi);o.textContent=`${dpi} DPI`;select.append(o);
  }
  select.value=previous!=="full" && Number(previous)<native && Number(previous)>=50 && Number(previous)%50===0 ? previous : "full";
}
async function refreshEstimate() {
  const v = ++revision;
  const j = job();
  estimateValid = false;
  updateStart();
  $("size").textContent =
    `${((bbox[2] - bbox[0]) / 1000).toFixed(2)} × ${((bbox[3] - bbox[1]) / 1000).toFixed(2)} km`;
  $("bbox").value = bbox.map((x) => x.toFixed(2)).join(", ");
  $("estimate").textContent = "Kontrollerer det aktuelle udsnit…";
  try {
    const e = await api("estimate", j);
    if (v !== revision) return;
    if (e.native_dpi) {
      dpiOptions(e.native_dpi);
      if ($("dpi").value !== String(j.dpi)) return refreshEstimate();
    }
    $("size").textContent =
      `${((bbox[2] - bbox[0]) / 1000).toFixed(2)} × ${((bbox[3] - bbox[1]) / 1000).toFixed(2)} km`;
    $("bbox").value = bbox.map((x) => x.toFixed(2)).join(", ");
    $("estimate").replaceChildren();
    const p = document.createElement("p");
    p.textContent = `${e.width_px.toLocaleString("da")} × ${e.height_px.toLocaleString("da")} eksportpixels · ca. ${e.tiles} billedforespørgsler`;
    $("estimate").append(p);
    for (const text of [
      `Ca. ${(e.disk_bytes / 1e9).toFixed(1)} GB diskreserve. Komprimering og midlertidige filer gør behovet usikkert.`,
      `Ledigt på serveren: ${(e.free_disk_bytes / 1e9).toFixed(1)} GB.${e.free_disk_bytes < e.disk_bytes ? " Der skal frigøres plads før dette job kan køre." : ""}`,
      ...(e.duration_seconds ? [`Anslået behandlingstid: ${duration(e.duration_seconds[0])} – ${duration(e.duration_seconds[1])}.`, e.duration_basis] : []),
      `Rasterets opløsning på papir: ${e.effective_dpi} DPI. Papir: ${e.paper_mm.join(" × ")} mm. Pixelafstand er ikke et mål for originalens detaljegrad.`,
      ...(e.pdf_width_px ? [`PDF: ${e.pdf_width_px.toLocaleString("da")} × ${e.pdf_height_px.toLocaleString("da")} pixels · ${e.pdf_dpi} DPI.`,
        e.pdf_width_px===e.width_px && e.pdf_height_px===e.height_px
          ? "Alle kildepixels bevares uden nedskalering eller ekstra JPEG-komprimering."
          : "PDF’en nedskaleres til den valgte opløsning og komprimeres tabsfrit. GeoTIFF bevarer alle kildepixels."] : []),
    ]) {
      const p = document.createElement("p");
      p.textContent = text;
      $("estimate").append(p);
    }
    estimateValid = true;
    updateStart();
  } catch (e) {
    if (v !== revision) return;
    $("estimate").textContent = e.message;
    message(e.message);
    updateStart();
  }
}
async function rectangle(fit = true) {
  stopEditing();
  const p = await api("convert", {
    direction: "geo",
    points: [
      [bbox[0], bbox[1]],
      [bbox[2], bbox[3]],
    ],
  });
  const bounds = L.latLngBounds(p.map(([x, y]) => [y, x]));
  if (rect) group.removeLayer(rect);
  rect = L.rectangle(bounds, {
    color: "#327d62",
    weight: 3,
    fillColor: "#a7d6c1",
    fillOpacity: 0.16,
  });
  group.addLayer(rect);
  if (fit) map.fitBounds(bounds, { padding: [30, 30] });
  await refreshEstimate();
}
async function fromRect(layer) {
  const b = layer.getBounds(),
    p = await api("convert", {
      direction: "utm",
      points: [
        [b.getWest(), b.getSouth()],
        [b.getEast(), b.getNorth()],
      ],
    });
  bbox = [p[0][0], p[0][1], p[1][0], p[1][1]];
  $("profile").selectedIndex = profiles.length;
  invalidate();
  await refreshEstimate();
}
let modernLayer, historicalLayer, mapImageUrl, mapTimer, mapRevision = 0, mapBusy = false;
function queueMapImage() {
  ++mapRevision;
  clearTimeout(mapTimer);
  if ($("background").value === "historical") mapTimer = setTimeout(loadMapImage, 450);
}
async function loadMapImage() {
  if (mapBusy || !map || $("background").value !== "historical" || $("workspace").hidden) return;
  const rev = mapRevision, bounds = map.getBounds(), size = map.getSize();
  const scale = Math.min(1, 1024 / size.x, 1024 / size.y);
  mapBusy = true;
  $("mapStatus").textContent = "Henter " + currentSource().label + "…";
  try {
    const blob = await api("map-image", {
      bbox:[bounds.getWest(),bounds.getSouth(),bounds.getEast(),bounds.getNorth()],
      width:Math.max(8,Math.round(size.x * scale)), height:Math.max(8,Math.round(size.y * scale)),
       source_profile: $("sourceProfile").value || "dmp_1954"
    });
    if (rev !== mapRevision || $("background").value !== "historical") return;
    const url = URL.createObjectURL(blob);
    const layer = L.imageOverlay(url,bounds,{opacity:1,interactive:false,attribution:currentSource().attribution});
    layer.once("load",()=>{
      if (rev !== mapRevision || $("background").value !== "historical") {
        map.removeLayer(layer); URL.revokeObjectURL(url); return;
      }
      if (historicalLayer) map.removeLayer(historicalLayer);
      if (mapImageUrl) URL.revokeObjectURL(mapImageUrl);
      historicalLayer=layer; mapImageUrl=url;
      layer.bringToBack(); if(rect) rect.bringToFront();
      $("mapStatus").textContent=currentSource().label+" · zoom ind for flere detaljer";
    });
    layer.addTo(map);
  } catch(e) {
    if(rev===mapRevision) $("mapStatus").textContent = `Kortet kunne ikke opdateres: ${e.message} Brug Opdatér kortbillede for at prøve igen.`;
  } finally {
    mapBusy=false;
    if(rev!==mapRevision) queueMapImage();
  }
}
$("background").onchange=()=>{
  ++mapRevision; clearTimeout(mapTimer);
  if($("background").value==="modern") {
    if(historicalLayer) map.removeLayer(historicalLayer);
    modernLayer.addTo(map);
    $("mapStatus").textContent="MODERNE ORIENTERINGSKORT · kommer aldrig med i eksporten";
  } else {
    map.removeLayer(modernLayer);
    if(historicalLayer) historicalLayer.addTo(map);
    queueMapImage();
  }
};
$("reloadMap").onclick=queueMapImage;
$("sourceProfile").onchange = async () => {
  ++mapRevision; clearTimeout(mapTimer);
  if (historicalLayer) {map.removeLayer(historicalLayer);historicalLayer=null;}
  if (mapImageUrl) {URL.revokeObjectURL(mapImageUrl);mapImageUrl=null;}
  sourceOptions();
  $("title").value="Aarhus · "+currentSource().period.split(" · ")[0];
  invalidate();
  await refreshEstimate();
  queueMapImage();
};
async function boot() {
  try {
    const cfg = await api("config");
    profiles = cfg.profiles;
    sources = cfg.sources || [{id:"dmp_1954",label:"DDO 1954",period:"1954",
      provider:"Hexagon",available:true,default_mpp:.25,meters_per_pixel:[.25,.5,1]}];
    $("sourceProfile").replaceChildren();
    for (const s of sources) {
      const option=document.createElement("option");
      option.value=s.id;
      option.disabled=!s.available;
      option.textContent=s.label+(s.available ? "" : " · ikke tilgængelig");
      $("sourceProfile").append(option);
    }
    $("sourceProfile").value="dmp_1954";
    sourceOptions();
    $("workspace").hidden = false;
    if (!map) {
      for (const p of profiles) {
        const o = document.createElement("option");
        o.textContent = p[0];
        $("profile").append(o);
      }
      $("profile").append(
        Object.assign(document.createElement("option"), {
          textContent: "Eget udsnit",
        }),
      );
      $("profile").selectedIndex = 1;
      map = L.map("map", { zoomControl: true, minZoom:10, maxZoom:19 });
      modernLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      });
      map.on("moveend",queueMapImage);
      group = L.featureGroup().addTo(map);
      map.on(L.Draw.Event.CREATED, async (e) => {
        group.clearLayers();
        rect = e.layer;
        group.addLayer(rect);
        await fromRect(rect);
      });
      await rectangle();
    }
    map.invalidateSize();
    queueMapImage();
    await listJobs();
  } catch (e) {
    message(e.message);
  }
}
$("profile").onchange = async () => {
  if ($("profile").selectedIndex === profiles.length) return;
  const [name, x, y, w, h] = profiles[$("profile").selectedIndex];
  bbox = [x - w * 500, y - h * 500, x + w * 500, y + h * 500];
  $("title").value = name + " · " + currentSource().period.split(" · ")[0];
  invalidate();
  await rectangle();
};
$("draw").onclick = () => {
  stopEditing();
  invalidate();
  new L.Draw.Rectangle(map, { shapeOptions: { color: "#327d62" } }).enable();
};
let editor;
function stopEditing() {
  if (editor) editor.disable();
  editor = null;
  $("edit").textContent = "Flyt / ændr ramme";
}
$("edit").onclick = async () => {
  if (editor) {
    editor.save();
    editor.disable();
    editor = null;
    $("edit").textContent = "Flyt / ændr ramme";
    await fromRect(rect);
  } else {
    editor = new L.EditToolbar.Edit(map, { featureGroup: group });
    editor.enable();
    $("edit").textContent = "Gem ramme";
    invalidate();
  }
};
$("fit").onclick = async () => {
  let [w, h] = {
    A0: [841, 1189],
    A1: [594, 841],
    A2: [420, 594],
    A3: [297, 420],
  }[$("paper").value];
  if (
    $("orientation").value === "landscape" ||
    ($("orientation").value === "auto" && bbox[2] - bbox[0] > bbox[3] - bbox[1])
  )
    [w, h] = [h, w];
  const m = Number($("margin").value),
    height = ((bbox[2] - bbox[0]) * (h - 2 * m)) / (w - 2 * m),
    cy = (bbox[1] + bbox[3]) / 2;
  bbox = [bbox[0], cy - height / 2, bbox[2], cy + height / 2];
  $("profile").selectedIndex = profiles.length;
  invalidate();
  await rectangle();
};
$("applyBbox").onclick = async () => {
  const b = $("bbox").value.split(",").map(Number);
  try {
    await api("estimate", { ...job(), bbox: b });
    bbox = b;
    $("profile").selectedIndex = profiles.length;
    invalidate();
    await rectangle();
  } catch (e) {
    message(e.message);
  }
};
for (const id of ["paper", "orientation", "dpi", "gsd", "margin", "title"])
  $(id).onchange = refreshEstimate;
$("previewButton").onclick = async () => {
  const j = job(),
    key = JSON.stringify({bbox:j.bbox,source_profile:j.source_profile});
  $("previewButton").disabled = true;
  const requestRevision = previewRevision;
  try {
    const b = await api("preview", j);
    if (requestRevision !== previewRevision || key !== JSON.stringify({bbox,source_profile:$("sourceProfile").value})) return;
    const im = document.createElement("img");
    im.alt = currentSource().label + " for det valgte område";
    const url = URL.createObjectURL(b);
    im.onload = () => URL.revokeObjectURL(url);
    im.src = url;
    $("previewBox").replaceChildren(im);
    previewKey = key;
    $("checked").checked = false;
    updateStart();
    message("Kontrollér motivet og markér feltet under billedet.");
  } catch (e) {
    message(e.message);
  } finally {
    $("previewButton").disabled = false;
  }
};
$("checked").onchange = updateStart;
$("start").onclick = async () => {
  $("start").disabled = true;
  try {
    await api("jobs", job());
    message("Eksporten er lagt i serverens kø.");
    await listJobs();
  } catch (e) {
    message(e.message);
  } finally {
    updateStart();
  }
};
$("import").onchange = async (e) => {
  try {
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > 32768) throw Error("Jobfilen må højst være 32 KB.");
    const j = JSON.parse(await f.text());
    const importedEstimate = await api("estimate", j);
    bbox = j.bbox;
    $("sourceProfile").value=j.source_profile || "dmp_1954";
    sourceOptions();
    if (j.meters_per_pixel !== undefined) $("gsd").value=String(j.meters_per_pixel);
    ++mapRevision;
    if (historicalLayer) {map.removeLayer(historicalLayer);historicalLayer=null;}
    if (mapImageUrl) {URL.revokeObjectURL(mapImageUrl);mapImageUrl=null;}
    $("profile").selectedIndex = profiles.length;
    for (const [id, key] of [
      ["paper", "paper"],
      ["orientation", "orientation"],
      ["gsd", "meters_per_pixel"],
      ["margin", "margin_mm"],
      ["title", "title"],
    ])
      if (j[key] !== undefined) $(id).value = j[key];
    dpiOptions(importedEstimate.native_dpi);
    $("dpi").value = typeof j.dpi === "number" && j.dpi % 50 === 0 && j.dpi < importedEstimate.native_dpi ? String(j.dpi) : "full";
    invalidate();
    await rectangle();
    queueMapImage();
    message("Jobbet er indlæst. Kontrollér et nyt prøvebillede før start.");
  } catch (e) {
    message(e.message);
  }
  e.target.value = "";
};
const states = {
  queued: "I kø",
  downloading: "Henter billeder",
  geotiff: "Samler GeoTIFF",
  pdf: "Danner PDF",
  done: "Færdig",
  interrupted: "Afbrudt ved genstart",
  cancelled: "Annulleret",
  error: "Fejl",
};
async function listJobs() {
  if ($("workspace").hidden) return;
  try {
    const jobs = await api("jobs");
    $("jobs").replaceChildren();
    if (!jobs.length) {
      $("jobs").textContent = "Dit første kort starter med et udsnit ovenfor.";
      return;
    }
    for (const j of jobs) {
      const row = document.createElement("article");
      row.className = "job";
      const info = document.createElement("div"),
        title = document.createElement("strong");
      title.textContent = j.config.title;
      info.append(title);
      const sourceInfo = document.createElement("p");
      const savedSource = sources.find(s => s.id === (j.config.source_profile || "dmp_1954"));
      sourceInfo.textContent = savedSource ? `${savedSource.label} · ${savedSource.period}` : j.config.source_profile;
      info.append(sourceInfo);
      const p = document.createElement("p");
      p.textContent = `${states[j.state]} · ${j.done}/${j.total} i fasen · ${Math.floor(j.elapsed / 60)} min ${Math.floor(j.elapsed % 60)} sek. arbejdstid`;
      info.append(p);
      const tileInfo = document.createElement("p");
      const [x0, y0, x1, y1] = j.config.bbox;
      const tiles =
        Math.ceil(Math.ceil((x1 - x0) / j.config.meters_per_pixel) / 1024) *
        Math.ceil(Math.ceil((y1 - y0) / j.config.meters_per_pixel) / 1024);
      tileInfo.textContent = `${j.state === "done" ? tiles : j.downloaded || 0}/${tiles} billedfelter gemt`;
      info.append(tileInfo);
      const time = document.createElement("p");
      time.textContent =
        "Seneste aktivitet: " + new Date(j.updated * 1000).toLocaleString("da");
      info.append(time);
      if (j.error) {
        const p = document.createElement("p");
        p.textContent = j.error;
        info.append(p);
      }
      if (["downloading", "geotiff", "pdf"].includes(j.state)) {
        const p = document.createElement("progress");
        p.max = j.total || 1;
        p.value = j.done;
        info.append(p);
      }
      const actions = document.createElement("div");
      actions.className = "job-actions";
      if (j.state === "done")
        for (const [file, label] of [
          ["map.pdf", "Hent PDF"],
          ["map.tif", "Hent GeoTIFF"],
          ["preview.png", "Se kort"],
        ]) {
          const a = document.createElement("a");
          a.href = `/api/jobs/${j.id}/files/${file}`;
          a.textContent = label;
          a.target = "_blank";
          actions.append(a);
        }
      for (const [action, label] of [
        "queued",
        "downloading",
        "geotiff",
        "pdf",
      ].includes(j.state)
        ? [["cancel", "Annullér"]]
        : j.state === "done"
          ? [["delete", "Slet"]]
          : [
              ["resume", "Genoptag"],
              ["delete", "Slet"],
            ]) {
        const b = document.createElement("button");
        b.textContent = label;
        b.onclick = async () => {
          if (
            action === "delete" &&
            !confirm(
              `Slet “${j.config.title}” og alle tilhørende kortfiler permanent?`,
            )
          )
            return;
          try {
            await api(`jobs/${j.id}/${action}`, { confirm: j.id });
            await listJobs();
          } catch (e) {
            message(e.message);
          }
        };
        actions.append(b);
      }
      row.append(info, actions);
      $("jobs").append(row);
    }
  } catch (e) {
    message(e.message);
  }
}
boot();
setInterval(listJobs, 4000);
