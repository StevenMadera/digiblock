"""Pruebas de páginas renderizadas y controles del laboratorio."""

from pathlib import Path

import app.database as database
from app.config import ADMIN_PASSWORD, ADMIN_USER
from app.services.certificates import emitir_certificado, revocar_certificado


def _iniciar_sesion(cliente_api) -> None:
	"""Inicia una sesión web con credenciales configuradas."""
	respuesta = cliente_api.post(
		"/login",
		data={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD, "next": "/"},
		follow_redirects=False,
	)
	assert respuesta.status_code == 303


def test_paginas_publicas_responden(cliente_api) -> None:
	"""Las páginas públicas renderizan correctamente."""
	for ruta in ("/", "/login", "/verificar", "/trazabilidad", "/acerca"):
		respuesta = cliente_api.get(ruta)
		assert respuesta.status_code == 200, ruta


def test_paginas_protegidas_redirigen_a_login(cliente_api) -> None:
	"""Emisión y laboratorio requieren una sesión universitaria."""
	for ruta in ("/emitir", "/laboratorio"):
		respuesta = cliente_api.get(ruta, follow_redirects=False)
		assert respuesta.status_code == 303
		assert respuesta.headers["location"].startswith("/login")


def test_login_habilita_emision_y_laboratorio(cliente_api) -> None:
	"""Una sesión permite acceder a las páginas universitarias."""
	_iniciar_sesion(cliente_api)
	assert cliente_api.get("/emitir").status_code == 200
	assert cliente_api.get("/laboratorio").status_code == 200


def test_nombre_de_usuario_se_escapa_en_html(cliente_api) -> None:
	"""Un nombre con etiquetas script se presenta como texto, no como HTML."""
	_iniciar_sesion(cliente_api)
	respuesta = cliente_api.post(
		"/emitir",
		data={
			"estudiante_nombre": "<script>alert(1)</script>",
			"estudiante_documento": "DOC-XSS-0002",
			"programa": "Ingeniería de Sistemas",
			"titulo": "Ingeniero de Sistemas",
			"fecha_expedicion": "2026-06-15",
		},
	)
	assert respuesta.status_code == 200
	assert "&lt;script&gt;alert(1)&lt;/script&gt;" in respuesta.text
	assert "<script>alert(1)</script>" not in respuesta.text


def test_resultado_web_muestra_los_cuatro_estados(
	cliente_api,
	datos_emision_demo,
	ruta_base_datos: Path,
	almacen_claves,
) -> None:
	"""La página de verificación presenta los estados definidos por el servicio."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	valido = cliente_api.get(f"/verificar/{certificado.id}")
	assert "VALIDO" in valido.text

	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET estudiante_nombre = ? WHERE id = ?",
			("Nombre Alterado", certificado.id),
		)
	alterado = cliente_api.get(f"/verificar/{certificado.id}")
	assert "ALTERADO" in alterado.text

	with database.conectar(ruta_base_datos) as conexion:
		conexion.execute(
			"UPDATE certificados SET estudiante_nombre = ? WHERE id = ?",
			(certificado.estudiante_nombre, certificado.id),
		)
	revocar_certificado(certificado.id, "Revocación ficticia")
	revocado = cliente_api.get(f"/verificar/{certificado.id}")
	no_encontrado = cliente_api.get("/verificar/DGB-2026-FFFFFF")
	assert "REVOCADO" in revocado.text
	assert "NO_ENCONTRADO" in no_encontrado.text


def test_vista_certificado_inexistente_usa_error_404(cliente_api) -> None:
	"""El error 404 usa la plantilla propia en vez de la página técnica."""
	respuesta = cliente_api.get("/certificado/DGB-2026-FFFFFF")
	assert respuesta.status_code == 404
	assert "No encontramos esa página" in respuesta.text


def test_vista_estudiante_ofrece_descarga_y_compartir(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""La ficha pública ofrece descarga JSON y un control de compartir enlace."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	respuesta = cliente_api.get(f"/certificado/{certificado.id}")

	assert respuesta.status_code == 200
	assert "Descargar JSON" in respuesta.text
	assert "Compartir enlace" in respuesta.text


def test_lab_simula_y_restaurar_alteracion(cliente_api, datos_emision_demo, almacen_claves) -> None:
	"""La operación protegida altera y restaura un certificado de prueba."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	_iniciar_sesion(cliente_api)
	alteracion = cliente_api.post(
		"/laboratorio/alterar",
		data={"certificado_id": certificado.id, "campo": "estudiante_nombre"},
		follow_redirects=False,
	)
	resultado_alterado = cliente_api.get(f"/verificar/{certificado.id}")
	restauracion = cliente_api.post(
		"/laboratorio/restaurar",
		data={"certificado_id": certificado.id},
		follow_redirects=False,
	)
	resultado_restaurado = cliente_api.get(f"/verificar/{certificado.id}")
	assert alteracion.status_code == 303
	assert "ALTERADO" in resultado_alterado.text
	assert restauracion.status_code == 303
	assert "VALIDO" in resultado_restaurado.text


def test_lab_revocar_certificado_y_mostrar_estado(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""El formulario revoca con sesión y la verificación posterior informa REVOCADO."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	_iniciar_sesion(cliente_api)
	respuesta = cliente_api.post(
		"/laboratorio/revocar",
		data={
			"certificado_id": certificado.id,
			"motivo": "Revocación ficticia desde la interfaz",
			"confirmacion": "REVOCAR",
		},
		follow_redirects=False,
	)
	verificacion = cliente_api.get(f"/verificar/{certificado.id}")
	laboratorio = cliente_api.get("/laboratorio")

	assert respuesta.status_code == 303
	assert "REVOCADO" in verificacion.text
	assert "Revocar certificado" in laboratorio.text


def test_revocacion_web_requiere_confirmacion(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""La ruta no revoca si falta la confirmación explícita del formulario."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	_iniciar_sesion(cliente_api)
	respuesta = cliente_api.post(
		"/laboratorio/revocar",
		data={"certificado_id": certificado.id, "motivo": "Motivo ficticio"},
	)

	assert respuesta.status_code == 200
	assert "Confirma la revocación" in respuesta.text
	assert "VALIDO" in cliente_api.get(f"/verificar/{certificado.id}").text