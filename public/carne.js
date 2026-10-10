import { PATRON_UUID } from "./validaciones.js";
const $ = (selector) => document.querySelector(selector);
const uuid = new URLSearchParams(location.search).get("uuid");
try {
  if (!PATRON_UUID.test(uuid || ""))
    throw new Error("Identificador de carné no válido.");
  const respuesta = await fetch(`/api/carnes/${uuid}`, {
    credentials: "same-origin",
  });
  const persona = await respuesta.json();
  if (!respuesta.ok) throw new Error(persona.mensaje);
  $("#card-name").textContent = `${persona.nombres} ${persona.apellidos}`;
  const longitudNombre = $("#card-name").textContent.length;
  $("#card-name").classList.toggle("nombre-largo", longitudNombre > 60);
  $("#card-name").classList.toggle("nombre-extenso", longitudNombre > 100);
  $("#card-uuid").textContent = persona.uuid;
  $("#card-status").textContent = persona.activo
    ? "Registro activo"
    : "Registro inactivo";
  $("#card-foto").src = persona.foto;
  $("#card-qr").src = persona.qr;
  await Promise.all([$("#card-foto").decode(), $("#card-qr").decode()]);
  $("#credential-card").hidden = false;
  $("#card-message").hidden = true;
  $("#print-card").disabled = false;
} catch (error) {
  $("#card-message").textContent =
    error.message === "Failed to fetch"
      ? "No se pudo conectar con el sistema."
      : error.message;
}
$("#print-card").addEventListener("click", () => window.print());
