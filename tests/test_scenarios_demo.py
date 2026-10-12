"""Escenarios de sustentación reproducidos de extremo a extremo por API."""

from app.config import ADMIN_PASSWORD, ADMIN_USER
from app.services.ledger import listar_eventos


def _iniciar_sesion(cliente_api) -> None:
	"""Abre una sesión universitaria en el cliente de prueba."""
	respuesta = cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)
	assert respuesta.status_code == 200


def _datos_certificado(numero: int = 1) -> dict[str, str]:
	"""Devuelve un registro estudiantil inventado para cada escenario."""
	return {
		"estudiante_nombre": f"Estudiante Escenario {numero}",
		"estudiante_documento": f"ESC-DOC-{numero:04d}",
		"programa": "Ingeniería de Sistemas",
		"titulo": "Ingeniero de Sistemas",
		"fecha_expedicion": "2025-06-15",
	}


def _emitir(cliente_api, numero: int = 1) -> dict[str, str]:
	"""Inicia sesión y emite un certificado ficticio por la API."""
	_iniciar_sesion(cliente_api)
	respuesta = cliente_api.post("/api/certificados", json=_datos_certificado(numero))
	assert respuesta.status_code == 201
	return respuesta.json()


def test_escenario_1_emision_y_qr(cliente_api) -> None:
	"""La universidad emite y registra un certificado verificable."""
	certificado = _emitir(cliente_api)
	qr = cliente_api.get(f"/api/certificados/{certificado['id']}/qr.png")
	eventos = listar_eventos(10, certificado["id"])

	assert certificado["estado"] == "vigente"
	assert qr.status_code == 200
	assert qr.content.startswith(b"\x89PNG\r\n\x1a\n")
	assert any(evento["tipo"] == "EMISION" for evento in eventos)


def test_escenario_2_empresa_verifica_sin_sesion(cliente_api) -> None:
	"""Una empresa consulta públicamente un título auténtico y vigente."""
	certificado = _emitir(cliente_api, 2)
	cliente_api.post("/api/logout")
	resultado = cliente_api.get(f"/api/verificar/{certificado['id']}")
	eventos = listar_eventos(10, certificado["id"])

	assert resultado.status_code == 200
	assert resultado.json()["estado"] == "VALIDO"
	assert any(evento["tipo"] == "VERIFICACION" for evento in eventos)


def test_escenario_3_alteracion_de_laboratorio_y_archivo(cliente_api) -> None:
	"""La alteración del laboratorio y del JSON falla; el diff señala el nombre."""
	certificado = _emitir(cliente_api, 3)
	descarga = cliente_api.get(
		f"/api/certificados/{certificado['id']}/descarga"
	).json()
	alteracion = cliente_api.post(
		"/api/laboratorio/alterar",
		json={"certificado_id": certificado["id"], "campo": "estudiante_nombre"},
	)
	resultado_registro = cliente_api.get(f"/api/verificar/{certificado['id']}")
	documento_alterado = dict(descarga)
	documento_alterado["documento"] = dict(descarga["documento"])
	documento_alterado["documento"]["estudiante_nombre"] = "Nombre Falsificado"
	resultado_archivo = cliente_api.post(
		"/api/verificar-documento",
		json=documento_alterado,
	)
	eventos = listar_eventos(20, certificado["id"])
	restauracion = cliente_api.post(
		"/api/laboratorio/restaurar",
		json={"certificado_id": certificado["id"]},
	)

	assert alteracion.status_code == 200
	assert resultado_registro.json()["estado"] == "ALTERADO"
	assert resultado_archivo.json()["estado"] == "ALTERADO"
	assert [cambio["campo"] for cambio in resultado_archivo.json()["cambios"]] == [
		"estudiante_nombre"
	]
	assert any(evento["tipo"] == "ALTERACION_DETECTADA" for evento in eventos)
	assert restauracion.status_code == 200


def test_escenario_4_revocacion_con_firma_valida(cliente_api) -> None:
	"""La firma se conserva válida, pero la verificación informa revocación."""
	certificado = _emitir(cliente_api, 4)
	revocacion = cliente_api.post(
		f"/api/certificados/{certificado['id']}/revocar",
		json={"motivo": "Revocación ficticia para la sustentación"},
	)
	cliente_api.post("/api/logout")
	resultado = cliente_api.get(f"/api/verificar/{certificado['id']}")

	assert revocacion.status_code == 200
	assert resultado.json()["estado"] == "REVOCADO"
	assert resultado.json()["detalles"]["firma_valida"] is True


def test_cadena_valida_despues_de_los_cuatro_escenarios(cliente_api) -> None:
	"""La secuencia completa de emisión, consulta, alteración y revocación encadena."""
	certificado = _emitir(cliente_api, 5)
	cliente_api.post("/api/logout")
	assert cliente_api.get(f"/api/verificar/{certificado['id']}").json()["estado"] == "VALIDO"
	_iniciar_sesion(cliente_api)
	cliente_api.post(
		"/api/laboratorio/alterar",
		json={"certificado_id": certificado["id"], "campo": "estudiante_nombre"},
	)
	assert cliente_api.get(f"/api/verificar/{certificado['id']}").json()["estado"] == "ALTERADO"
	cliente_api.post(
		"/api/laboratorio/restaurar",
		json={"certificado_id": certificado["id"]},
	)
	cliente_api.post(
		f"/api/certificados/{certificado['id']}/revocar",
		json={"motivo": "Revocación ficticia"},
	)
	cliente_api.post("/api/logout")
	assert cliente_api.get(f"/api/verificar/{certificado['id']}").json()["estado"] == "REVOCADO"

	cadena = cliente_api.get("/api/trazabilidad/verificar-cadena")
	assert cadena.json() == {
		"valida": True,
		"total": cadena.json()["total"],
		"primer_error": None,
	}