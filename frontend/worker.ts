/**
 * Cloudflare Worker for the Blindspot AI website.
 *
 * Serves the built web app from static assets and forwards every /api/* request to the
 * Blindspot AI API on Render, so the browser only ever talks to one origin.
 */
interface Env {
  API_ORIGIN: string;
  ASSETS: { fetch: (request: Request) => Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);

    const target = new URL(url.pathname + url.search, env.API_ORIGIN);
    const headers = new Headers(request.headers);
    headers.delete("host");
    const ip = request.headers.get("cf-connecting-ip");
    if (ip) headers.set("x-forwarded-for", ip);
    headers.set("x-forwarded-proto", url.protocol.replace(":", ""));
    headers.set("x-forwarded-host", url.host);

    try {
      return await fetch(target.toString(), { method: request.method, headers, body: request.body, redirect: "manual" });
    } catch {
      // Render's free plan sleeps when idle; the first request after a pause can fail while it wakes.
      return new Response(
        JSON.stringify({ error: { code: "api_unavailable", message: "The analysis server is starting up. Please try again in about a minute." } }),
        { status: 503, headers: { "content-type": "application/json", "retry-after": "30" } },
      );
    }
  },
};
