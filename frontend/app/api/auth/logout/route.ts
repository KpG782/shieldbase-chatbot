export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { makeClearCookieHeader } from "../_auth";

export async function POST() {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": makeClearCookieHeader(),
    },
  });
}
