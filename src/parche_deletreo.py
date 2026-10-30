"""Cambia, en un video ya terminado (con subtítulos), solo el audio de las letras deletreadas por la versión en inglés.
No renderiza ni subtitula de nuevo: video y subtítulos quedan intactos, la duración no cambia.
Uso:  python src/parche_deletreo.py <video.mp4> <salida.mp4> <parches.json>
parches.json = [{"antes": "letras consecutivas como", "letras": "X, Y, Z", "despues": "marcará la diferencia"}, ...]  (en orden de aparición)
"""
import json, sys, subprocess, difflib, unicodedata, re, tempfile, urllib.request
from pathlib import Path
import numpy as np

VOZ = "http://127.0.0.1:5055"
ESTILO = ("Habla con acento colombiano natural (de Bogotá), cálido, claro y pausado, como un profesor amable. "
          "Cuando aparezcan letras sueltas deletreadas, como C A R L O S, pronuncia cada letra con su nombre en inglés "
          "(sii, éi, ar, el, ou, es), nunca en español. Las frases en inglés se leen con pronunciación inglesa.")
SR = 44100


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def leer_wav(ruta):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def palabras(modelo, audio, idioma="es"):
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-ar", "16000", str(wav)],
                       input=audio.tobytes(), check=True)
        seg, _ = modelo.transcribe(str(wav), language=idioma, word_timestamps=True, vad_filter=False)
        return [(w.start, w.end, norm(w.word)) for s in seg for w in s.words if norm(w.word)]


def buscar(pal, frase, desde=0):
    """Índice de la primera palabra de `frase` (lista de palabras normalizadas) a partir de `desde`; None si no está."""
    n, mejor = len(frase), (0.0, None)
    for i in range(desde, len(pal) - n + 1):
        r = sum(difflib.SequenceMatcher(None, a[2], b).ratio() for a, b in zip(pal[i:i + n], frase)) / n
        if r > mejor[0]:
            mejor = (r, i)
    return mejor[1] if mejor[0] >= 0.8 else None


def sintetizar(texto):
    cuerpo = {"text": texto, "voice": "es-419-podcaster-3", "language": "es-419", "style": ESTILO,
              "temperature": 1.0, "speed": "normal", "pitch": "normal"}
    req = urllib.request.Request(VOZ + "/api/generate-tts", json.dumps(cuerpo).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    mp3 = urllib.request.urlopen(VOZ + "/api/audio/" + r["file"]).read()
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.mp3"; p.write_bytes(mp3)
        return leer_wav(p)


def sin_pausas_largas(seg, min_s=0.15, deja_s=0.07, umbral_db=-42):
    """Acorta las pausas entre letras (las del inglés salen más espaciadas que las del hueco original)."""
    v = 20 * np.log10(np.convolve(np.abs(seg), np.ones(220) / 220, "same") + 1e-9)
    callado, partes, i, n = v < umbral_db, [], 0, len(seg)
    while i < n:
        j = i
        while j < n and callado[j] == callado[i]:
            j += 1
        trozo = seg[i:j]
        partes.append(trozo[:int(deja_s * SR)] if callado[i] and (j - i) > min_s * SR and 0 < i else trozo)
        i = j
    return np.concatenate(partes)


def ajustar(seg, largo, tope=1.3):
    """Estira o comprime `seg` (hasta 0,8–`tope`×) para que mida `largo` muestras; lo que sobre se recorta, lo que falte es silencio."""
    seg = sin_pausas_largas(seg)
    r = min(tope, max(0.8, len(seg) / max(largo, 1)))
    print(f"    ajuste: audio {len(seg)/SR:.2f} s -> hueco {largo/SR:.2f} s (velocidad x{r:.2f})")
    if abs(r - 1) > 0.01:
        out = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", f"atempo={r}", "-f", "f32le", "-"],
                             input=seg.tobytes(), capture_output=True, check=True).stdout
        seg = np.frombuffer(out, dtype=np.float32)
    return np.pad(seg, (0, max(0, largo - len(seg))))[:largo]


def rms(x):
    return float(np.sqrt(np.mean(x ** 2) + 1e-12))


def parchear(audio, parches, modelo, log=print):
    pal = palabras(modelo, audio)
    cursor, huecos = 0, []
    for p in parches:
        a, d = [norm(w) for w in p["antes"].split()], [norm(w) for w in p["despues"].split()]
        ia = buscar(pal, a, cursor)
        id_ = buscar(pal, d, (ia or cursor) + len(a)) if ia is not None else None
        if ia is None or id_ is None or id_ - (ia + len(a)) > 14:
            raise SystemExit(f"No encontré «{p['antes']} … {p['despues']}» en el audio (ni sin ambigüedad)")
        t0, t1 = pal[ia + len(a) - 1][1], pal[id_][0]
        nuevo = sintetizar(f"{p['antes']} {p['letras']} {p['despues']}")
        pn = palabras(modelo, nuevo)
        ja = buscar(pn, a); jd = buscar(pn, d, (ja or 0) + len(a)) if ja is not None else None
        if ja is None or jd is None:
            raise SystemExit(f"No encontré el contexto en el audio nuevo de «{p['letras']}»")
        n0, n1 = pn[ja + len(a) - 1][1], pn[jd][0]
        huecos.append((int(t0 * SR), int(t1 * SR), nuevo[int(n0 * SR):int(n1 * SR)], p["letras"], t0, t1, n1 - n0))
        log(f"  {p['letras']!r}: hueco {t0:.2f}-{t1:.2f} s ({t1 - t0:.2f}), audio nuevo {n1 - n0:.2f} s")
        cursor = id_
    salida, pos = [], 0
    for i0, i1, seg, letras, *_ in huecos:
        if len(sin_pausas_largas(seg)) / max(i1 - i0, 1) > 1.3:                       # no cabe sin acelerar demasiado: se deja el original
            print(f"    SE OMITE {letras!r}: en inglés dura {len(sin_pausas_largas(seg))/SR:.2f} s y el hueco solo {(i1-i0)/SR:.2f} s")
            continue
        seg = ajustar(seg, i1 - i0)
        seg = seg * min(2.0, rms(audio[max(0, i0 - SR):i1 + SR]) / rms(seg))        # igualar volumen con lo de alrededor
        f = int(0.012 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        salida += [audio[pos:i0], seg]; pos = i1
    salida.append(audio[pos:])
    out = np.concatenate(salida)
    assert len(out) == len(audio)
    return out


if __name__ == "__main__":
    video, destino, parches = sys.argv[1:4]
    from faster_whisper import WhisperModel
    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    audio = leer_wav(video)
    nuevo = parchear(audio, json.loads(Path(parches).read_text(encoding="utf-8")), modelo)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "n.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(wav)], input=nuevo.tobytes(), check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "173k", "-movflags", "+faststart", destino], check=True)
    print("listo:", destino)
