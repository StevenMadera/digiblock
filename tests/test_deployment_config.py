"""Pruebas de configuración de despliegue y cookie de producción."""

import pytest
from fastapi.testclient import TestClient

import app.config as config
import app.main as main
import app.services.auth as auth
from app.services.auth import limpiar_intentos


def test_produccion_rechaza_secret_key_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
	"""La app no se construye en producción sin SECRET_KEY."""
	monkeypatch.setattr(config, "APP_ENV", "produccion")
	monkeypatch.setattr(config, "SECRET_KEY", None)
	monkeypatch.setattr(config, "ADMIN_PASSWORD", "password-seguro-de-prueba")

	with pytest.raises(RuntimeError, match="SECRET_KEY"):
		main.crear_app()


def test_produccion_rechaza_admin_password_ausente(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""La app no se construye en producción sin ADMIN_PASSWORD."""
	monkeypatch.setattr(config, "APP_ENV", "produccion")
	monkeypatch.setattr(config, "SECRET_KEY", "clave-segura-de-prueba")
	monkeypatch.setattr(config, "ADMIN_PASSWORD", None)

	with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
		main.crear_app()


def test_cookie_de_produccion_es_secure_httponly_y_lax(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Login sobre HTTPS firma cookie Secure, HttpOnly y SameSite=Lax."""
	monkeypatch.setattr(config, "APP_ENV", "produccion")
	monkeypatch.setattr(config, "SECRET_KEY", "clave-segura-de-prueba")
	monkeypatch.setattr(config, "ADMIN_USER", "universidad")
	monkeypatch.setattr(config, "ADMIN_PASSWORD", "contrasena-segura-de-prueba")
	monkeypatch.setattr(auth, "ADMIN_PASSWORD", "contrasena-segura-de-prueba")
	monkeypatch.setattr(main, "inicializar_entorno", lambda: {})
	limpiar_intentos()
	aplicacion = main.crear_app()

	with TestClient(aplicacion, base_url="https://testserver") as cliente:
		respuesta = cliente.post(
			"/api/login",
			json={"usuario": "universidad", "contrasena": "contrasena-segura-de-prueba"},
		)

	assert respuesta.status_code == 200
	cookie = respuesta.headers["set-cookie"].lower()
	assert "secure" in cookie
	assert "httponly" in cookie
	assert "samesite=lax" in cookie
	limpiar_intentos()