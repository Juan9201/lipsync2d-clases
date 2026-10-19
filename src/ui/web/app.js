"use strict";
const $ = id => document.getElementById(id);
const estado = { clases: [], marcadas: new Set(), vistoVideo: null, escenarios: [] };

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
  if (b.dataset.p === "escenarios") cargarEscenarios();
};

// ---------- estado del proyecto ----------
async function cargarEstado() {
  const e = await api("/api/estado");
  const chip = (txt, ok) => h("span", { class: "chip " + (ok ? "ok" : "mal") }, (ok ? "● " : "○ ") + txt);
  $("chips").replaceChildren(chip("voz (gemini-tts-studio)", e.tts), chip("ffmpeg", e.ffmpeg), chip("Rhubarb", e.rhubarb),
    h("span", { class: "chip" }, `${e.poses} poses · ${e.poses_con_parpadeo} con parpadeo`),
    h("span", { class: "chip" }, `${e.escenarios.length} escenario(s)`));
  estado.escenarios = e.escenarios;
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
    const voz = h("select", { onchange: ev => cambiar(c.id, { voz: ev.target.value }) },
      h("option", { value: "colombiano" }, "Colombiano"), h("option", { value: "neutro" }, "Neutro"));
    voz.value = c.voz;
    const escenario = h("select", { onchange: ev => cambiar(c.id, { escenarios: ev.target.value }) },
      h("option", { value: "" }, "Automático"), ...estado.escenarios.map(x => h("option", { value: x.id }, `${x.id} ${x.nombre}`)));
    escenario.value = c.escenarios;
    return h("tr", {},
      h("td", {}, marca),
      h("td", {}, h("strong", {}, c.id), h("div", { class: "vista", title: c.vista_previa }, c.vista_previa)),
      h("td", {}, idioma), h("td", {}, voz), h("td", {}, escenario),
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
  const c = await api("/api/clases", { texto: $("nuevo-texto").value, id: $("nuevo-id").value.trim(), idioma: $("nuevo-idioma").value, voz: $("nuevo-voz").value });
  $("nuevo-texto").value = ""; $("nuevo-id").value = "";
  avisar(`Clase ${c.id} guardada (${c.palabras} palabras).`, true); await cargarClases();
});
$("btn-importar").onclick = () => seguro(async () => {
  const archivos = [...$("archivos").files];
  if (!archivos.length) throw new Error("Elige uno o varios archivos .txt primero");
  const datos = await Promise.all(archivos.map(async f => ({ nombre: f.name, texto: await f.text() })));
  const r = await api("/api/clases/importar", { archivos: datos, idioma: $("nuevo-idioma").value, voz: $("nuevo-voz").value });
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

// ---------- escenarios (fondos) ----------
async function cargarEscenarios() {
  const e = await api("/api/estado"); estado.escenarios = e.escenarios;
  $("esc-vacio").hidden = e.escenarios.length > 0; $("esc-cuenta").textContent = e.escenarios.length ? `(${e.escenarios.length})` : "";
  $("esc-lista").replaceChildren(...e.escenarios.map(x => {
    const reemplazo = h("input", { type: "file", accept: ".png,.jpg,.jpeg,.webp,.mp4", hidden: true, onchange: ev => { if (ev.target.files[0]) subirFondo(ev.target.files[0], x.nombre, x.id); } });
    return h("div", { class: "tarjeta" },
      h("img", { src: `/miniaturas/${encodeURIComponent(x.carpeta)}.jpg?v=${Date.now()}`, alt: x.carpeta, loading: "lazy" }),
      h("div", { class: "cuerpo" }, h("strong", {}, `${x.id} ${x.nombre}`),
        h("div", { class: "nota" }, `${x.tipo === "video" ? "Video" : "Imagen"} · ${x.ancho}×${x.alto}` + (x.duracion ? ` · ${x.duracion} s` : "")),
        (x.ancho && (x.ancho < 1280 || x.alto < 720)) ? h("div", { class: "aviso nota" }, "Menor que 1280×720: se verá borroso") : "",
        h("div", { class: "fila" }, h("button", { class: "chico", onclick: () => reemplazo.click() }, "Reemplazar"), reemplazo,
          h("button", { class: "chico", onclick: () => quitarEscenario(x) }, "Quitar"))));
  }));
  await cargarEstado();
}
function subirFondo(archivo, nombre, reemplazar) {
  return new Promise(resolver => {
    const barra = $("esc-progreso"), texto = $("esc-estado");
    const xhr = new XMLHttpRequest();
    const q = new URLSearchParams({ nombre: nombre || archivo.name.replace(/\.[^.]+$/, ""), archivo: archivo.name });
    if (reemplazar) q.set("reemplazar", reemplazar);
    xhr.open("POST", "/api/escenarios?" + q);
    xhr.setRequestHeader("X-Lipsync", "1"); xhr.setRequestHeader("Content-Type", "application/octet-stream");
    barra.hidden = false; barra.value = 0; texto.textContent = "Subiendo…";
    xhr.upload.onprogress = ev => { if (ev.lengthComputable) { barra.value = 100 * ev.loaded / ev.total; texto.textContent = `Subiendo… ${Math.round(100 * ev.loaded / ev.total)} %`; } };
    xhr.onload = () => {
      barra.hidden = true; let d = {}; try { d = JSON.parse(xhr.responseText); } catch (e) { }
      if (xhr.status === 200) { texto.textContent = ""; avisar(`Fondo ${d.id} listo (${d.ancho}×${d.alto}).` + (d.aviso ? " Ojo: " + d.aviso + "." : ""), !d.aviso); cargarEscenarios(); }
      else { texto.textContent = ""; avisar(d.error || "No se pudo subir el fondo"); }
      resolver();
    };
    xhr.onerror = () => { barra.hidden = true; texto.textContent = ""; avisar("Se perdió la conexión con la interfaz mientras subía"); resolver(); };
    xhr.send(archivo);
  });
}
$("btn-esc-subir").onclick = async () => {
  const f = $("esc-archivo").files[0];
  if (!f) return avisar("Elige primero un archivo de imagen o video");
  await subirFondo(f, $("esc-nombre").value.trim(), null); $("esc-archivo").value = ""; $("esc-nombre").value = "";
};
async function quitarEscenario(x) {
  if (!confirm(`¿Quitar ${x.id} ${x.nombre}? Se guarda en escenarios/_papelera. Las clases que lo usaban pasan a Automático.`)) return;
  await seguro(async () => { await api(`/api/escenarios/${encodeURIComponent(x.carpeta)}/eliminar`, {}); avisar("Escenario quitado.", true); await cargarEscenarios(); await cargarClases(); });
}

// ---------- arranque ----------
seguro(async () => { await cargarEstado(); await cargarClases(); sondear(); });
