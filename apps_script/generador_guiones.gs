// =========================================================================
// GENERADOR DE GUIONES POR LOTES - un .txt por clase en Drive/Guiones/<nivel>/
// =========================================================================
// Uso (en script.google.com, proyecto del Script Maestro):
//   1. Configuración del proyecto -> Propiedades del script -> añade GEMINI_API_KEY = tu clave NUEVA.
//      (La clave NO va en el código: este archivo está en un repo público.)
//   2. Ejecuta estado() para ver cuántas clases hay hechas y pendientes.
//   3. Ejecuta iniciar(). Trabaja solo: 5 clases por minuto, A1 -> A2 -> B1 -> B2, y se reanuda si se corta.
//   4. detener() lo para. Volver a ejecutar iniciar() continúa donde quedó: NO duplica ni rehace lo ya generado.
// Para rehacer una clase concreta, borra su .txt de Drive y ejecuta iniciar().
// =========================================================================

var SPREADSHEET_ID = '10Pz0RQ3h2P3dR2eQMIGu0i0elPZ9A_VzCcSAyt_xLbI';
var MODELO = 'gemini-3.1-pro-preview';
var CARPETA_RAIZ = 'Guiones';              // dentro de Mi unidad
var NIVELES = ['A1', 'A2', 'B1', 'B2'];
var LOTE = 5;                              // clases por ejecución
var MIN_PAL = 720, MAX_PAL = 880;          // palabras habladas aceptables (objetivo 800 = ~5 min)
var MAX_INTENTOS = 3;
var ESPERA_NORMAL_MS = 60 * 1000;
var ESPERA_ERROR_MS = 5 * 60 * 1000;

// ------------------------------------------------------------------ arranque
function iniciar() {
  borrarTriggers_();
  PropertiesService.getScriptProperties().deleteProperty('ERRORES');
  tick();
}

function detener() {
  borrarTriggers_();
  Logger.log('Detenido. Ejecuta iniciar() para continuar.');
}

function estado() {
  var props = PropertiesService.getScriptProperties();
  var abandonadas = JSON.parse(props.getProperty('ERRORES') || '[]');
  NIVELES.forEach(function (n) {
    var filas = filasDe_(n);
    var hechas = hechasDe_(n);
    var hechasN = filas.filter(function (f) { return hechas[f.id]; }).length;
    Logger.log(n + ': ' + hechasN + ' de ' + filas.length + ' hechas, ' + (filas.length - hechasN) + ' pendientes');
  });
  Logger.log('Abandonadas tras ' + MAX_INTENTOS + ' intentos: ' + (abandonadas.length ? abandonadas.join(', ') : 'ninguna'));
}

// ------------------------------------------------------------------ ciclo
function tick() {
  var cerrojo = LockService.getScriptLock();
  if (!cerrojo.tryLock(30000)) { return; }
  var espera = ESPERA_NORMAL_MS;
  try {
    borrarTriggers_();
    var props = PropertiesService.getScriptProperties();
    var abandonadas = JSON.parse(props.getProperty('ERRORES') || '[]');
    var pendientes = null;
    for (var k = 0; k < NIVELES.length && !pendientes; k++) {
      var nivel = NIVELES[k];
      var hechas = hechasDe_(nivel);
      var lista = filasDe_(nivel).filter(function (f) { return !hechas[f.id] && abandonadas.indexOf(f.id) < 0; });
      if (lista.length) { pendientes = { nivel: nivel, lista: lista }; }
    }
    if (!pendientes) {
      Logger.log('PROCESO COMPLETADO. Abandonadas: ' + (abandonadas.length ? abandonadas.join(', ') : 'ninguna'));
      return;
    }
    var lote = pendientes.lista.slice(0, LOTE);
    var carpeta = carpetaDe_(pendientes.nivel);
    var url = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODELO + ':generateContent';
    var cabeceras = { 'x-goog-api-key': clave_() };
    var peticiones = lote.map(function (f) {
      return {
        url: url, method: 'post', contentType: 'application/json', headers: cabeceras, muteHttpExceptions: true,
        payload: JSON.stringify({
          contents: [{ parts: [{ text: prompt_(pendientes.nivel, f) }] }]
        })
      };
    });
    var respuestas = UrlFetchApp.fetchAll(peticiones);
    for (var j = 0; j < respuestas.length; j++) {
      var f = lote[j];
      var codigo = respuestas[j].getResponseCode();
      var texto = '', motivo = '';
      if (codigo === 200) {
        try {
          var json = JSON.parse(respuestas[j].getContentText());
          var partes = (json.candidates && json.candidates[0] && json.candidates[0].content.parts) || [];
          texto = partes.map(function (p) { return p.text || ''; }).join('').trim();
          motivo = (json.candidates && json.candidates[0] && json.candidates[0].finishReason) || '?';
        } catch (e) { texto = ''; }
      } else if (codigo === 429 || codigo >= 500) {
        espera = ESPERA_ERROR_MS;
      }
      var intentos = (parseInt(props.getProperty('INT_' + f.id), 10) || 0) + 1;
      var palabras = contarPalabras_(texto);
      var buena = texto && palabras >= MIN_PAL && palabras <= MAX_PAL;
      if (buena || (texto && intentos >= MAX_INTENTOS)) {
        guardar_(carpeta, f, texto, !buena, palabras);
        props.deleteProperty('INT_' + f.id);
      } else if (intentos >= MAX_INTENTOS) {
        abandonadas.push(f.id);
        props.setProperty('ERRORES', JSON.stringify(abandonadas));
        Logger.log('ABANDONADA ' + f.id + ' (HTTP ' + codigo + ')');
      } else {
        props.setProperty('INT_' + f.id, String(intentos));
        Logger.log('Reintento ' + f.id + ' (HTTP ' + codigo + ', ' + palabras + ' palabras, fin: ' + motivo + ', intento ' + intentos + ')');
      }
    }
    ScriptApp.newTrigger('tick').timeBased().after(espera).create();
  } finally {
    cerrojo.releaseLock();
  }
}

// ------------------------------------------------------------------ hoja y Drive
// Cada fila: {id: 'A1-M02-3', modulo, subtema, descripcion, ejemplo, ia: true|false}.
// La 1.ª clase de cada módulo es HUMANA (se genera igual, queda marcada); las otras 3 son de IA.
function filasDe_(nivel) {
  var hoja = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName('Subtemas_' + nivel);
  if (!hoja) { throw new Error('No existe la pestaña Subtemas_' + nivel); }
  var datos = hoja.getDataRange().getValues();
  var filas = [], posicion = {};
  for (var i = 1; i < datos.length; i++) {
    var modulo = String(datos[i][0]).trim(), subtema = String(datos[i][1]).trim();
    if (!subtema) { continue; }
    var m = modulo.match(/(\d+)/);
    var num = m ? ('0' + m[1]).slice(-2) : '00';
    posicion[modulo] = (posicion[modulo] || 0) + 1;
    filas.push({
      id: nivel + '-M' + num + '-' + posicion[modulo], modulo: modulo, subtema: subtema,
      descripcion: String(datos[i][2]), ejemplo: String(datos[i][3]), ia: posicion[modulo] > 1
    });
  }
  return filas;
}

function carpetaDe_(nivel) {
  var raices = DriveApp.getFoldersByName(CARPETA_RAIZ);
  var raiz = raices.hasNext() ? raices.next() : DriveApp.createFolder(CARPETA_RAIZ);
  var subs = raiz.getFoldersByName(nivel);
  return subs.hasNext() ? subs.next() : raiz.createFolder(nivel);
}

// Qué clases ya tienen su archivo: por el identificador que abre el nombre (A1-M02-3 ...).
function hechasDe_(nivel) {
  var hechas = {};
  var it = carpetaDe_(nivel).getFiles();
  while (it.hasNext()) { hechas[it.next().getName().split(' ')[0]] = true; }
  return hechas;
}

function guardar_(carpeta, f, texto, revisar, palabras) {
  var nombre = f.id + (f.ia ? ' IA' : ' HUMANO') + ' - ' + f.modulo.replace(/^M.dulo \d+:\s*/, '') + ' - ' + f.subtema;
  nombre = nombre.replace(/[:\\\/*?|"<>]/g, '').substring(0, 140).trim();
  if (revisar) { nombre += ' (REVISAR ' + palabras + ' pal)'; }
  carpeta.createFile(nombre + '.txt', texto, MimeType.PLAIN_TEXT);   // solo el guion: sin cabeceras que la voz leería
}

// ------------------------------------------------------------------ texto
function contarPalabras_(texto) {
  var limpio = texto.replace(/^-{5,}$/gm, '').replace(/^(The Definition and Purpose|The Spanish Equivalent|Breaking the Rules and Verb Tenses|Application in Past, Present, and Future|Contexts and Examples of Use|Precautions for Listening and Speaking)$/gm, '');
  var p = limpio.split(/\s+/).filter(function (w) { return w.length; });
  return p.length;
}

var TITULOS = '\n-------------------------------------------------\nThe Definition and Purpose\n-------------------------------------------------\n[Text]\n\n' +
  '-------------------------------------------------\nThe Spanish Equivalent\n-------------------------------------------------\n[Text]\n\n' +
  '-------------------------------------------------\nBreaking the Rules and Verb Tenses\n-------------------------------------------------\n[Text]\n\n' +
  '-------------------------------------------------\nApplication in Past, Present, and Future\n-------------------------------------------------\n[Text]\n\n' +
  '-------------------------------------------------\nContexts and Examples of Use\n-------------------------------------------------\n[Text]\n\n' +
  '-------------------------------------------------\nPrecautions for Listening and Speaking\n-------------------------------------------------\n[Text]';

function prompt_(nivel, f) {
  if (nivel === 'A1' || nivel === 'A2') {
    return 'Actúa como un profesor experto de inglés. Escribe un guion de estudio sobre el subtema gramatical: "' + f.subtema + '" (Contexto: ' + f.modulo + ').\n' +
      'Definición/Descripción: ' + f.descripcion + '.\nCaso de uso a incluir: ' + f.ejemplo + '.\n\n' +
      'REGLAS CRÍTICAS DE FORMATO Y LENGUAJE:\n' +
      '1. CONDICIÓN DE IDIOMA ESTRICTA: Toda la explicación, teoría y narrativa DEBEN ESTAR EN ESPAÑOL. Sin embargo, cuando menciones palabras, oraciones o ejemplos en inglés, DÉJALOS ESTRICTAMENTE EN INGLÉS (Nivel ' + nivel + ').\n' +
      '2. LONGITUD: El guion DEBE tener 800 palabras (entre 760 y 840), sin contar los títulos de sección, para 5 minutos de lectura en voz alta. Cuenta antes de responder.\n' +
      '3. SIN ACOTACIONES: NO incluyas direcciones de escena, [SCENE START], **TEACHER**, ni acciones entre paréntesis.\n' +
      '4. SIN MARKDOWN: NO uses # ni asteriscos para los títulos.\n' +
      '5. SECCIONES OBLIGATORIAS: DEBES usar EXACTAMENTE los siguientes bloques literales en inglés para separar tus secciones. Cópialos y pégalos exactamente así, aunque tu explicación debajo esté en español:\n' + TITULOS;
  }
  return 'Act as an expert English Teacher. Write a comprehensive study script about the grammar subtopic: "' + f.subtema + '" (Context: ' + f.modulo + ').\n' +
    'Definition/Description: ' + f.descripcion + '.\nUse case context to include: ' + f.ejemplo + '.\n\n' +
    'CRITICAL FORMATTING RULES:\n' +
    '1. LANGUAGE CONDITION: The ENTIRE script must be written in English. English level: ' + nivel + ' strictly.\n' +
    '2. LENGTH: The script MUST be 800 words long (between 760 and 840), not counting the section titles, to take 5 minutes to read aloud. Count before answering.\n' +
    '3. NO STAGE DIRECTIONS: DO NOT include [SCENE START], **TEACHER**, or actions in parentheses.\n' +
    '4. NO MARKDOWN: DO NOT use # or asterisks for titles.\n' +
    '5. MANDATORY SECTIONS: YOU MUST use the EXACT literal text blocks below to separate your sections. Copy and paste them exactly as they appear here:\n' + TITULOS;
}

// ------------------------------------------------------------------ utilidades
function clave_() {
  var k = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!k) { throw new Error('Falta GEMINI_API_KEY en Configuración del proyecto -> Propiedades del script'); }
  return k;
}

function borrarTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'tick') { ScriptApp.deleteTrigger(t); }
  });
}
