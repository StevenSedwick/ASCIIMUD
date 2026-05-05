export { ChannelRoom } from "./channel_room";

export interface Env {
  CHANNEL_ROOM: DurableObjectNamespace;
  SECRETS: KVNamespace;
  TWITCH_EXT_SECRETS: string;
}

const json = (data: unknown, init?: ResponseInit): Response =>
  new Response(JSON.stringify(data), {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);

    if (request.method === "GET" && parts.length === 1 && parts[0] === "healthz") {
      return json({ ok: true });
    }

    if (
      parts.length === 2 &&
      (parts[0] === "ingest" || parts[0] === "ws" ||
       parts[0] === "state"  || parts[0] === "map"  ||
       parts[0] === "interface" || parts[0] === "spells")
    ) {
      const channelId = parts[1];
      if (!/^[A-Za-z0-9_-]+$/.test(channelId)) {
        return json({ error: "invalid channelId" }, { status: 400 });
      }
      const id = env.CHANNEL_ROOM.idFromName(channelId);
      const stub = env.CHANNEL_ROOM.get(id);

      const inner = new URL(request.url);
      inner.pathname = `/${parts[0]}`;
      inner.searchParams.set("channelId", channelId);

      return stub.fetch(new Request(inner.toString(), request));
    }

    return json({ error: "not found" }, { status: 404 });
  },
} satisfies ExportedHandler<Env>;
