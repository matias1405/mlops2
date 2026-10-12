// Configuración de runtime: la escribe nginx desde variables de entorno (misma imagen en dev y prod).
export type RuntimeConfig = {
  envName: "dev" | "prod";
  keycloakUrl: string;
  realm: string;
  clientId: string;
};

export async function loadConfig(): Promise<RuntimeConfig> {
  const res = await fetch("/config.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`No se pudo leer /config.json (${res.status})`);
  return res.json();
}
