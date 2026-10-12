"""Pruebas de idempotencia, reset y escritura del informe de benchmark."""

from pathlib import Path

import app.database as database
from app.services.certificates import listar_certificados
from app.services.ledger import verificar_cadena
from scripts.benchmark import ejecutar_benchmark
from scripts.reset_demo import reiniciar_demo
from scripts.seed_demo import sembrar_demo


def test_seed_es_idempotente(ruta_base_datos: Path, almacen_claves) -> None:
	"""La segunda ejecución no añade certificados ni eventos de verificación."""
	primero = sembrar_demo(almacen_claves)
	segundo = sembrar_demo(almacen_claves)

	assert primero == {"creados": 5, "ya_existian": 0, "verificaciones_creadas": 3}
	assert segundo == {"creados": 0, "ya_existian": 5, "verificaciones_creadas": 0}
	assert len(listar_certificados()) == 5
	assert verificar_cadena()["valida"] is True


def test_reset_borra_db_y_claves_y_vuelve_a_sembrar(
	ruta_base_datos: Path,
	ruta_claves: Path,
	almacen_claves,
) -> None:
	"""El reset sustituye la base y genera un nuevo par local para la demo."""
	sembrar_demo(almacen_claves)
	privada_anterior = (ruta_claves / "universidad_ml_dsa_65_privada.bin").read_bytes()

	resultado = reiniciar_demo(ruta_claves)
	privada_nueva = (ruta_claves / "universidad_ml_dsa_65_privada.bin").read_bytes()

	assert resultado["creados"] == 5
	assert len(listar_certificados()) == 5
	assert privada_nueva != privada_anterior
	assert verificar_cadena()["valida"] is True
	assert database.DATABASE_PATH == ruta_base_datos


def test_benchmark_escribe_estadisticas_en_markdown(tmp_path: Path) -> None:
	"""Una ejecución pequeña valida las cuatro estadísticas y la salida Markdown."""
	informe = tmp_path / "resultados_benchmark.md"
	resultado = ejecutar_benchmark(2, informe)
	contenido = informe.read_text(encoding="utf-8")

	assert set(resultado["emision"]) == {"promedio", "mediana", "p95", "maximo"}
	assert set(resultado["verificacion"]) == {"promedio", "mediana", "p95", "maximo"}
	assert len(resultado["firmas"]) == 2
	assert "ML-DSA-65" in contenido
	assert "Ed25519" in contenido