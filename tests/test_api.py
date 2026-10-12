"""Pruebas de los endpoints JSON de DigiBlock."""

from app.config import ADMIN_PASSWORD, ADMIN_USER


def _iniciar_sesion(cliente_api) -> None:
    """Autentica al usuario de demostración en el cliente de prueba."""
    respuesta = cliente_api.post(
        "/api/login",
        json={"usuario": ADMIN_USER, "contrasena": ADMIN_PASSWORD},
    )
    assert respuesta.status_code == 200


def _datos_certificado() -> dict[str, str]:
    """Devuelve datos ficticios para una emisión por API."""
    return {
        "estudiante_nombre": "Estudiante Ficticio",
        "estudiante_documento": "DOC-API-0001",
        "programa": "Ingeniería de Sistemas",
        "titulo": "Ingeniero de Sistemas",
        "fecha_expedicion": "2026-06-15",
    }


def test_endpoint_salud(cliente_api) -> None:
    """Comprueba que el endpoint de salud responde correctamente."""
    respuesta = cliente_api.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_emision_exige_sesion_y_devuelve_201(cliente_api) -> None:
    """La emisión requiere sesión universitaria y crea el certificado al entrar."""
    assert cliente_api.post("/api/certificados", json=_datos_certificado()).status_code == 401
    _iniciar_sesion(cliente_api)
    respuesta = cliente_api.post("/api/certificados", json=_datos_certificado())

    assert respuesta.status_code == 201
    assert respuesta.json()["estado"] == "vigente"


def test_verificacion_publica_no_requiere_sesion(cliente_api) -> None:
    """La consulta de verificación se mantiene pública."""
    _iniciar_sesion(cliente_api)
    emision = cliente_api.post("/api/certificados", json=_datos_certificado())
    certificado_id = emision.json()["id"]
    cliente_api.post("/api/logout")

    respuesta = cliente_api.get(f"/api/verificar/{certificado_id}")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "VALIDO"


def test_ficha_publica_omite_documento_personal(cliente_api) -> None:
    """La consulta pública no devuelve el número de documento del estudiante."""
    _iniciar_sesion(cliente_api)
    emision = cliente_api.post("/api/certificados", json=_datos_certificado())
    certificado_id = emision.json()["id"]
    cliente_api.post("/api/logout")

    respuesta = cliente_api.get(f"/api/certificados/{certificado_id}")

    assert respuesta.status_code == 200
    assert "estudiante_documento" not in respuesta.json()


def test_descarga_se_verifica_y_diff_detecta_alteracion(cliente_api) -> None:
    """La descarga vuelve a verificar y un cambio devuelve su diff exacto."""
    _iniciar_sesion(cliente_api)
    emision = cliente_api.post("/api/certificados", json=_datos_certificado())
    certificado_id = emision.json()["id"]
    descarga = cliente_api.get(f"/api/certificados/{certificado_id}/descarga").json()

    valido = cliente_api.post("/api/verificar-documento", json=descarga)
    documento_alterado = dict(descarga)
    documento_alterado["documento"] = dict(descarga["documento"])
    documento_alterado["documento"]["estudiante_nombre"] = "Nombre Modificado"
    alterado = cliente_api.post("/api/verificar-documento", json=documento_alterado)

    assert valido.status_code == 200
    assert valido.json()["estado"] == "VALIDO"
    assert alterado.status_code == 200
    assert alterado.json()["estado"] == "ALTERADO"
    assert [cambio["campo"] for cambio in alterado.json()["cambios"]] == [
        "estudiante_nombre"
    ]
    assert "no sustituye la verificación criptográfica" in alterado.json()["aviso_analisis"]


def test_certificado_revocado_no_aparece_valido(cliente_api) -> None:
    """La revocación autenticada se refleja en la verificación pública."""
    _iniciar_sesion(cliente_api)
    emision = cliente_api.post("/api/certificados", json=_datos_certificado())
    certificado_id = emision.json()["id"]
    revocacion = cliente_api.post(
        f"/api/certificados/{certificado_id}/revocar",
        json={"motivo": "Prueba ficticia de revocación"},
    )

    assert revocacion.status_code == 200
    resultado = cliente_api.get(f"/api/verificar/{certificado_id}").json()
    assert resultado["estado"] == "REVOCADO"
    assert resultado["detalles"]["firma_valida"] is True


def test_inyeccion_sql_en_path_se_trata_como_codigo_inexistente(cliente_api) -> None:
    """Una entrada SQL en la ruta no filtra ni altera registros."""
    respuesta = cliente_api.get("/api/verificar/%27%20OR%201%3D1%20--")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "NO_ENCONTRADO"