"""CLI de lotes: crear -> encolar -> estado -> reintentar, con rutas temporales."""
from src.lote.__main__ import main
from src.lote.cola import Cola


def _clases(proyecto, n=3):
    for i in range(1, n + 1):
        (proyecto / "clases" / f"clase_{i:04d}.txt").write_text(f"Guion {i}.", encoding="utf-8")
        (proyecto / "clases" / f"clase_{i:04d}.mp3").write_bytes(b"x")


def test_flujo_crear_encolar_estado_reintentar(proyecto_tmp, capsys):
    _clases(proyecto_tmp)
    db = proyecto_tmp / "lote" / "cola.db"
    csv_ruta = proyecto_tmp / "lote" / "manifiestos" / "L.csv"
    base = ["--db", str(db), "--raiz", str(proyecto_tmp)]
    assert main(["crear", "--carpeta", str(proyecto_tmp / "clases"), "--personaje", "profe", "--lote", "L",
                 "--salida", str(csv_ruta), *base]) == 0
    assert "3 clases" in capsys.readouterr().out
    assert main(["encolar", str(csv_ruta), *base]) == 0
    assert "3 trabajos encolados" in capsys.readouterr().out
    assert main(["encolar", str(csv_ruta), *base]) == 0                      # repetir no duplica
    assert "3 ya estaban" in capsys.readouterr().out
    assert main(["estado", "--lote", "L", *base]) == 0
    assert "3 pendientes" in capsys.readouterr().out
    cola = Cola(db)
    cola.fallar(cola.reclamar().id, "falló")
    assert main(["reintentar", *base]) == 0
    assert "1 clases vuelven a la cola" in capsys.readouterr().out


def test_un_manifiesto_con_errores_se_informa_en_espanol(proyecto_tmp, capsys):
    ruta = proyecto_tmp / "lote" / "manifiestos" / "malo.csv"
    ruta.write_text("id,guion,audio,personaje,escenarios,poses,resolucion,semilla,tts,lote\n"
                    "a,,,profe,,,1280x720,,,L\n", encoding="utf-8")
    codigo = main(["encolar", str(ruta), "--db", str(proyecto_tmp / "lote" / "cola.db"), "--raiz", str(proyecto_tmp)])
    err = capsys.readouterr().err
    assert codigo == 1 and "ERROR" in err and "fila 2" in err and "Qué hacer" in err


def test_avisa_de_guiones_sin_audio_y_audios_sin_guion(proyecto_tmp, capsys):
    (proyecto_tmp / "clases" / "solo_guion.txt").write_text("hola", encoding="utf-8")
    (proyecto_tmp / "clases" / "solo_audio.mp3").write_bytes(b"x")
    main(["crear", "--carpeta", str(proyecto_tmp / "clases"), "--lote", "L",
          "--salida", str(proyecto_tmp / "lote" / "manifiestos" / "L.csv"),
          "--db", str(proyecto_tmp / "lote" / "cola.db"), "--raiz", str(proyecto_tmp)])
    salida = capsys.readouterr().out
    assert "guiones sin audio" in salida and "solo_guion" in salida
    assert "audios sin guion" in salida and "solo_audio" in salida
