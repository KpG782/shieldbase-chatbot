export const dynamic = "force-dynamic";
export const runtime = "nodejs";

import { isValidSession } from "../_auth";

export async function GET(request: Request) {
  const cookieHeader = request.headers.get("cookie");
  const authenticated = isValidSession(cookieHeader);
  return Response.json({ authenticated });
}
