"""Pruebas de seguridad de autenticación y sesiones."""

import base64
import logging

import pytest

from app.config import ADMIN_PASSWORD, ADMIN_USER
from app.services.certificates import emitir_certificado
from app.services.auth import (
	AccesoTemporalmenteBloqueadoError,
	CredencialesInvalidasError,
	autenticar,
	limpiar_intentos,
)


@pytest.fixture(autouse=True)
def limpiar_limitador() -> None:
	"""Aísla el estado de bloqueo entre pruebas."""
	limpiar_intentos()
	yield
	limpiar_intentos()


def test_acepta_credenciales_configuradas() -> None:
	"""Las credenciales definidas por configuración permiten el acceso."""
	autenticar(ADMIN_USER, ADMIN_PASSWORD, "prueba-valida")


def test_rechaza_contrasena_incorrecta_sin_registrarla(caplog) -> None:
	"""La contraseña errónea se rechaza y no aparece en logs."""
	contrasena = "secreto-ficticio-incorrecto"
	with caplog.at_level(logging.DEBUG):
		with pytest.raises(CredencialesInvalidasError):
			autenticar(ADMIN_USER, contrasena, "prueba-invalida")

	assert contrasena not in caplog.text


def test_bloquea_tras_cinco_intentos_fallidos() -> None:
	"""El sexto intento durante el bloqueo recibe un error de espera."""
	for _ in range(5):
		with pytest.raises(CredencialesInvalidasError):
			autenticar("usuario-incorrecto", "contrasena-incorrecta", "cliente-demo")

	with pytest.raises(AccesoTemporalmenteBloqueadoError) as error:
		autenticar(ADMIN_USER, ADMIN_PASSWORD, "cliente-demo")

	assert error.value.segundos_restantes > 0


def test_cookie_de_sesion_es_http_only_y_same_site_lax(cliente_api) -> None:
	"""La cookie de sesión firmada limita su acceso desde JavaScript y otros sitios."""
	respuesta = cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)

	assert respuesta.status_code == 200
	cookie = respuesta.headers["set-cookie"].lower()
	assert "httponly" in cookie
	assert "samesite=lax" in cookie


def test_login_api_bloquea_sexto_intento(cliente_api) -> None:
	"""La API responde 401 a fallos y 429 al siguiente intento bloqueado."""
	for _ in range(5):
		respuesta = cliente_api.post(
			"/api/login",
			json={"usuario": "incorrecto", "contrasena": "incorrecta"},
		)
		assert respuesta.status_code == 401

	respuesta = cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)

	assert respuesta.status_code == 429
	assert int(respuesta.headers["retry-after"]) > 0


def test_cuerpo_json_mayor_al_limite_se_rechaza(cliente_api) -> None:
	"""El middleware limita el tamaño de cuerpos de la API."""
	respuesta = cliente_api.post(
		"/api/verificar-documento",
		content=b'{"documento":"' + b"x" * 1_000_001 + b'"}',
		headers={"content-type": "application/json"},
	)

	assert respuesta.status_code == 413


def test_entrada_con_tipo_incorrecto_devuelve_422(cliente_api) -> None:
	"""Pydantic rechaza tipos que no corresponden al contrato."""
	cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)
	datos = {
		"estudiante_nombre": "Estudiante Ficticio",
		"estudiante_documento": "DOC-API-0001",
		"programa": "Ingeniería de Sistemas",
		"titulo": "Ingeniero de Sistemas",
		"fecha_expedicion": 123,
	}

	assert cliente_api.post("/api/certificados", json=datos).status_code == 422


def test_revocacion_sin_sesion_devuelve_401(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""La ruta de revocación exige una sesión universitaria."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)

	respuesta = cliente_api.post(
		f"/api/certificados/{certificado.id}/revocar",
		json={"motivo": "Revocación de prueba"},
	)

	assert respuesta.status_code == 401


def test_laboratorio_y_reinicio_api_exigen_sesion(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""La alteración y el reinicio de demo no son accesibles como invitado."""
	certificado = emitir_certificado(datos_emision_demo, almacen_claves)
	alteracion = cliente_api.post(
		"/api/laboratorio/alterar",
		json={"certificado_id": certificado.id, "campo": "estudiante_nombre"},
	)
	reinicio = cliente_api.post("/api/demo/reiniciar")

	assert alteracion.status_code == 401
	assert reinicio.status_code == 401


def test_reinicio_api_autenticado_limpia_registros(
	cliente_api, datos_emision_demo, almacen_claves
) -> None:
	"""La universidad puede limpiar datos de demo sin borrar las claves."""
	emitir_certificado(datos_emision_demo, almacen_claves)
	cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)

	respuesta = cliente_api.post("/api/demo/reiniciar")

	assert respuesta.status_code == 200
	assert respuesta.json()["certificados_eliminados"] == 1
	assert respuesta.json()["claves_preservadas"] is True
	assert cliente_api.get("/api/certificados").json() == []


def test_nombre_con_script_se_conserva_como_dato_json(cliente_api) -> None:
	"""La API transporta texto como JSON, no como HTML ejecutable."""
	cliente_api.post(
		"/api/login",
		json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
	)
	datos = {
		"estudiante_nombre": "<script>alert(1)</script>",
		"estudiante_documento": "DOC-XSS-0001",
		"programa": "Ingeniería de Sistemas",
		"titulo": "Ingeniero de Sistemas",
		"fecha_expedicion": "2026-06-15",
	}
	respuesta = cliente_api.post("/api/certificados", json=datos)

	assert respuesta.status_code == 201
	assert respuesta.headers["content-type"].startswith("application/json")
	assert respuesta.json()["estudiante_nombre"] == "<script>alert(1)</script>"


def test_respuestas_api_no_contienen_clave_privada(
	cliente_api, ruta_claves, datos_emision_demo
) -> None:
	"""Las respuestas de rutas públicas y autenticadas nunca exponen la clave privada."""
	respuestas = [
		cliente_api.post(
			"/api/login",
			json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
		)
	]
	emision = cliente_api.post("/api/certificados", json=datos_emision_demo)
	respuestas.append(emision)
	certificado_id = emision.json()["id"]
	respuestas.extend(
		[
			cliente_api.get("/api/certificados"),
			cliente_api.get(f"/api/certificados/{certificado_id}"),
			cliente_api.get(f"/api/certificados/{certificado_id}/descarga"),
			cliente_api.get(f"/api/certificados/{certificado_id}/qr.png"),
			cliente_api.get(f"/api/verificar/{certificado_id}"),
			cliente_api.get("/api/trazabilidad"),
			cliente_api.get("/api/trazabilidad/verificar-cadena"),
			cliente_api.get("/api/clave-publica"),
			cliente_api.get("/api/estadisticas"),
			cliente_api.post(
				f"/api/certificados/{certificado_id}/revocar",
				json={"motivo": "Prueba de no exposición"},
			),
			cliente_api.post("/api/logout"),
		]
	)
	descarga = cliente_api.get(f"/api/certificados/{certificado_id}/descarga").json()
	respuestas.extend(
		[
			cliente_api.post("/api/verificar-documento", json=descarga),
			cliente_api.get("/api/certificados/DGB-2026-FFFFFF"),
			cliente_api.get("/api/verificar/DGB-2026-FFFFFF"),
			cliente_api.post(
				"/api/login",
				json={"usuario": "incorrecto", "contrasena": "incorrecta"},
			),
		]
	)
	clave_privada = (ruta_claves / "universidad_ml_dsa_65_privada.bin").read_bytes()
	marcas = (clave_privada.hex().encode("ascii"), base64.b64encode(clave_privada))

	for respuesta in respuestas:
		assert all(marca not in respuesta.content for marca in marcas)
		if respuesta.headers.get("content-type", "").startswith("application/json"):
			contenido = respuesta.json()
			for clave in _claves_json(contenido):
				assert "private" not in clave.lower()


def _claves_json(valor: object) -> list[str]:
	"""Recopila recursivamente las claves de un objeto JSON."""
	if isinstance(valor, dict):
		claves = [str(clave) for clave in valor]
		for elemento in valor.values():
			claves.extend(_claves_json(elemento))
		return claves
	if isinstance(valor, list):
		return [clave for elemento in valor for clave in _claves_json(elemento)]
	return []
