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
  if (b.dataset.p === "lote") { cargarLote(); cargarPublicacion(); }
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
function clasesVisibles() {
  const nivel = $("op-nivel").value, sinVideo = $("op-sinvideo").checked;
  return estado.clases.filter(c => (!nivel || c.id.startsWith(nivel + "-")) && (!sinVideo || !c.video));
}
function pintarClases() {
  const cuerpo = document.querySelector("#tabla-clases tbody");
  const visibles = clasesVisibles();
  $("vacio").hidden = estado.clases.length > 0;
  $("cuenta").textContent = estado.clases.length ? (visibles.length === estado.clases.length ? `(${estado.clases.length})` : `(${visibles.length} de ${estado.clases.length})`) : "";
  cuerpo.replaceChildren(...visibles.map(c => {
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
$("marcar-todas").onchange = ev => { clasesVisibles().forEach(c => ev.target.checked ? estado.marcadas.add(c.id) : estado.marcadas.delete(c.id)); pintarClases(); };
$("op-nivel").onchange = $("op-sinvideo").onchange = () => { $("marcar-todas").checked = false; pintarClases(); };
$("btn-producir").onclick = () => seguro(async () => {
  const marcadas = estado.clases.filter(c => estado.marcadas.has(c.id));
  if (!marcadas.length) throw new Error("Marca primero las clases que quieres producir");
  const trab = +$("op-trab").value, esc = $("op-escenario").value, sinVoz = marcadas.filter(c => !c.audio);
  const horas = Math.round(marcadas.length * 4 / trab / 60 * 10) / 10;
  const lineas = [`Vas a producir ${marcadas.length} clase(s) con ${trab} trabajador(es).`,
    `Escenario: ${esc || "automático (reparto entre los escenarios válidos)"}.`,
    sinVoz.length ? `Voz nueva (de pago, Gemini): ${sinVoz.length} clase(s), unos ${Math.round(sinVoz.reduce((s, c) => s + c.minutos, 0))} min de audio.` : "Todas ya tienen voz: no se paga voz nueva.",
    `Tiempo estimado de render: unas ${horas} h.`, "", "¿Continuar?"];
  const texto = lineas.join("\n");
  if (!confirm(texto)) return;
  const r = await api("/api/producir", { ids: marcadas.map(c => c.id), escenario: esc, trabajadores: trab });
  avisar(`Lote ${r.lote} en marcha: ${r.encoladas} nueva(s)` + (r.ya_estaban ? `, ${r.ya_estaban} ya estaban en la cola` : "") + ".", true);
  document.querySelector('#pestanas button[data-p="lote"]').click(); sondear();
});
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

$("btn-importar-drive").onclick = () => seguro(async () => {
  const r = await api("/api/clases/importar-carpeta", { carpeta: $("carpeta-drive").value.trim(), solo_ia: $("solo-ia").checked });
  const aviso = [`${r.creadas.length} nueva(s)`, `${r.actualizadas.length} actualizada(s)`, `${r.sin_cambios.length} sin cambios`];
  if (r.omitidas_humano.length) aviso.push(`${r.omitidas_humano.length} humana(s) omitida(s)`);
  if (r.ignoradas.length) aviso.push(`${r.ignoradas.length} ignorada(s): ${r.ignoradas.map(i => i.id).join(", ")}`);
  avisar("Guiones de Drive: " + aviso.join(" · ") + ".", true); await cargarClases();
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
    h("td", {}, t.error ? t.error.slice(0, 120) : (t.salida ? h("button", { class: "chico", title: "Verlo aquí", onclick: () => verVideo(t.salida.split(/[\\/]/).pop()) }, "▶ " + t.salida.split(/[\\/]/).pop()) : "")))));
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
async function cargarPublicacion() {
  const p = await api("/api/publicacion");
  const cuenta = {}; p.clases.forEach(c => cuenta[c.estado] = (cuenta[c.estado] || 0) + 1);
  $("pub-resumen").textContent = p.clases.length ? "· " + Object.entries(cuenta).map(([k, v]) => `${v} ${k}`).join(" · ") + " · Drive: " + p.drive : "· nada aún · Drive: " + p.drive;
  document.querySelector("#tabla-pub tbody").replaceChildren(...p.clases.slice(-60).reverse().map(c => h("tr", {},
    h("td", {}, c.id), h("td", {}, c.origen === "humano" ? "humana" : "IA"),
    h("td", { class: c.estado === "publicado" ? "ok" : c.estado === "error" ? "mal" : "" }, c.estado),
    h("td", {}, c.error ? c.error.slice(0, 120) : (c.destino || "")))));
}
$("btn-pub-correr").onclick = () => seguro(async () => { await api("/api/publicacion/correr", {}); avisar("Subtitulando lo pendiente. Mira el avance en «En vivo».", true); sondear(); cargarPublicacion(); });
$("btn-pub-reintentar").onclick = () => seguro(async () => { const r = await api("/api/publicacion/reintentar", {}); avisar(`${r.reintentadas} clase(s) vuelven a la cola de subtítulos.`, true); cargarPublicacion(); });
$("btn-abrir-salidas").onclick = () => seguro(async () => { const r = await api("/api/salidas/abrir", {}); avisar("Carpeta de videos: " + r.carpeta, true); });
$("btn-lote-reintentar").onclick = () => seguro(async () => { const r = await api("/api/lote/reintentar", {}); avisar(`${r.reintentadas} clase(s) vuelven a la cola.`, true); cargarLote(); });
$("lote-nombre").placeholder = new Date().toISOString().slice(0, 10) + "-A";

// ---------- actualizar poses ----------
$("btn-poses").onclick = () => seguro(async () => {
  const { cambios } = await api("/api/poses/cambios");
  const listas = cambios.filter(c => c.estado === "actualizable");
  const otras = cambios.filter(c => c.estado !== "actualizable");
  if (!cambios.length) return avisar("Todas las imágenes de Torso Organizado ya están en las poses del render.", true);
  const partes = [];
  if (listas.length) partes.push(`Se actualizarán ${listas.length} pose(s):\n` + listas.map(c => `  • ${c.pose}  (${c.detalle})`).join("\n"));
  if (otras.length) partes.push("No se tocan:\n" + otras.map(c => `  • ${c.pose}: ${c.detalle}`).join("\n"));
  if (!listas.length) return avisar(partes.join(" ").slice(0, 600));
  partes.push("Antes se guarda copia de las anteriores en respaldo_poses/. ¿Actualizar?");
  if (!confirm(partes.join("\n\n"))) return;
  const r = await api("/api/poses/actualizar", {});
  avisar(`${r.actualizadas.length} pose(s) actualizada(s): ${r.actualizadas.join(", ")}.` + (r.pendientes.length ? ` Quedan ${r.pendientes.length} por revisar a mano.` : ""), true);
});

// ---------- escenarios (fondos) ----------
async function cargarEscenarios() {
  const e = await api("/api/estado"); estado.escenarios = e.escenarios;
  $("esc-vacio").hidden = e.escenarios.length > 0; $("esc-cuenta").textContent = e.escenarios.length ? `(${e.escenarios.length})` : "";
  $("esc-lista").replaceChildren(...e.escenarios.map(x => {
    const reemplazo = h("input", { type: "file", accept: ".png,.jpg,.jpeg,.webp,.mp4", hidden: true, onchange: ev => { if (ev.target.files[0]) subirFondo(ev.target.files[0], x.nombre, x.id); } });
    const frente = h("input", { type: "file", accept: ".png,image/png", hidden: true, onchange: ev => { if (ev.target.files[0]) subirFrente(ev.target.files[0], x.carpeta); } });
    return h("div", { class: "tarjeta" },
      h("img", { src: `/miniaturas/${encodeURIComponent(x.carpeta)}.jpg?v=${Date.now()}`, alt: x.carpeta, loading: "lazy" }),
      h("div", { class: "cuerpo" }, h("strong", {}, `${x.id} ${x.nombre}`),
        h("div", { class: "nota" }, `${x.tipo === "video" ? "Video" : "Imagen"} · ${x.ancho}×${x.alto}` + (x.duracion ? ` · ${x.duracion} s` : "")),
        (x.ancho && (x.ancho < 1280 || x.alto < 720)) ? h("div", { class: "aviso nota" }, "Menor que 1280×720: se verá borroso") : "",
        x.transparente > 0.25 ? h("div", { class: "mal nota" }, `⚠ ${Math.round(x.transparente * 100)} % del fondo es transparente: se verá negro. ¿Es una capa delantera? Súbela como «frente» de otro escenario. El reparto automático no lo usa.`) : "",
        h("div", { class: "nota" }, x.capas ? h("span", { class: "ok" }, "● con capas (frente)") : "sin frente"),
        h("div", { class: "fila" }, h("button", { class: "chico", onclick: () => reemplazo.click() }, "Reemplazar"), reemplazo,
          h("button", { class: "chico", onclick: () => frente.click() }, x.capas ? "Cambiar frente" : "Subir frente"), frente,
          x.capas ? h("button", { class: "chico primario", onclick: () => abrirEditor(x.carpeta) }, "Editar escena") : "",
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

// ---------- subir el frente y editor de escenas ----------
function subirFrente(archivo, carpeta) {
  const barra = $("esc-progreso"), texto = $("esc-estado"), xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/escenas/${encodeURIComponent(carpeta)}/frente`);
  xhr.setRequestHeader("X-Lipsync", "1"); xhr.setRequestHeader("Content-Type", "application/octet-stream");
  barra.hidden = false; barra.value = 0; texto.textContent = "Subiendo el frente…";
  xhr.upload.onprogress = ev => { if (ev.lengthComputable) barra.value = 100 * ev.loaded / ev.total; };
  xhr.onload = () => { barra.hidden = true; texto.textContent = ""; let d = {}; try { d = JSON.parse(xhr.responseText); } catch (e) { }
    if (xhr.status === 200) { avisar(`Frente guardado. Luces detectadas: ${d.luces_detectadas}. Pulsa «Editar escena».`, true); cargarEscenarios(); } else avisar(d.error || "No se pudo subir el frente"); };
  xhr.onerror = () => { barra.hidden = true; avisar("Se perdió la conexión mientras subía"); };
  xhr.send(archivo);
}

const ed = { carpeta: null, cfg: null, poses: [], pose: null, visema: "X", ojos: "abierto", v: [0, 0, 1280, 720], pidiendo: false, pendiente: null, tGuardar: null, luz: 0, url: null };
const planoActual = () => $("ed-plano").value;

async function abrirEditor(carpeta) {
  await seguro(async () => {
    const d = await api(`/api/escenas/${encodeURIComponent(carpeta)}/config`);
    Object.assign(ed, { carpeta, cfg: d.config, poses: d.poses, luz: 0 });
    ed.pose = (d.poses.find(p => p.id === "frontal_neutro_01") || d.poses[0] || {}).id;
    $("ed-titulo").textContent = carpeta; $("esc-editor").hidden = false; $("esc-editor").scrollIntoView({ behavior: "smooth" });
    $("ed-pose").replaceChildren(...d.poses.map(p => h("option", { value: p.id }, p.id.replace("tres_cuartos_der", "3/4").replace("_", " ")))); $("ed-pose").value = ed.pose;
    $("ed-bocas").replaceChildren(..."ABCDEFGHX".split("").map(v => h("button", { "data-v": v, onclick: () => { ed.visema = v; marcarBotones(); vista(false); } }, v)));
    $("ed-ojos").replaceChildren(...["abierto", "medio", "cerrado"].map(o => h("button", { "data-o": o, onclick: () => { ed.ojos = o; marcarBotones(); vista(false); } }, o)));
    marcarBotones(); pintarControles(); vista(false);
  });
}
$("ed-cerrar").onclick = () => { $("esc-editor").hidden = true; };
function marcarBotones() {
  document.querySelectorAll("#ed-bocas button").forEach(b => b.classList.toggle("activo", b.dataset.v === ed.visema));
  document.querySelectorAll("#ed-ojos button").forEach(b => b.classList.toggle("activo", b.dataset.o === ed.ojos));
}
const colorAHex = c => "#" + c.map(x => Math.max(0, Math.min(255, Math.round(x * 255))).toString(16).padStart(2, "0")).join("");
const hexACol = hx => [1, 3, 5].map(i => +(parseInt(hx.slice(i, i + 2), 16) / 255).toFixed(3));

function pintarControles() {
  const c = ed.cfg, a = c.personaje.ajustes[ed.pose] || { dx: 0, dy: 0 };
  $("ed-cx").value = Math.round(c.personaje.cabeza[0]); $("ed-cy").value = Math.round(c.personaje.cabeza[1]);
  $("ed-esc").value = c.personaje.escala; $("ed-escn").value = c.personaje.escala.toFixed(2);
  $("ed-dx").value = a.dx; $("ed-dy").value = a.dy;
  $("ed-mesa").max = c.lienzo[1]; $("ed-mesa").value = c.mesa.y; $("ed-mesan").value = Math.round(c.mesa.y);
  $("ed-luz-activa").checked = c.luz.activa; $("ed-ambiente").value = colorAHex(c.luz.ambiente);
  $("ed-luces").replaceChildren(...c.luz.luces.map((L, i) => h("div", { class: "luz" + (i === ed.luz ? " sel" : "") },
    h("div", { class: "fila" }, h("label", { class: "check" }, h("input", { type: "radio", name: "luz-sel", checked: i === ed.luz, onchange: () => { ed.luz = i; pintarControles(); guias(); } }), " "),
      h("input", { value: L.nombre, size: 14, onchange: e => { L.nombre = e.target.value; cambiado(); } }),
      h("input", { type: "color", value: colorAHex(L.color), onchange: e => { L.color = hexACol(e.target.value); cambiado(); } }),
      h("button", { class: "chico", onclick: () => { c.luz.luces.splice(i, 1); ed.luz = 0; pintarControles(); cambiado(); } }, "Quitar")),
    h("div", { class: "fila" }, ...[["fuerza", 0, 3, 0.05], ["alcance", 100, 4000, 20], ["altura", 20, 2500, 10]].map(([k, mn, mx, st]) =>
      h("label", {}, k, h("input", { type: "range", min: mn, max: mx, step: st, value: L[k], oninput: e => { L[k] = +e.target.value; cambiado(true); } })))),
    h("div", { class: "fila" }, h("label", {}, "x", h("input", { type: "number", value: Math.round(L.pos[0]), onchange: e => { L.pos[0] = +e.target.value; cambiado(); } })),
      h("label", {}, "y", h("input", { type: "number", value: Math.round(L.pos[1]), onchange: e => { L.pos[1] = +e.target.value; cambiado(); } }))))));
  const permitidas = new Set(c.poses_permitidas);
  $("ed-poses").replaceChildren(...ed.poses.map(p => h("label", {}, h("input", { type: "checkbox", checked: permitidas.has(p.id), onchange: e => {
    const s = new Set(ed.cfg.poses_permitidas); e.target.checked ? s.add(p.id) : s.delete(p.id); ed.cfg.poses_permitidas = [...s]; cambiado(); } }), p.id.replace("tres_cuartos_der", "3/4"))));
}
function cambiado(borrador) { vista(!!borrador); programaGuardar(); }
function programaGuardar() {
  $("ed-guardado").textContent = "· cambios sin guardar…"; clearTimeout(ed.tGuardar);
  ed.tGuardar = setTimeout(async () => {
    try { const r = await api(`/api/escenas/${encodeURIComponent(ed.carpeta)}/config`, { config: ed.cfg }); ed.cfg = { ...r.config, lienzo: ed.cfg.lienzo };
      $("ed-guardado").textContent = "· guardado ✓ " + new Date().toLocaleTimeString(); }
    catch (e) { $("ed-guardado").textContent = "· NO se guardó: " + e.message; avisar(e.message); }
  }, 1200);
}
const ligar = (id, fn, evento = "input") => $(id).addEventListener(evento, e => { const x = parseFloat(e.target.value); if (!isNaN(x)) { fn(x); pintarControlesSuaves(); cambiado(evento === "input"); } });
function pintarControlesSuaves() { // refresca solo los números que dependen unos de otros, sin reconstruir las listas (el foco no se pierde)
  const c = ed.cfg; $("ed-escn").value = c.personaje.escala.toFixed(2); $("ed-esc").value = c.personaje.escala; $("ed-mesan").value = Math.round(c.mesa.y); $("ed-mesa").value = c.mesa.y;
}
ligar("ed-cx", x => ed.cfg.personaje.cabeza[0] = x); ligar("ed-cy", x => ed.cfg.personaje.cabeza[1] = x);
ligar("ed-esc", x => ed.cfg.personaje.escala = x); ligar("ed-escn", x => ed.cfg.personaje.escala = x);
ligar("ed-mesa", x => ed.cfg.mesa.y = x); ligar("ed-mesan", x => ed.cfg.mesa.y = x);
const ajuste = () => (ed.cfg.personaje.ajustes[ed.pose] = ed.cfg.personaje.ajustes[ed.pose] || { dx: 0, dy: 0 });
ligar("ed-dx", x => ajuste().dx = x); ligar("ed-dy", x => ajuste().dy = x);
$("ed-aj-reset").onclick = () => { delete ed.cfg.personaje.ajustes[ed.pose]; pintarControles(); cambiado(); };
$("ed-aj-todas").onclick = () => { const a = ajuste(); ed.poses.forEach(p => ed.cfg.personaje.ajustes[p.id] = { dx: a.dx, dy: a.dy }); avisar("Ajuste copiado a todas las poses.", true); cambiado(); };
$("ed-luz-activa").onchange = e => { ed.cfg.luz.activa = e.target.checked; cambiado(); };
$("ed-ambiente").onchange = e => { ed.cfg.luz.ambiente = hexACol(e.target.value); cambiado(); };
$("ed-luz-nueva").onclick = () => { if (ed.cfg.luz.luces.length >= 8) return avisar("Máximo 8 luces"); const w = ed.cfg.lienzo[0];
  ed.cfg.luz.luces.push({ nombre: "luz " + (ed.cfg.luz.luces.length + 1), pos: [w / 2, ed.cfg.lienzo[1] / 3], color: [1, 0.85, 0.65], fuerza: 1, alcance: Math.round(w * 0.3), altura: Math.round(w * 0.1) });
  ed.luz = ed.cfg.luz.luces.length - 1; pintarControles(); cambiado(); };
$("ed-pp-todas").onclick = () => { ed.cfg.poses_permitidas = ed.poses.map(p => p.id); pintarControles(); cambiado(); };
$("ed-pp-ninguna").onclick = () => { ed.cfg.poses_permitidas = []; pintarControles(); cambiado(); };
$("ed-plano").onchange = () => vista(false);
$("ed-luz").onchange = () => vista(false);
$("ed-ver-guias").onchange = guias;
$("ed-pose").onchange = e => { ed.pose = e.target.value; pintarControles(); vista(false); };

// ---- la vista previa la dibuja el servidor con el mismo código del render: la boca y los ojos no pueden quedar fuera de sitio ----
async function vista(borrador) {
  if (!ed.carpeta) return;
  if (ed.pidiendo) { ed.pendiente = borrador; return; }
  ed.pidiendo = true;
  try {
    const r = await fetch(`/api/escenas/${encodeURIComponent(ed.carpeta)}/vista`, { method: "POST", headers: { "Content-Type": "application/json", "X-Lipsync": "1" },
      body: JSON.stringify({ config: ed.cfg, pose: ed.pose, plano: planoActual(), visema: ed.visema, ojos: ed.ojos, luz: $("ed-luz").checked, borrador }) });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || "No se pudo dibujar la vista previa"); }
    ed.v = r.headers.get("X-Ventana").split(",").map(Number);
    const blob = await r.blob(); const url = URL.createObjectURL(blob);
    const img = $("ed-img"); img.onload = () => { guias(); if (ed.url) URL.revokeObjectURL(ed.url); ed.url = url; }; img.src = url;
  } catch (e) { avisar(e.message); }
  finally { ed.pidiendo = false; if (ed.pendiente !== null) { const b = ed.pendiente; ed.pendiente = null; vista(b); } }
}
function guias() {
  const img = $("ed-img"), cv = $("ed-guias"); cv.width = img.clientWidth; cv.height = img.clientHeight;
  const k = cv.getContext("2d"); k.clearRect(0, 0, cv.width, cv.height); if (!$("ed-ver-guias").checked || !ed.cfg) return;
  const [x0, y0, w, h] = ed.v, ex = cv.width / w, ey = cv.height / h;
  const ym = (ed.cfg.mesa.y - y0) * ey; k.strokeStyle = "rgba(255,200,0,.9)"; k.setLineDash([8, 6]); k.lineWidth = 2; k.beginPath(); k.moveTo(0, ym); k.lineTo(cv.width, ym); k.stroke(); k.setLineDash([]);
  k.fillStyle = "rgba(255,200,0,.9)"; k.font = "12px sans-serif"; k.fillText("borde de la mesa", 6, ym - 5);
  ed.cfg.luz.luces.forEach((L, i) => { const px = (L.pos[0] - x0) * ex, py = (L.pos[1] - y0) * ey; k.strokeStyle = colorAHex(L.color); k.lineWidth = i === ed.luz ? 3 : 1.5;
    k.beginPath(); k.arc(px, py, i === ed.luz ? 11 : 8, 0, 7); k.stroke(); k.beginPath(); k.moveTo(px - 14, py); k.lineTo(px + 14, py); k.moveTo(px, py - 14); k.lineTo(px, py + 14); k.stroke();
    k.fillStyle = colorAHex(L.color); k.fillText(L.nombre, px + 12, py - 12); });
  const cx = (ed.cfg.personaje.cabeza[0] - x0) * ex, cy = (ed.cfg.personaje.cabeza[1] - y0) * ey; k.strokeStyle = "rgba(76,194,255,.9)"; k.lineWidth = 1.5;
  k.beginPath(); k.moveTo(cx - 10, cy); k.lineTo(cx + 10, cy); k.moveTo(cx, cy - 10); k.lineTo(cx, cy + 10); k.stroke();
}
window.addEventListener("resize", () => { if (ed.carpeta && !$("esc-editor").hidden) guias(); });
(function () {
  const lienzo = document.querySelector(".lienzo-ed"); let arr = null;
  const aEscena = ev => { const r = $("ed-img").getBoundingClientRect(), [x0, y0, w, h] = ed.v; return [x0 + (ev.clientX - r.left) / r.width * w, y0 + (ev.clientY - r.top) / r.height * h, w / r.width]; };
  lienzo.addEventListener("mousedown", ev => {
    if (!ed.cfg) return; ev.preventDefault(); const modo = $("ed-modo").value, [sx, sy, esc] = aEscena(ev);
    if (modo === "luz") { const L = ed.cfg.luz.luces[ed.luz]; if (!L) return avisar("Primero añade una luz"); L.pos = [Math.round(sx), Math.round(sy)]; pintarControles(); cambiado(); return; }
    arr = { modo, x: ev.clientX, y: ev.clientY, cab: [...ed.cfg.personaje.cabeza], mesa: ed.cfg.mesa.y, esc }; lienzo.style.cursor = "grabbing";
  });
  window.addEventListener("mousemove", ev => { if (!arr) return; const dx = (ev.clientX - arr.x) * arr.esc, dy = (ev.clientY - arr.y) * arr.esc;
    if (arr.modo === "pj") { ed.cfg.personaje.cabeza = [Math.round(arr.cab[0] + dx), Math.round(arr.cab[1] + dy)]; } else { ed.cfg.mesa.y = Math.round(arr.mesa + dy); }
    pintarControlesSuaves(); $("ed-cx").value = ed.cfg.personaje.cabeza[0]; $("ed-cy").value = ed.cfg.personaje.cabeza[1]; vista(true); });
  window.addEventListener("mouseup", () => { if (!arr) return; arr = null; lienzo.style.cursor = ""; cambiado(false); });
  lienzo.addEventListener("wheel", ev => { if (!ed.cfg) return; ev.preventDefault(); const f = ev.shiftKey ? 0.005 : 0.02;
    ed.cfg.personaje.escala = Math.max(0.2, Math.min(2, +(ed.cfg.personaje.escala * (1 + (ev.deltaY < 0 ? f : -f))).toFixed(3))); pintarControlesSuaves(); cambiado(true); }, { passive: false });
})();

// ---------- arranque ----------
seguro(async () => { await cargarEstado(); await cargarClases(); sondear(); });

// ---------- cronómetros en vivo (etapas del render con milisegundos) ----------
const ETAPAS_VIVO = [["voz", "Voz (TTS)"], ["assets", "Cargar poses y fondo"], ["rhubarb", "Análisis de labios (Rhubarb)"],
  ["linea_de_tiempo", "Director y línea de tiempo"], ["capas", "Preparar capas"], ["render_y_encode", "Render y video"]];
const vivo = { clases: [], desfase: 0, hayEnCurso: false, timer: null };
const p2 = n => String(n).padStart(2, "0"), p3 = n => String(n).padStart(3, "0");
function fmtMs(ms) { ms = Math.max(0, Math.round(ms)); return `${p2(Math.floor(ms / 60000))}:${p2(Math.floor(ms / 1000) % 60)}.${p3(ms % 1000)}`; }
const ahoraSrv = () => Date.now() - vivo.desfase;
const ICONOS = { en_curso: "●", ok: "✓", error: "✕", pendiente: "○" };

function tarjetaVivo(c) {
  const corriendo = c.estado === "en_curso";
  const porNombre = new Map(c.etapas.map(e => [e.nombre, e]));
  const nombres = [...ETAPAS_VIVO.map(e => e[0]), ...c.etapas.map(e => e.nombre).filter(n => !ETAPAS_VIVO.some(x => x[0] === n))];
  const fin = c.fin_ms || ahoraSrv();
  const filas = [];
  for (const nombre of nombres) {
    const e = porNombre.get(nombre), etiqueta = (ETAPAS_VIVO.find(x => x[0] === nombre) || [0, nombre])[1];
    if (nombre === "voz" && !e) continue;                         // la voz solo aparece si hubo que generarla
    const est = e ? e.estado : "pendiente";
    const t = h("span", { class: "t" }, e ? fmtMs((e.fin_ms || ahoraSrv()) - e.inicio_ms) : "—");
    if (e && !e.fin_ms && corriendo) { t.dataset.ini = e.inicio_ms; }
    filas.push(h("span", { class: "ic " + est }, ICONOS[est]), h("span", { class: e ? "" : "pendiente" }, etiqueta), t);
    if (nombre === "render_y_encode" && e && c.total) {
      const seg = ((e.fin_ms || ahoraSrv()) - e.inicio_ms) / 1000, fps = seg > 0 ? c.n / seg : 0;
      filas.push(h("div", { class: "barra" }, h("i", { style: `width:${Math.round(c.fraccion * 1000) / 10}%` })),
        h("div", { class: "barra-txt" }, `${(c.fraccion * 100).toFixed(1)} % · cuadro ${c.n} de ${c.total} · ${fps.toFixed(1)} cuadros/s`));
    }
  }
  const crono = h("span", { class: "crono" }, fmtMs(fin - c.inicio_ms));
  if (corriendo) crono.dataset.ini = c.inicio_ms;
  const estadoTxt = { en_curso: "en curso", hecha: "terminada", error: "con error", sin_senal: "sin señal (¿se cerró la ventana del lote?)" }[c.estado] || c.estado;
  return h("div", { class: "vivo " + c.estado },
    h("div", { class: "cab" }, h("strong", {}, c.clase, " ", h("span", { class: "nota" }, estadoTxt)), crono),
    h("div", { class: "etapas-vivas" }, ...filas), c.error ? h("div", { class: "mal", style: "margin-top:6px" }, c.error) : "");
}

function pintarVivo() {
  const pestana = document.querySelector("#pestanas button.activa").dataset.p;
  const lista = vivo.clases.filter(c => c.estado === "en_curso").concat(vivo.clases.filter(c => c.estado !== "en_curso").slice(0, 3));
  $("envivo").hidden = !(lista.length && (pestana === "render" || pestana === "lote"));
  $("envivo-nota").textContent = vivo.hayEnCurso ? "· cronómetro con milisegundos" : "· últimas clases";
  if (!$("envivo").hidden) $("envivo-lista").replaceChildren(...lista.map(tarjetaVivo));
}
function tic() {                                                  // entre consulta y consulta, los cronómetros siguen corriendo
  const ahora = ahoraSrv();
  document.querySelectorAll("#envivo [data-ini]").forEach(e => e.textContent = fmtMs(ahora - +e.dataset.ini));
}
async function consultarVivo() {
  try {
    const d = await api("/api/progreso");
    vivo.clases = d.clases; vivo.desfase = Date.now() - d.ahora_ms; vivo.hayEnCurso = d.clases.some(c => c.estado === "en_curso");
    pintarVivo();
  } catch (e) {                                                   // sin servidor: los cronómetros seguirían corriendo solos, así que se avisa
    vivo.hayEnCurso = false;
    $("envivo-nota").textContent = "⚠ sin conexión con la interfaz: los tiempos que ves ya no son reales. ¿Se apagó? Ejecuta iniciar_todo.ps1 -Lote";
    $("envivo").hidden = false;
  }
  setTimeout(consultarVivo, vivo.hayEnCurso ? 400 : 3000);
}
setInterval(tic, 33);
consultarVivo();
document.querySelectorAll("#pestanas button").forEach(b => b.addEventListener("click", () => setTimeout(pintarVivo, 0)));
