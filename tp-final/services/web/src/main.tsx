import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/barlow-condensed/800.css";
import "@fontsource/permanent-marker/400.css";
import "./styles.css";

import Keycloak from "keycloak-js";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createApi, type Api } from "./api";
import { App } from "./App";
import { loadConfig, type RuntimeConfig } from "./config";

const root = createRoot(document.getElementById("root")!);

function render(cfg: RuntimeConfig, api: Api, username: string, onLogout: () => void) {
  root.render(
    <StrictMode>
      <App config={cfg} api={api} username={username} onLogout={onLogout} />
    </StrictMode>,
  );
}

async function start() {
  const params = new URLSearchParams(window.location.search);
  // Solo en desarrollo: ?mock=1 usa datos simulados y no pide login (para comparar diseños).
  if (import.meta.env.DEV && params.get("mock") === "1") {
    const { createMockApi } = await import("./mock/mockApi");
    const envName = params.get("env") === "dev" ? "dev" : "prod";
    render({ envName, keycloakUrl: "", realm: "", clientId: "" }, createMockApi(), "client_user", () => {});
    return;
  }
  const cfg = await loadConfig();
  const kc = new Keycloak({ url: cfg.keycloakUrl, realm: cfg.realm, clientId: cfg.clientId });
  // Login obligatorio (authorization code + PKCE). Sin iframe de sesión: la CSP no permite frames.
  await kc.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false });
  render(cfg, createApi(kc), kc.tokenParsed?.preferred_username ?? "",
         () => kc.logout({ redirectUri: window.location.origin }));
}

start().catch((err) => {
  root.render(
    <main className="fatal">
      <h1 className="sign"><img className="sign__icon" src="/logo.svg" alt="" width="64" height="60" /><span className="sign__word">Movie<span className="sign__rec">Rec</span></span></h1>
      <p>No se pudo iniciar la sesión: {String(err?.message ?? err)}.</p>
      <p>Revisá que Keycloak esté disponible y recargá la página.</p>
    </main>,
  );
});
