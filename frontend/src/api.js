const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok && !data.stage) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  state: () => request("/state"),
  detect: (url) => request("/detect", { method: "POST", body: JSON.stringify({ url }) }),
  fill: () => request("/fill", { method: "POST" }),
  submit: () => request("/submit", { method: "POST" }),
  reset: () => request("/reset", { method: "POST" }),
  screenshotUrl: (name) => `${BASE}/screenshot/${name}?t=${Date.now()}`,
};
