import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// PWA: solo en la web publicada (no en desarrollo ni dentro del APK de Capacitor)
const esCapacitor = (window as unknown as { Capacitor?: unknown }).Capacitor !== undefined;
if (import.meta.env.PROD && "serviceWorker" in navigator && !esCapacitor) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => { /* sin PWA, la app igual funciona */ });
  });
}
