"""Pruebas de rendimiento con umbrales explícitos para el prototipo."""

from statistics import mean
from time import perf_counter

from app.services.certificates import emitir_certificado
from app.services.verification import verificar_por_codigo


def test_verificacion_promedio_menor_a_un_segundo(
	datos_emision_demo, ruta_base_datos, almacen_claves
) -> None:
	"""La media de cinco verificaciones debe quedar bajo un segundo."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	tiempos: list[float] = []
	for _ in range(5):
		inicio = perf_counter()
		resultado = verificar_por_codigo(certificado.id, almacen_claves)
		tiempos.append(perf_counter() - inicio)
		assert resultado.estado == "VALIDO"

	assert mean(tiempos) < 1.0


def test_cincuenta_verificaciones_no_se_degradan_de_forma_notable(
	datos_emision_demo, ruta_base_datos, almacen_claves
) -> None:
	"""La mitad final no supera ampliamente la mitad inicial ni un segundo."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	tiempos: list[float] = []
	for _ in range(50):
		inicio = perf_counter()
		resultado = verificar_por_codigo(certificado.id, almacen_claves)
		tiempos.append(perf_counter() - inicio)
		assert resultado.estado == "VALIDO"

	promedio_inicial = mean(tiempos[:25])
	promedio_final = mean(tiempos[25:])
	umbral_sin_degradacion = max(promedio_inicial * 3, promedio_inicial + 0.1)
	assert promedio_final < 1.0
	assert promedio_final <= umbral_sin_degradacion


def test_emision_promedio_bajo_un_segundo(
	datos_emision_demo, ruta_base_datos, almacen_claves
) -> None:
	"""La media de cinco emisiones ML-DSA-65 debe quedar bajo un segundo."""
	tiempos: list[float] = []
	for numero in range(5):
		datos = dict(
			datos_emision_demo,
			estudiante_documento=f"PERF-DOC-{numero:04d}",
		)
		inicio = perf_counter()
		certificado = emitir_certificado(datos, almacen_claves)
		tiempos.append(perf_counter() - inicio)
		assert certificado.firma_hex

	assert mean(tiempos) < 1.0