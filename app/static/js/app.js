"use strict";

document.addEventListener("DOMContentLoaded", () => {
	const archivo = document.querySelector("#archivo");
	const nombreArchivo = document.querySelector("#file-name");
	if (archivo && nombreArchivo) {
		archivo.addEventListener("change", () => {
			nombreArchivo.textContent = archivo.files?.[0]?.name ?? "Ningún archivo seleccionado";
		});
	}

	const botonPegar = document.querySelector("[data-paste-link]");
	const campoCodigo = document.querySelector("#codigo");
	if (botonPegar && campoCodigo) {
		botonPegar.addEventListener("click", async () => {
			try {
				const texto = await navigator.clipboard.readText();
				const url = new URL(texto, window.location.origin);
				const segmentos = url.pathname.split("/").filter(Boolean);
				campoCodigo.value = segmentos.at(-1) ?? texto;
				campoCodigo.focus();
			} catch {
				campoCodigo.focus();
			}
		});
	}

	document.querySelectorAll("[data-share-link]").forEach((boton) => {
		boton.addEventListener("click", async () => {
			try {
				await navigator.clipboard.writeText(window.location.href);
				boton.textContent = "Enlace copiado";
			} catch {
				const campoTemporal = document.createElement("textarea");
				campoTemporal.value = window.location.href;
				campoTemporal.setAttribute("readonly", "");
				campoTemporal.style.position = "fixed";
				campoTemporal.style.opacity = "0";
				document.body.append(campoTemporal);
				campoTemporal.select();
				document.execCommand("copy");
				campoTemporal.remove();
				boton.textContent = "Enlace copiado";
			}
		});
	});

	document.querySelectorAll("form[data-confirm]").forEach((formulario) => {
		formulario.addEventListener("submit", (evento) => {
			if (!window.confirm(formulario.dataset.confirm)) evento.preventDefault();
		});
	});

	document.querySelectorAll("form").forEach((formulario) => {
		formulario.addEventListener("submit", () => {
			const boton = formulario.querySelector("button[type='submit'][data-loading-text]");
			if (!boton) return;
			boton.textContent = boton.dataset.loadingText;
			boton.disabled = true;
		});
	});
});
