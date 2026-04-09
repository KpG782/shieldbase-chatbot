export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { checkCredentials, makeSetCookieHeader } from "../_auth";

const SESSION_MAX_AGE = 86_400; // 24 hours

export async function POST(request: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const username = String(body.username ?? "").trim();
  const password = String(body.password ?? "");

  if (!username || !password) {
    return Response.json({ error: "Username and password are required." }, { status: 400 });
  }

  // Artificial delay to resist brute-force timing attacks.
  await new Promise<void>((resolve) => setTimeout(resolve, 150));

  if (!checkCredentials(username, password)) {
    return Response.json({ error: "Invalid username or password." }, { status: 401 });
  }

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": makeSetCookieHeader(SESSION_MAX_AGE),
    },
  });
}
