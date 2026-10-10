import { createApp } from "vue";
import { createPinia } from "pinia";
import { createVuetify } from "vuetify";
import { es } from "vuetify/locale";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";
import "vuetify/styles";
import "./estilos.css";
import Aplicacion from "./Aplicacion.vue";

const vuetify = createVuetify({
  locale: { locale: "es", messages: { es } },
  icons: { defaultSet: "mdi", aliases, sets: { mdi } },
  theme: {
    cspNonce: document.querySelector('meta[name="csp-nonce"]')?.content,
    defaultTheme: "institucional",
    themes: {
      institucional: {
        dark: false,
        colors: {
          primary: "#17645f",
          secondary: "#18374c",
          background: "#f3f6f8",
          surface: "#ffffff",
          error: "#ae2633",
          success: "#17645f",
          "on-surface": "#24384a",
        },
      },
    },
  },
  defaults: {
    VBtn: { rounded: "lg", elevation: 0 },
    VCard: { rounded: "lg", elevation: 0, border: true },
    VTextField: {
      variant: "outlined",
      density: "compact",
      hideDetails: "auto",
    },
    VSelect: { variant: "outlined", density: "compact", hideDetails: "auto" },
    VFileInput: {
      variant: "outlined",
      density: "compact",
      hideDetails: "auto",
    },
    VAlert: { density: "compact", variant: "tonal", rounded: "lg" },
  },
});

createApp(Aplicacion).use(createPinia()).use(vuetify).mount("#app");
