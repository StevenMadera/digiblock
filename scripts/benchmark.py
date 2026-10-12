"""Benchmark reproducible de emisión, verificación y tamaños de firma."""

import math
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.database as database
from app.config import BASE_DIR
from app.crypto.keystore import KeyStore
from app.services.certificates import emitir_certificado
from app.services.laboratory import medir_comparacion_firmas
from app.services.verification import verificar_por_codigo


def _estadisticas(tiempos: list[float]) -> dict[str, float]:
	"""Calcula promedio, mediana, percentil 95 y máximo en milisegundos."""
	ordenados = sorted(tiempos)
	indice_p95 = max(0, math.ceil(len(ordenados) * 0.95) - 1)
	return {
		"promedio": mean(ordenados),
		"mediana": median(ordenados),
		"p95": ordenados[indice_p95],
		"maximo": max(ordenados),
	}


def ejecutar_benchmark(
	cantidad: int = 100,
	archivo_salida: str | Path | None = None,
) -> dict[str, Any]:
	"""Ejecuta N emisiones y verificaciones reales en SQLite temporal."""
	if not isinstance(cantidad, int) or cantidad < 1 or cantidad > 1000:
		raise ValueError("La cantidad debe estar entre 1 y 1000 operaciones.")

	ruta_informe = (
		Path(archivo_salida)
		if archivo_salida is not None
		else BASE_DIR / "docs" / "resultados_benchmark.md"
	)
	ruta_original = database.DATABASE_PATH
	tiempos_emision: list[float] = []
	tiempos_verificacion: list[float] = []

	try:
		with tempfile.TemporaryDirectory(prefix="digiblock-benchmark-") as temporal:
			directorio = Path(temporal)
			database.DATABASE_PATH = directorio / "data" / "benchmark.sqlite3"
			database.init_db()
			almacen = KeyStore(directorio / "keys")
			certificados: list[str] = []
			for numero in range(cantidad):
				datos = {
					"estudiante_nombre": f"Estudiante Benchmark {numero:04d}",
					"estudiante_documento": f"BENCH-DOC-{numero:04d}",
					"programa": "Ingeniería de Sistemas",
					"titulo": "Ingeniero de Sistemas",
					"fecha_expedicion": "2025-06-15",
				}
				inicio = perf_counter()
				certificado = emitir_certificado(datos, almacen)
				tiempos_emision.append((perf_counter() - inicio) * 1000)
				certificados.append(certificado.id)

			for certificado_id in certificados:
				inicio = perf_counter()
				resultado = verificar_por_codigo(certificado_id, almacen)
				tiempos_verificacion.append((perf_counter() - inicio) * 1000)
				if resultado.estado != "VALIDO":
					raise RuntimeError(f"Falló el benchmark para {certificado_id}.")
	finally:
		database.DATABASE_PATH = ruta_original

	comparacion = medir_comparacion_firmas()
	mediciones = {
		"emision": _estadisticas(tiempos_emision),
		"verificacion": _estadisticas(tiempos_verificacion),
		"firmas": comparacion,
	}
	informe = _crear_informe(cantidad, mediciones)
	ruta_informe.parent.mkdir(parents=True, exist_ok=True)
	ruta_informe.write_text(informe, encoding="utf-8")
	return mediciones


def _crear_informe(cantidad: int, mediciones: dict[str, Any]) -> str:
	"""Genera el informe Markdown con los valores medidos en esta ejecución."""
	fecha = datetime.now(timezone.utc).isoformat()
	lineas = [
		"# Resultados del benchmark DigiBlock",
		"",
		f"- Fecha de ejecución (UTC): `{fecha}`",
		f"- Entorno: Python `{sys.version.split()[0]}` · `{platform.platform()}`",
		f"- Muestras de emisión y verificación: **N = {cantidad}**",
		"- SQLite temporal; no se modificó la base de datos de la demostración.",
		"",
		"## Emisión y verificación ML-DSA-65",
		"",
		"| Operación | Promedio (ms) | Mediana (ms) | p95 (ms) | Máximo (ms) |",
		"|---|---:|---:|---:|---:|",
	]
	for clave, etiqueta in (("emision", "Emisión completa (firma + SQLite)"), ("verificacion", "Verificación completa (firma + SQLite)")):
		estadisticas = mediciones[clave]
		lineas.append(
			f"| {etiqueta} | {estadisticas['promedio']:.3f} | "
			f"{estadisticas['mediana']:.3f} | {estadisticas['p95']:.3f} | "
			f"{estadisticas['maximo']:.3f} |"
		)
	lineas.extend(
		[
			"",
			"## Comparación puntual de firmas",
			"",
			"Una firma y verificación por algoritmo en este equipo; no es una evaluación estadística.",
			"",
			"| Algoritmo | Clave pública (B) | Firma (B) | Firmar (ms) | Verificar (ms) |",
			"|---|---:|---:|---:|---:|",
		]
	)
	for firma in mediciones["firmas"]:
		lineas.append(
			f"| {firma['algoritmo']} | {firma['clave_publica_bytes']} | "
			f"{firma['firma_bytes']} | {firma['firma_ms']:.3f} | "
			f"{firma['verificacion_ms']:.3f} |"
		)
	lineas.extend(
		[
			"",
			"## Alcance de la medición",
			"",
			"Las operaciones ML-DSA-65 incluyen firma/verificación y persistencia en SQLite temporal. "
			"La comparación de firmas mide una operación en vivo. El resultado describe este equipo y "
			"esta ejecución; no predice rendimiento de producción.",
			"",
		]
	)
	return "\n".join(lineas)


def main() -> None:
	"""Ejecuta cien muestras y muestra la ruta del informe generado."""
	ejecutar_benchmark(100)
	print(f"Informe generado: {BASE_DIR / 'docs' / 'resultados_benchmark.md'}")


if __name__ == "__main__":
	main()
