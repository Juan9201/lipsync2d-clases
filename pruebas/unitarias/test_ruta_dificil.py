"""NFR-005: el entorno de pruebas usa rutas con espacios y acentos."""


def test_proyecto_tmp_tiene_espacios_y_acentos(proyecto_tmp):
    assert " " in proyecto_tmp.name
    assert any(ord(c) > 127 for c in proyecto_tmp.name)
    assert (proyecto_tmp / "salidas").is_dir()
    assert (proyecto_tmp / "lote" / "manifiestos").is_dir()
