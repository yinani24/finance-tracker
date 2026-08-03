"use client";

import { createBrowserClient } from "@supabase/ssr";

/**
 * A Supabase browser client, or null when none is configured.
 *
 * Sign-in was removed — statements are parsed in the tab and nothing is stored
 * server-side — so these environment variables are optional. They were read
 * with `!`, which is a lie the type system believes: on a deployment without
 * them, `createBrowserClient(undefined, undefined)` throws during the very
 * first render of the root layout and takes the whole site down, not just the
 * features that need auth.
 *
 * Returning null lets every caller degrade instead.
 */
export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  return createBrowserClient(url, key);
}
