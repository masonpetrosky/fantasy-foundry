import { describe, expect, it, vi } from "vitest";
import { createSupabaseClientLoader } from "./supabase_client.js";

describe("createSupabaseClientLoader", () => {
  it("returns null and skips import when auth sync is disabled", async () => {
    const importSupabaseModule = vi.fn();
    const loadClient = createSupabaseClientLoader({
      enabled: false,
      supabaseUrl: "https://example.supabase.co",
      supabaseAnonKey: "anon-key",
      importSupabaseModule,
    });

    await expect(loadClient()).resolves.toBeNull();
    expect(importSupabaseModule).not.toHaveBeenCalled();
  });

  it("deduplicates concurrent imports and reuses one client instance", async () => {
    const client = { auth: {} };
    const createClient = vi.fn(() => client);
    const importSupabaseModule = vi.fn(async () => ({ createClient }));
    const loadClient = createSupabaseClientLoader({
      enabled: true,
      supabaseUrl: "https://example.supabase.co",
      supabaseAnonKey: "anon-key",
      importSupabaseModule,
    });

    const [first, second] = await Promise.all([loadClient(), loadClient()]);

    expect(first).toBe(client);
    expect(second).toBe(client);
    expect(importSupabaseModule).toHaveBeenCalledTimes(1);
    expect(createClient).toHaveBeenCalledTimes(1);
    expect(createClient).toHaveBeenCalledWith(
      "https://example.supabase.co",
      "anon-key",
      expect.objectContaining({
        auth: expect.objectContaining({
          persistSession: true,
          autoRefreshToken: true,
        }),
      })
    );
  });

  it("retries import after an initialization failure", async () => {
    const client = { auth: {} };
    const createClient = vi.fn(() => client);
    const importSupabaseModule = vi
      .fn()
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValue({ createClient });
    const loadClient = createSupabaseClientLoader({
      enabled: true,
      supabaseUrl: "https://example.supabase.co",
      supabaseAnonKey: "anon-key",
      importSupabaseModule,
    });

    await expect(loadClient()).rejects.toThrow("temporary failure");
    await expect(loadClient()).resolves.toBe(client);
    expect(importSupabaseModule).toHaveBeenCalledTimes(2);
    expect(createClient).toHaveBeenCalledTimes(1);
  });
});
