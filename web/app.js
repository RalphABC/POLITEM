const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = v => "$ " + Number(v || 0).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const S = { cortes: [], personal: [], tipos: {}, obs: [], timer: null, emitida: null };

async function api(url, opt = {}) {
  const r = await fetch(url, opt);
  if (!r.ok) {
    let d = r.statusText; try { d = (await r.json()).detail || d; } catch (e) {}
    throw new Error(d);
  }
  return r.json();
}
const post = (u, b) => api(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const leer = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };

// ---------- pestañas
$("#tabs").addEventListener("click", e => {
  const b = e.target.closest(".tab"); if (!b) return;
  $$(".tab").forEach(x => x.classList.toggle("active", x === b));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === "p-" + b.dataset.t));
  if (b.dataset.t === "historial") { cargarActas(); cargarInformes(); }
  if (b.dataset.t === "rag") cargarRag();
  if (b.dataset.t === "matriz") cargarCortes();
  if (b.dataset.t === "catalogos") cargarPersonal(true);
});

// ---------- inicio
async function iniciar() {
  S.tipos = await api("/api/tipos-observacion");
  const h = await api("/api/salud");
  $("#estado").textContent = h.ultimo_corte ? `Matriz: corte ${h.ultimo_corte.fecha} · ${h.ultimo_corte.n_validas} bienes · ${h.actas} actas` : "Sin matriz cargada";
  $("#fecha").value = new Date().toISOString().slice(0, 10);
  $("#num-aviso").textContent = `(siguiente: ${h.siguiente_numero})`;
  $("#acerca").innerHTML = ACERCA;
  await Promise.all([cargarCortes(), cargarPersonal()]);
  await llenarUbicaciones();
  await iniciarReporte();
  vista();
}

async function cargarCortes() {
  S.cortes = await api("/api/cortes");
  const sel = $("#corte");
  const actual = sel.value;
  sel.innerHTML = S.cortes.map(c => `<option value="${c.id}">${c.fecha} — ${esc(c.archivo)} (${c.n_validas} bienes)</option>`).join("");
  if (actual) sel.value = actual;
  $("#lista-cortes").innerHTML = S.cortes.length ? `<table class="lista"><tr><th>Fecha</th><th>Archivo</th><th class="n">Válidas</th><th class="n">Rechazadas</th><th></th></tr>` +
    S.cortes.map(c => `<tr><td>${c.fecha}</td><td>${esc(c.archivo)}<br><span class="badge ${c.alcance === "institucional" ? "ok" : "warn"}">${c.alcance}</span> <span class="muted small">${(c.formato || "").toUpperCase()}</span></td><td class="n">${c.n_validas}</td><td class="n">${c.n_rechazadas}</td><td><button class="lnk" data-diff="${c.id}">Ver cambios</button></td></tr>`).join("") + "</table>"
    : '<p class="muted">Aún no hay matrices.</p>';
}

async function cargarPersonal(render) {
  S.personal = await api("/api/personal");
  const op = rol => S.personal.filter(p => p.rol === rol).map(p => `<option value="${p.id}">${esc((p.titulo + " " + p.nombre).trim())} — ${esc(p.cargo)}</option>`).join("");
  const a = $("#analista"), c = $("#coord"), va = a.value, vc = c.value;
  a.innerHTML = op("analista"); c.innerHTML = op("coordinador");
  a.value = va || leer("analista") || a.value; c.value = vc || leer("coord") || c.value;
  if (render !== false) {
    $("#lista-personal").innerHTML = `<table class="lista"><tr><th>Rol</th><th>Nombre</th><th>Cargo</th><th></th></tr>` + S.personal.map(p =>
      `<tr><td>${p.rol === "analista" ? "Analista" : "Coordinación"}</td><td>${esc((p.titulo + " " + p.nombre).trim())}</td><td>${esc(p.cargo)}</td><td><button class="lnk" data-del="${p.id}">Quitar</button></td></tr>`).join("") + "</table>";
  }
}
$("#p-add").onclick = async () => {
  try {
    await post("/api/personal", { rol: $("#p-rol").value, titulo: $("#p-titulo").value, nombre: $("#p-nombre").value, cargo: $("#p-cargo").value });
    $("#p-nombre").value = ""; await cargarPersonal(true);
  } catch (e) { alert(e.message); }
};
$("#lista-personal").onclick = async e => {
  const b = e.target.closest("[data-del]"); if (!b) return;
  await api("/api/personal/" + b.dataset.del, { method: "DELETE" }); cargarPersonal(true);
};

// ---------- selección de ubicación / custodio
const modo = () => $("input[name=modo]:checked").value;
async function llenarUbicaciones() {
  const cid = $("#corte").value; if (!cid) return;
  const u = await api(`/api/cortes/${cid}/ubicaciones`);
  const prev = $("#ubicacion").value;
  $("#ubicacion").innerHTML = u.map(x => `<option value="${esc(x.ubicacion)}">${esc(x.ubicacion)} (${x.n} ítems)</option>`).join("");
  if (prev) $("#ubicacion").value = prev;
  await llenarCustodios();
}
async function llenarCustodios() {
  const cid = $("#corte").value, ub = $("#ubicacion").value; if (!cid || !ub) return;
  const c = await api(`/api/cortes/${cid}/ubicaciones/custodios?ubicacion=${encodeURIComponent(ub)}`);
  $("#custodio").innerHTML = `<option value="">Todos los custodios (${c.reduce((s, x) => s + x.n, 0)} ítems)</option>` +
    c.map(x => `<option value="${esc(x.custodio_nombre)}">${esc(x.custodio_nombre)} (${x.n})</option>`).join("");
  $("#r-nombre").value = c[0] ? c[0].custodio_nombre : "";
  S.custodios = c;
}
$("#corte").onchange = async () => { await llenarUbicaciones(); vista(); };
$("#ubicacion").onchange = async () => { await llenarCustodios(); vista(); };
$("#custodio").onchange = () => { if ($("#custodio").value) $("#r-nombre").value = $("#custodio").value; vista(); };
$$("input[name=modo]").forEach(r => r.onchange = () => {
  const m = modo() === "matriz";
  $("#bloque-matriz").classList.toggle("hidden", !m); $("#bloque-manual").classList.toggle("hidden", m); $("#bloque-valores").classList.toggle("hidden", !m);
  vista();
});
$("#chk-manual").onchange = () => { $("#vals-manual").classList.toggle("hidden", !$("#chk-manual").checked); vista(); };

// ---------- novedades
function pintarObs() {
  $("#obs").innerHTML = S.obs.map((o, i) => `<div class="obs" data-i="${i}"><button class="x" data-x="${i}" title="Quitar">✕</button>
    <div class="r"><select data-k="tipo">${Object.entries(S.tipos).map(([k, v]) => `<option value="${k}" ${o.tipo === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
    <input data-k="codigo" list="dl-bienes" placeholder="Código (ESP-…)" value="${esc(o.codigo)}"></div>
    <div class="r" style="margin-top:8px"><input data-k="detalle" placeholder="Lugar / detalle" value="${esc(o.detalle)}"><input data-k="nota" placeholder="Nota del analista" value="${esc(o.nota)}"></div>
    ${o.orient ? `<div class="or"><b>Orientación (revisar):</b> ${esc(o.orient)}</div>` : ""}</div>`).join("") + '<datalist id="dl-bienes"></datalist>';
}
$("#add-obs").onclick = () => { S.obs.push({ tipo: "faltante", codigo: "", detalle: "", nota: "" }); pintarObs(); orientar(S.obs.length - 1); };
$("#obs").addEventListener("click", e => { const x = e.target.closest("[data-x]"); if (x) { S.obs.splice(+x.dataset.x, 1); pintarObs(); vista(); } });
$("#obs").addEventListener("input", async e => {
  const f = e.target.closest("[data-k]"); if (!f) return;
  const i = +f.closest(".obs").dataset.i; S.obs[i][f.dataset.k] = f.value;
  if (f.dataset.k === "codigo" && f.value.length >= 3 && modo() === "matriz") {
    const r = await api(`/api/bienes/buscar?cid=${$("#corte").value}&q=${encodeURIComponent(f.value)}&ubicacion=${encodeURIComponent($("#ubicacion").value)}`);
    $("#dl-bienes").innerHTML = r.map(b => `<option value="${esc(b.codigo)}">${esc(b.descripcion)}</option>`).join("");
  }
  vista();
});
$("#obs").addEventListener("change", async e => { if (e.target.dataset.k === "tipo") { const i = +e.target.closest(".obs").dataset.i; S.obs[i].tipo = e.target.value; await orientar(i); } });
async function orientar(i) {
  try { const r = await post("/api/observaciones/orientar", { tipo: S.obs[i].tipo }); S.obs[i].orient = r[0] ? `${r[0].titulo}: ${r[0].texto.slice(0, 170)}…` : ""; } catch (e) {}
  pintarObs(); vista();
}

// ---------- carga útil, vista previa y emisión
function payload() {
  const p = {
    modo: modo(), fecha: $("#fecha").value, analista_id: +$("#analista").value || null, coordinador_id: +$("#coord").value || null,
    responsable_titulo: $("#r-titulo").value, responsable_nombre: $("#r-nombre").value, secuencia: $("#secuencia").value || null,
    observaciones: S.obs.filter(o => o.codigo || o.detalle || o.nota || o.tipo === "sobrante" || o.tipo === "otro"), incluir_normativa: $("#chk-norm").checked,
  };
  if (p.modo === "matriz") {
    Object.assign(p, { corte_id: +$("#corte").value, ubicacion: $("#ubicacion").value, custodio_nombre: $("#custodio").value });
    if ($("#chk-manual").checked) { p.valor_total_manual = $("#v-valor").value; p.dep_acum_manual = $("#v-dep").value; }
  } else Object.assign(p, { ubicacion: $("#m-ubic").value, items: $("#m-items").value, valor_total: $("#m-valor").value, dep_acum: $("#m-dep").value });
  return p;
}
["#fecha", "#secuencia", "#analista", "#coord", "#r-titulo", "#r-nombre", "#m-ubic", "#m-items", "#m-valor", "#m-dep", "#v-valor", "#v-dep", "#chk-norm"].forEach(s =>
  $(s).addEventListener("input", () => { $("#resultado").classList.add("hidden"); if (s === "#analista") guardar("analista", $(s).value); if (s === "#coord") guardar("coord", $(s).value); vista(); }));

function vista() { clearTimeout(S.timer); S.timer = setTimeout(pintarVista, 250); }
async function pintarVista() {
  try {
    const e = await post("/api/actas/previa", payload());
    S.previa = e; $("#preview").innerHTML = hoja(e);
    $("#avisos").innerHTML = e.advertencias.length ? '<div class="avisos">' + e.advertencias.map(a => `<div class="a">⚠ ${esc(a)}</div>`).join("") + "</div>" : "";
    $("#msg").classList.add("hidden"); $("#emitir").disabled = false;
  } catch (err) { $("#preview").innerHTML = `<p class="muted">${esc(err.message)}</p>`; $("#avisos").innerHTML = ""; $("#emitir").disabled = true; }
}
function hoja(e) {
  const f = e.firmas;
  return `<img src="/static/logo_espoch.png" alt="ESPOCH"><h3>${esc(e.titulo)}</h3><h3>ACTA N. ° ${esc(e.numero)}</h3><br>
  <p>${esc(e.apertura)}</p>
  <table>${e.tabla.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join("")}</table>
  <p>${esc(e.adjunto)}</p>
  ${e.novedades.length ? `<p><b>Novedades constatadas:</b></p><ol>${e.novedades.map(n => `<li>${esc(n)}</li>`).join("")}</ol>` : ""}
  ${e.normativa.length ? `<p><b>Base normativa de referencia:</b></p>${e.normativa.map(n => `<div class="norm"><b>${esc(n.titulo)}.</b> ${esc(n.texto)}</div>`).join("")}` : ""}
  <p>${esc(e.cierre)}</p>
  <div class="firmas"><b>${esc(f.custodio.nombre)}</b><br>${f.custodio.cargo}
  <div class="dos"><div><b>${esc(f.analista.nombre)}</b><br>${esc(f.analista.cargo)}</div><div><b>${esc(f.coordinador.nombre)}</b><br>${esc(f.coordinador.cargo)}</div></div></div>`;
}
$("#emitir").onclick = async () => {
  try {
    const e = await post("/api/actas", payload());
    $("#resultado").classList.remove("hidden");
    $("#resultado").innerHTML = `<b>Acta N.° ${esc(e.numero)} emitida.</b> <a class="lnk" href="/api/actas/${e.id}/docx">Descargar Word</a>` +
      (e.meta.modo === "matriz" ? `<a class="lnk" href="/api/actas/${e.id}/anexo">Descargar anexo (Excel)</a>` : "");
    S.obs = []; pintarObs(); $("#secuencia").value = "";
    const h = await api("/api/salud"); $("#num-aviso").textContent = `(siguiente: ${h.siguiente_numero})`; vista();
  } catch (err) { const m = $("#msg"); m.className = "msg err"; m.textContent = err.message; }
};
$("#borrador").onclick = async () => {
  try {
    const r = await fetch("/api/actas/previa/docx", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    if (!r.ok) throw new Error((await r.json()).detail);
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = "Borrador_acta.docx"; a.click();
  } catch (err) { const m = $("#msg"); m.className = "msg err"; m.textContent = err.message; }
};

// ---------- actas emitidas
async function cargarActas() {
  const a = await api("/api/actas");
  $("#lista-actas").innerHTML = a.length ? `<table class="lista"><tr><th>N.°</th><th>Fecha</th><th>Ubicación</th><th>Origen</th><th class="n">Ítems</th><th class="n">Valor total</th><th class="n">Dep. acum.</th><th>Estado</th><th></th></tr>` +
    a.map(x => `<tr><td><b>${x.numero}</b></td><td>${x.fecha}</td><td>${esc(x.ubicacion)}</td><td>${x.modo}${x.valor_manual ? " · valores manuales" : ""}</td><td class="n">${x.items}</td><td class="n">${money(x.valor_total)}</td><td class="n">${money(x.dep_acum)}</td>
    <td><span class="badge ${x.estado === "emitida" ? "ok" : "bad"}">${x.estado}</span></td><td><a class="lnk" href="/api/actas/${x.id}/docx">Word</a>${x.modo === "matriz" ? `<a class="lnk" href="/api/actas/${x.id}/anexo">Excel</a>` : ""}${x.estado === "emitida" ? `<button class="lnk" data-an="${x.id}">Anular</button>` : ""}</td></tr>`).join("") + "</table>"
    : '<p class="muted">Todavía no se emitió ningún acta.</p>';
}
$("#lista-actas").onclick = async e => { const b = e.target.closest("[data-an]"); if (b && confirm("¿Anular esta acta?")) { await post(`/api/actas/${b.dataset.an}/anular`, {}); cargarActas(); } };

// ---------- matriz mensual
$("#subir").onclick = async () => {
  const f = $("#arch").files[0]; if (!f) { alert("Seleccione un archivo."); return; }
  const fd = new FormData(); fd.append("archivo", f); fd.append("alcance", $("input[name=alc]:checked").value); if ($("#f-corte").value) fd.append("fecha", $("#f-corte").value);
  $("#res-carga").innerHTML = '<p class="muted">Cargando…</p>';
  try {
    const r = await api("/api/cortes", { method: "POST", body: fd });
    const c = r.carga;
    $("#res-carga").innerHTML = `<div class="msg okm">Corte ${c.fecha}: ${c.n_validas} de ${c.n_filas} filas válidas.</div>` +
      (c.rechazos.length ? `<details><summary>${c.rechazos.length} filas rechazadas</summary>${c.rechazos.slice(0, 30).map(x => `<div class="small">Fila ${x.fila}: ${esc(x.motivo)} ${esc(x.codigo)}</div>`).join("")}</details>` : "") +
      (c.advertencias.length ? `<details open><summary>Avisos</summary>${c.advertencias.slice(0, 5).map(a => `<div class="small">⚠ ${esc(a)}</div>`).join("")}</details>` : "") + (c.sin_mapear.length ? `<details><summary>${c.sin_mapear.length} columnas sin usar</summary><div class="small">${c.sin_mapear.map(esc).join(", ")}</div></details>` : "");
    await cargarCortes(); await llenarUbicaciones(); await iniciarReporte(); iniciarEstado(); if (r.diferencias) pintarDiff(r.diferencias);
  } catch (e) { $("#res-carga").innerHTML = `<div class="msg err">${esc(e.message)}</div>`; }
};
async function iniciarEstado() { const h = await api("/api/salud"); $("#estado").textContent = `Matriz: corte ${h.ultimo_corte.fecha} · ${h.ultimo_corte.n_validas} bienes · ${h.actas} actas`; }
$("#lista-cortes").onclick = async e => {
  const b = e.target.closest("[data-diff]"); if (!b) return;
  try { pintarDiff(await api(`/api/cortes/${b.dataset.diff}/diferencias`)); } catch (err) { $("#diff").innerHTML = `<p class="muted">${esc(err.message)}</p>`; }
};
function pintarDiff(d) {
  const lista = (t, arr, f) => arr.length ? `<details><summary>${t} (${arr.length})</summary><table class="lista">${arr.slice(0, 40).map(f).join("")}</table></details>` : "";
  $("#diff").innerHTML = `<p class="muted small">Corte ${d.corte} comparado con el corte ${d.contra}.</p><div class="kpis">
  <div class="kpi"><b>${d.altas.length}</b><span>Altas (ingresos)</span></div><div class="kpi"><b>${d.bajas.length}</b><span>Bajas / salidas</span></div>
  <div class="kpi"><b>${d.traspasos.length}</b><span>Traspasos de custodio</span></div><div class="kpi"><b>${d.reubicaciones.length}</b><span>Cambios de ubicación</span></div>
  <div class="kpi"><b>${d.cambios_estado.length}</b><span>Cambios de estado</span></div><div class="kpi"><b>${d.dep_actualizada}</b><span>Con depreciación actualizada</span></div></div>` +
    lista("Altas", d.altas, x => `<tr><td>${x.codigo}</td><td>${esc(x.descripcion)}</td><td>${esc(x.ubicacion)}</td><td>${esc(x.custodio)}</td></tr>`) +
    lista("Bajas", d.bajas, x => `<tr><td>${x.codigo}</td><td>${esc(x.descripcion)}</td><td>${esc(x.ubicacion)}</td><td>${esc(x.custodio)}</td></tr>`) +
    lista("Traspasos", d.traspasos, x => `<tr><td>${x.codigo}</td><td>${esc(x.descripcion)}</td><td>${esc(x.de)} → ${esc(x.a)}</td></tr>`) +
    lista("Cambios de ubicación", d.reubicaciones, x => `<tr><td>${x.codigo}</td><td>${esc(x.descripcion)}</td><td>${esc(x.de)} → ${esc(x.a)}</td></tr>`) +
    lista("Cambios de estado", d.cambios_estado, x => `<tr><td>${x.codigo}</td><td>${esc(x.descripcion)}</td><td>${esc(x.de)} → ${esc(x.a)}</td></tr>`);
}

const ACERCA = `<h2>Qué integra este prototipo</h2>
<p>Reúne lo que pidió el tutor y lo que pidió la Unidad de Bienes y Bodegas, con <b>RAG obligatorio</b>:</p>
<table><tr><th>Necesidad</th><th>Dónde está</th></tr>
<tr><td>Entrada: documento de eSByE por cédula, en PDF o CSV (tutor)</td><td>«Carga de datos» acepta CSV, Excel y PDF con texto; «Reporte inteligente» busca por cédula.</td></tr>
<tr><td>Reporte totalizado de activos con RAG (tutor)</td><td>«Reporte inteligente»: cifras calculadas por el sistema + redacción con recuperación, citas y validación.</td></tr>
<tr><td>Carga, segmentación, incrustaciones y base vectorial (tutor)</td><td>Pestaña «Sistema RAG»: fragmentos por bien y por norma, embeddings y ChromaDB.</td></tr>
<tr><td>Acta de constatación por defecto con un clic (Unidad de Bienes)</td><td>«Acta de constatación»: texto fijo, firmas y matriz adjunta en Excel.</td></tr>
<tr><td>Matriz que cambia cada mes (Unidad de Bienes)</td><td>«Carga de datos»: cortes mensuales con comparación (altas, bajas, traspasos).</td></tr>
<tr><td>Observaciones del analista</td><td>En el acta: novedades redactadas y orientación normativa recuperada con el mismo RAG.</td></tr></table>
<h2>Qué no hace</h2><p>No se conecta a eSByE, no firma electrónicamente, no tiene inicio de sesión institucional y no lee PDF escaneados. Los datos son ficticios y la normativa es un resumen de apoyo. Ver el PDF de alcance y requerimientos.</p>`;

// ---------- Reporte inteligente (RAG)
const amb = () => $("input[name=amb]:checked").value;
async function iniciarReporte() {
  const cs = S.cortes; if (!cs.length) return;
  $("#r-corte").innerHTML = '<option value="">Automático (el más reciente)</option>' + cs.map(c => `<option value="${c.id}">${c.fecha} — ${esc(c.archivo)} (${c.alcance})</option>`).join("");
  const ult = cs.find(c => c.alcance === "institucional") || cs[0];
  const f = await api(`/api/cortes/${ult.id}/funcionarios`); S.func = f;
  $("#dl-func").innerHTML = f.map(x => `<option value="${esc(x.cedula)}">${esc(x.nombre)} — ${x.n} bienes</option>`).join("");
  const u = await api(`/api/cortes/${ult.id}/ubicaciones`); S.ubr = ult.id;
  const pv = $("#r-ubic").value;
  $("#r-ubic").innerHTML = u.map(x => `<option value="${esc(x.ubicacion)}">${esc(x.ubicacion)} (${x.n})</option>`).join(""); if (pv) $("#r-ubic").value = pv;
  await custodiosReporte();
}
async function custodiosReporte() {
  if (!S.ubr || !$("#r-ubic").value) return;
  const c = await api(`/api/cortes/${S.ubr}/ubicaciones/custodios?ubicacion=${encodeURIComponent($("#r-ubic").value)}`);
  $("#r-cust").innerHTML = '<option value="">Todos los custodios</option>' + c.map(x => `<option value="${esc(x.custodio_nombre)}">${esc(x.custodio_nombre)} (${x.n})</option>`).join("");
}
$("#r-ubic").onchange = custodiosReporte;
$$("input[name=amb]").forEach(r => r.onchange = () => { $("#amb-cedula").classList.toggle("hidden", amb() !== "cedula"); $("#amb-ubic").classList.toggle("hidden", amb() !== "ubicacion"); });
$("#r-tipo").onchange = () => $("#r-preg-box").classList.toggle("hidden", $("#r-tipo").value !== "consulta_libre");
$("#r-cedula").addEventListener("input", () => {
  const f = (S.func || []).find(x => x.cedula === $("#r-cedula").value.trim() || x.nombre.toLowerCase() === $("#r-cedula").value.trim().toLowerCase());
  if (f && f.nombre.toLowerCase() === $("#r-cedula").value.trim().toLowerCase()) $("#r-cedula").value = f.cedula;
  $("#r-cedula-info").textContent = f ? `${f.nombre} · ${f.n} bienes · ${money(f.valor)}` : "";
});
$("#r-gen").onclick = async () => {
  const m = $("#r-msg"); m.classList.add("hidden");
  const ambito = amb() === "cedula" ? { tipo: "cedula", valor: $("#r-cedula").value.trim() } : { tipo: "ubicacion", valor: $("#r-ubic").value, custodio: $("#r-cust").value };
  $("#r-gen").disabled = true; $("#r-gen").textContent = "Generando…";
  try {
    const r = await post("/api/informes", { ambito, tipo: $("#r-tipo").value, pregunta: $("#r-preg").value, corte_id: $("#r-corte").value ? +$("#r-corte").value : null });
    pintarReporte(r);
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
  $("#r-gen").disabled = false; $("#r-gen").textContent = "Generar reporte";
};
function md(t, codigos) {
  const inline = x => esc(x).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>")
    .replace(/\[([^\[\]\s]{3,40})\]/g, (m, c) => /\d/.test(c) ? `<button class="chip" data-cod="${c}">${c}</button>` : m);
  let o = "", lista = null;
  const cerrar = () => { if (lista) { o += `</${lista}>`; lista = null; } };
  for (const ln0 of t.split("\n")) {
    const ln = ln0.trimEnd();
    if (!ln) { cerrar(); continue; }
    let m;
    if ((m = ln.match(/^#{2,3}\s+(.*)/))) { cerrar(); o += `<h3>${inline(m[1])}</h3>`; }
    else if ((m = ln.match(/^-\s+(.*)/))) { if (lista !== "ul") { cerrar(); o += "<ul>"; lista = "ul"; } o += `<li>${inline(m[1])}</li>`; }
    else if ((m = ln.match(/^\d+\.\s+(.*)/))) { if (lista !== "ol") { cerrar(); o += "<ol>"; lista = "ol"; } o += `<li>${inline(m[1])}</li>`; }
    else { cerrar(); o += `<p>${inline(ln)}</p>`; }
  }
  cerrar(); return o;
}
function pintarReporte(r) {
  $("#r-vacio").classList.add("hidden"); $("#r-out").classList.remove("hidden");
  $("#r-titulo").textContent = r.titulo; $("#r-sub").textContent = `${r.etiqueta} · corte ${r.fecha_corte}`;
  const t = r.totales;
  $("#r-kpis").innerHTML = [["Bienes", t.total], ["Valor contable", money(t.valor_contable)], ["Dep. acumulada", money(t.dep_acum)], ["Valor en libros", money(t.valor_libros)], ["Críticos", t.n_criticos], ["Totalmente deprec.", t.totalmente_depreciados]]
    .map(k => `<div class="kpi"><b>${k[1]}</b><span>${k[0]}</span></div>`).join("");
  $("#r-texto").innerHTML = md(r.texto);
  const v = r.validacion, cl = v.estado === "APROBADO" ? "ok" : v.estado === "RECHAZADO" ? "bad" : "warn";
  $("#r-badge").innerHTML = `<span class="badge ${cl}">Validación: ${v.estado}</span>`;
  $("#r-val").innerHTML = `<b>${v.citas_validas}/${v.citas_total}</b> citas verificadas · ${esc(v.mensajes.join(" "))}`;
  $("#r-docx").href = `/api/informes/${r.id}/docx`;
  $("#r-evid").innerHTML = r.evidencias.slice(0, 40).map(e => `<div class="ev" id="ev-${esc(e.codigo)}"><b>${esc(e.codigo)}</b> <span class="muted small">relevancia ${(e.score * 100).toFixed(0)}% (similitud ${(e.componentes.semantica * 100).toFixed(0)}% · regla ${(e.componentes.regla * 100).toFixed(0)}%)</span><div>${esc(e.texto)}</div></div>`).join("") +
    (r.normas.length ? "<h3>Criterios normativos recuperados</h3>" + r.normas.map(n => `<div class="ev norma"><b>${esc(n.titulo)}</b> <span class="muted small">similitud ${(n.sim * 100).toFixed(0)}%</span><div>${esc(n.texto)}</div></div>`).join("") : "");
  const z = r.traza;
  $("#r-traza").innerHTML = `<table class="lista"><tr><td>Generación</td><td>${esc(z.proveedor)} (${esc(z.modelo)})${z.respaldo_plantilla ? ' <span class="badge warn">respaldo</span>' : ""}</td></tr>
   <tr><td>Embeddings</td><td>${esc(z.embeddings)}</td></tr><tr><td>Base vectorial</td><td>${esc(z.base_vectorial)}</td></tr>
   <tr><td>Recuperación</td><td>${z.candidatos} candidatos → ${z.en_contexto} en el contexto (universo: ${z.universo} bienes) · ${z.t_recuperacion_ms} ms</td></tr>
   <tr><td>Generación y validación</td><td>${z.intentos} intento(s) · ${z.t_generacion_ms} ms</td></tr>${z.aviso ? `<tr><td>Aviso</td><td>${esc(z.aviso)}</td></tr>` : ""}</table>`;
}
$("#r-out").addEventListener("click", e => {
  const c = e.target.closest(".chip"); if (!c) return;
  const ev = document.getElementById("ev-" + c.dataset.cod); if (!ev) return;
  ev.scrollIntoView({ behavior: "smooth", block: "center" }); ev.classList.add("flash"); setTimeout(() => ev.classList.remove("flash"), 1600);
});

// ---------- Historial de reportes y estado del RAG
async function cargarInformes() {
  const a = await api("/api/informes");
  $("#lista-informes").innerHTML = a.length ? `<table class="lista"><tr><th>N.°</th><th>Fecha</th><th>Tipo</th><th>Ámbito</th><th></th></tr>` +
    a.map(x => `<tr><td>${x.id}</td><td>${esc(x.creado)}</td><td>${esc(x.tipo)}</td><td>${esc(x.etiqueta)}${x.pregunta ? "<br><i class='small'>" + esc(x.pregunta) + "</i>" : ""}</td><td><a class="lnk" href="/api/informes/${x.id}/docx">Word</a></td></tr>`).join("") + "</table>"
    : '<p class="muted">Todavía no se generó ningún reporte.</p>';
}
async function cargarRag() {
  const [e, ] = await Promise.all([api("/api/rag/estado")]);
  $("#rag-pipeline").innerHTML = `<div class="pipe">${["1 · Carga<br><small>CSV · Excel · PDF</small>", "2 · Segmentación<br><small>un fragmento por bien y por norma</small>", "3 · Incrustaciones<br><small>" + esc(e.embeddings) + "</small>",
    "4 · Base vectorial<br><small>" + esc(e.base_vectorial) + "</small>", "5 · Recuperación híbrida<br><small>filtro + similitud + reglas</small>", "6 · Generación<br><small>" + esc(e.generacion.modelo) + "</small>", "7 · Validación<br><small>citas y cifras</small>"]
    .map(x => `<div class="paso">${x}</div>`).join('<span class="flecha">→</span>')}</div>`;
  $("#rag-estado").innerHTML = `<table class="lista"><tr><td>Base vectorial</td><td>${esc(e.base_vectorial)}</td></tr><tr><td>Embeddings</td><td>${esc(e.embeddings)} · ${e.dimension} dim. · ${e.semantico ? "semánticos" : "léxicos (n-gramas)"}</td></tr>
   <tr><td>Fragmentos de normativa</td><td>${e.fragmentos_normativa}</td></tr>` + e.cortes.map(c => `<tr><td>Corte ${c.fecha} (${c.alcance})</td><td>${c.indexados} / ${c.bienes} bienes indexados ${c.indexados === c.bienes ? "✔" : "⚠"}</td></tr>`).join("") + "</table>" +
   (e.semantico ? "" : '<p class="muted small">Embeddings léxicos: encuentran palabras parecidas. Para similitud por significado active <code>EMBEDDING_PROVIDER=ollama</code> (ver README).</p>');
  const g = e.generacion;
  $("#rag-llm").innerHTML = `<p><span class="badge ${g.disponible ? "ok" : "bad"}">${g.disponible ? "disponible" : "no disponible"}</span> <b>${esc(g.proveedor)}</b> · ${esc(g.modelo)}</p><p class="muted small">${esc(g.detalle || (g.proveedor === "plantilla" ? "Modo plantilla: redacción determinista sin modelo. Cambie LLM_PROVIDER en .env para usar un modelo." : ""))}</p>`;
}
$("#rag-reindex").onclick = async () => { $("#rag-reindex").disabled = true; await post("/api/rag/reindexar", {}); await cargarRag(); $("#rag-reindex").disabled = false; };
iniciar().catch(e => { document.body.insertAdjacentHTML("afterbegin", `<div class="msg err">${esc(e.message)}</div>`); });
