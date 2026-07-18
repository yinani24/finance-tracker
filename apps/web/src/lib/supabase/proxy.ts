import { NextResponse, type NextRequest } from "next/server";

// Single-user app: no auth gate. Pass every request through untouched.
// (Previously redirected unauthenticated requests to /login.)
export async function updateSession(request: NextRequest) {
  return NextResponse.next({ request });
}
