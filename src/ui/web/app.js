"use strict";
const $ = id => document.getElementById(id);
const estado = { clases: [], marcadas: new Set(), vistoVideo: null, voces: null };

// ---------- utilidades ----------
function h(tag, attrs, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "onclick" || k === "onchange") e[k] = v; else if (v === true) e.setAttribute(k, ""); else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const c of hijos.flat()) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
}
async function api(ruta, cuerpo) {
  const opciones = cuerpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-Lipsync": "1" }, body: JSON.stringify(cuerpo) };
  const r = await fetch(ruta, opciones);
  const datos = await r.json().catch(() => ({ error: "Respuesta no válida del servidor" }));
  if (!r.ok || datos.error) throw new Error(datos.error || ("Error " + r.status));
  return datos;
}
function avisar(texto, bien) {
  const a = $("aviso"); a.textContent = texto; a.className = bien ? "bien" : ""; a.hidden = false;
  clearTimeout(avisar.t); avisar.t = setTimeout(() => a.hidden = true, bien ? 4000 : 12000);
}
async function seguro(fn) { try { return await fn(); } catch (e) { avisar(e.message); } }

// ---------- pestañas ----------
for (const b of document.querySelectorAll("#pestanas button")) b.onclick = () => {
  document.querySelectorAll("#pestanas button").forEach(x => x.classList.toggle("activa", x === b));
  for (const s of document.querySelectorAll("main > section")) s.hidden = s.id !== "p-" + b.dataset.p;
  if (b.dataset.p === "lote") cargarLote();
};

// ---------- estado del proyecto ----------
async function cargarEstado() {
  const e = await api("/api/estado");
  const chip = (txt, ok) => h("span", { class: "chip " + (ok ? "ok" : "mal") }, (ok ? "● " : "○ ") + txt);
  $("chips").replaceChildren(chip("voz (gemini-tts-studio)", e.tts), chip("ffmpeg", e.ffmpeg), chip("Rhubarb", e.rhubarb),
    h("span", { class: "chip" }, `${e.poses} poses · ${e.poses_con_parpadeo} con parpadeo`),
    h("span", { class: "chip" }, `${e.escenarios.length} escenario(s)`));
  const sel = $("op-escenario"), actual = sel.value;
  sel.replaceChildren(h("option", { value: "" }, "Automático (según la clase)"),
    ...e.escenarios.map(x => h("option", { value: x.id }, `${x.id} ${x.nombre} (${x.tipo})`)));
  sel.value = actual;
}

// ---------- clases ----------
async function cargarClases() {
  const d = await api("/api/clases");
  estado.clases = d.clases;
  $("nuevo-id").placeholder = d.siguiente_id;
  pintarClases();
}
function pintarClases() {
  const cuerpo = document.querySelector("#tabla-clases tbody");
  $("vacio").hidden = estado.clases.length > 0;
  $("cuenta").textContent = estado.clases.length ? `(${estado.clases.length})` : "";
  cuerpo.replaceChildren(...estado.clases.map(c => {
    const marca = h("input", { type: "checkbox", onchange: ev => { ev.target.checked ? estado.marcadas.add(c.id) : estado.marcadas.delete(c.id); actualizarMarcadas(); } });
    marca.checked = estado.marcadas.has(c.id);
    const idioma = h("select", { onchange: ev => cambiar(c.id, { idioma: ev.target.value }) },
      ...[["es", "Español"], ["en", "English"], ["mixto", "Mixto"]].map(([v, t]) => h("option", { value: v }, t)));
    idioma.value = c.idioma;
    const genero = h("select", { onchange: ev => cambiar(c.id, { genero: ev.target.value }) },
      h("option", { value: "hombre" }, "Hombre"), h("option", { value: "mujer" }, "Mujer"));
    genero.value = c.genero;
    return h("tr", {},
      h("td", {}, marca),
      h("td", {}, h("strong", {}, c.id), h("div", { class: "vista", title: c.vista_previa }, c.vista_previa)),
      h("td", {}, idioma), h("td", {}, genero),
      h("td", {}, `${c.palabras} (~${c.minutos} min)`),
      h("td", {}, c.audio ? h("span", { class: "ok" }, "✓ " + c.audio) : h("span", { class: "aviso" }, "sin voz")),
      h("td", {}, c.video ? h("a", { href: "#", onclick: ev => { ev.preventDefault(); verVideo(c.video); } }, "▶ ver") : "—"),
      h("td", { class: "acciones" },
        h("button", { class: "chico", onclick: () => editarTexto(c.id) }, "Texto"), " ",
        h("button", { class: "chico", onclick: () => generarVoz(c.id, !!c.audio) }, c.audio ? "Regenerar voz" : "Generar voz"), " ",
        h("button", { class: "chico primario", disabled: !c.audio, title: c.audio ? "" : "Genera la voz primero", onclick: () => renderizar(c.id) }, "Render"), " ",
        h("button", { class: "chico", onclick: () => quitar(c.id) }, "Quitar")));
  }));
  actualizarMarcadas();
}
function actualizarMarcadas() {
  $("lote-marcadas").textContent = `${estado.marcadas.size} clase${estado.marcadas.size === 1 ? "" : "s"} marcada${estado.marcadas.size === 1 ? "" : "s"}`;
}
$("marcar-todas").onchange = ev => { estado.clases.forEach(c => ev.target.checked ? estado.marcadas.add(c.id) : estado.marcadas.delete(c.id)); pintarClases(); };
async function cambiar(id, campos) { await seguro(async () => { await api("/api/clases/" + id, campos); await cargarClases(); }); }
$("btn-actualizar").onclick = () => seguro(async () => { await cargarClases(); await cargarEstado(); });

$("btn-guardar").onclick = () => seguro(async () => {
  const c = await api("/api/clases", { texto: $("nuevo-texto").value, id: $("nuevo-id").value.trim(), idioma: $("nuevo-idioma").value, genero: $("nuevo-genero").value });
  $("nuevo-texto").value = ""; $("nuevo-id").value = "";
  avisar(`Clase ${c.id} guardada (${c.palabras} palabras).`, true); await cargarClases();
});
$("btn-importar").onclick = () => seguro(async () => {
  const archivos = [...$("archivos").files];
  if (!archivos.length) throw new Error("Elige uno o varios archivos .txt primero");
  const datos = await Promise.all(archivos.map(async f => ({ nombre: f.name, texto: await f.text() })));
  const r = await api("/api/clases/importar", { archivos: datos, idioma: $("nuevo-idioma").value, genero: $("nuevo-genero").value });
  $("archivos").value = ""; avisar(`${r.ids.length} clase(s) importada(s).`, true); await cargarClases();
});

const dlg = $("dlg-texto");
async function editarTexto(id) {
  await seguro(async () => {
    const d = await api(`/api/clases/${id}/texto`);
    $("dlg-titulo").textContent = "Guion de " + id; $("dlg-area").value = d.texto; dlg.dataset.id = id; dlg.showModal();
  });
}
$("dlg-cerrar").onclick = () => dlg.close();
$("dlg-guardar").onclick = () => seguro(async () => {
  await api("/api/clases/" + dlg.dataset.id, { texto: $("dlg-area").value }); dlg.close();
  avisar("Guion guardado. Si cambiaste el texto, regenera la voz.", true); await cargarClases();
});
async function quitar(id) {
  if (!confirm(`¿Quitar ${id} de la lista? El guion se guarda en clases/_papelera.`)) return;
  await seguro(async () => { await api(`/api/clases/${id}/eliminar`, {}); estado.marcadas.delete(id); await cargarClases(); });
}

// ---------- voz y render ----------
async function generarVoz(id, regenerar) {
  if (regenerar && !confirm("Se generará de nuevo el audio con la voz actual y el anterior pasa a la papelera. ¿Seguir?")) return;
  await seguro(async () => { await api("/api/voz/generar", { id, forzar: regenerar }); avisar("Generando la voz… mira el avance en «Render».", true); sondear(); });
}
async function renderizar(id) {
  await seguro(async () => {
    await api("/api/render", { id, escenario: $("op-escenario").value, plano: $("op-plano").value, director: $("op-director").checked });
    avisar("Render lanzado. Tarda unos minutos; el avance sale en «Render».", true); sondear();
    document.querySelector('#pestanas button[data-p="render"]').click();
  });
}
function verVideo(nombre, cambiarPestana = true) {
  const v = $("visor"); if (estado.vistoVideo !== nombre) { v.src = "/salidas/" + encodeURIComponent(nombre); estado.vistoVideo = nombre; }
  v.hidden = false; $("visor-nota").textContent = nombre;
  if (cambiarPestana) document.querySelector('#pestanas button[data-p="render"]').click();
}

// ---------- voces (catálogo) ----------
$("btn-voces").onclick = () => seguro(async () => {
  $("voces-nota").textContent = "Consultando el catálogo…";
  const [es, en] = await Promise.all([api("/api/voces?idioma=es"), api("/api/voces?idioma=en")]);
  $("voces-nota").textContent = "Elige, escucha y guarda.";
  const guardadas = es.guardadas;
  $("voces").replaceChildren(columnaVoces("es", "Español", es.catalogo, guardadas.es), columnaVoces("en", "English", en.catalogo, guardadas.en));
});
function columnaVoces(idioma, titulo, catalogo, actual) {
  const opciones = g => [h("option", { value: "" }, "(sin cambiar)"), ...catalogo.filter(v => !g || !v.genero || v.genero.startsWith(g))
    .map(v => h("option", { value: v.id, title: v.descripcion }, `${v.nombre}${v.genero ? " · " + v.genero : ""}`))];
  const selH = h("select", {}, ...opciones("m")), selM = h("select", {}, ...opciones("f"));
  const audio = h("audio", { controls: true, hidden: true, style: "width:100%" });
  const escuchar = (genero, sel) => seguro(async () => {
    const voz = sel.value || actual[genero]; if (!voz) throw new Error("No hay voz elegida ni guardada para escuchar");
    avisar("Generando la muestra…", true);
    const r = await api("/api/muestra", { idioma, genero, voz }); audio.src = r.url; audio.hidden = false; audio.play();
  });
  return h("div", { class: "col" },
    h("h3", {}, titulo), h("div", { class: "nota" }, `Guardada: hombre ${actual.hombre || "—"} · mujer ${actual.mujer || "—"}`),
    h("label", {}, "Voz de hombre"), selH, h("button", { class: "chico", onclick: () => escuchar("hombre", selH) }, "▶ Escuchar"),
    h("label", {}, "Voz de mujer"), selM, h("button", { class: "chico", onclick: () => escuchar("mujer", selM) }, "▶ Escuchar"),
    audio,
    h("div", { class: "fila" }, h("button", { class: "primario chico", onclick: () => seguro(async () => {
      await api("/api/voces", { idioma, hombre: selH.value || null, mujer: selM.value || null });
      avisar(`Voces de ${titulo} guardadas. Las clases nuevas ya las usan.`, true); $("btn-voces").click();
    }) }, "Guardar estas voces")));
}

// ---------- tareas ----------
function duracion(t) { const s = Math.round(((t.fin || Date.now() / 1000) - t.inicio)); return s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`; }
async function cargarTareas() {
  const { tareas } = await api("/api/tareas");
  $("tareas-vacio").hidden = tareas.length > 0;
  $("tareas").replaceChildren(...tareas.map(t => h("div", { class: "tarea" },
    h("div", { class: "cab" }, h("strong", {}, t.titulo),
      h("span", { class: t.estado === "hecha" ? "ok" : t.estado === "error" ? "mal" : "aviso" }, t.estado + " · " + duracion(t))),
    t.error ? h("div", { class: "mal" }, t.error) : "",
    t.salida && /\.mp4$/.test(t.salida) ? h("button", { class: "chico", onclick: () => verVideo(t.salida) }, "▶ Ver " + t.salida) : "",
    t.log ? h("pre", {}, t.log.split("\n").slice(-8).join("\n")) : "")));
  const ultimo = tareas.find(t => t.estado === "hecha" && /\.mp4$/.test(t.salida));
  if (ultimo && estado.vistoVideo === null) verVideo(ultimo.salida, false);
  const hayEnCurso = tareas.some(t => t.estado === "en curso");
  if (!hayEnCurso && estado.habiaEnCurso) await cargarClases();
  estado.habiaEnCurso = hayEnCurso;
  return hayEnCurso;
}
let temporizador = null;
function sondear() {
  clearTimeout(temporizador);
  const vuelta = async () => { const en = await cargarTareas().catch(() => false); temporizador = setTimeout(vuelta, en ? 2000 : 8000); };
  vuelta();
}

// ---------- lote ----------
async function cargarLote() {
  const l = await api("/api/lote");
  $("lote-resumen").textContent = l.total ? "· " + Object.entries(l.estados).map(([k, v]) => `${v} ${k}`).join(" · ") : "· vacía";
  document.querySelector("#tabla-lote tbody").replaceChildren(...l.trabajos.map(t => h("tr", {},
    h("td", {}, t.id), h("td", {}, t.lote),
    h("td", { class: t.estado === "hecho" ? "ok" : t.estado === "error" ? "mal" : "" }, t.estado),
    h("td", {}, t.error ? t.error.slice(0, 120) : (t.salida ? t.salida.split(/[\\/]/).pop() : "")))));
}
$("btn-lote-crear").onclick = () => seguro(async () => {
  const nombre = $("lote-nombre").value.trim() || new Date().toISOString().slice(0, 10) + "-A";
  const r = await api("/api/lote", { nombre, ids: [...estado.marcadas] });
  avisar(`${r.encoladas} clase(s) encolada(s) en el lote ${nombre}` + (r.ya_estaban ? ` (${r.ya_estaban} ya estaban)` : "") + ".", true); cargarLote();
});
$("btn-lote-correr").onclick = () => seguro(async () => {
  await api("/api/lote/correr", { trabajadores: +$("lote-trab").value }); avisar("Lote en marcha. Mira el avance aquí abajo.", true); sondear();
  const refrescar = setInterval(() => { if (!document.querySelector('#p-lote').hidden) cargarLote(); }, 5000); setTimeout(() => clearInterval(refrescar), 3600000);
});
$("btn-lote-reintentar").onclick = () => seguro(async () => { const r = await api("/api/lote/reintentar", {}); avisar(`${r.reintentadas} clase(s) vuelven a la cola.`, true); cargarLote(); });
$("lote-nombre").placeholder = new Date().toISOString().slice(0, 10) + "-A";

// ---------- arranque ----------
seguro(async () => { await cargarEstado(); await cargarClases(); sondear(); });
