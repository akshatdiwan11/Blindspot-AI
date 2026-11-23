import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useAsync } from "../hooks/useAsync";

describe("useAsync", () => {
  it("reports loading on the very first render after it becomes enabled", async () => {
    // Regression: pages crashed when a run was auto-selected, because one render had
    // loading=false and no data yet.
    const fn = vi.fn(() => Promise.resolve({ value: 1 }));
    const { result, rerender } = renderHook(({ id }) => useAsync(() => fn(), [id], id !== null), { initialProps: { id: null as number | null } });
    expect(result.current.loading).toBe(false);
    rerender({ id: 7 });
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ value: 1 });
  });

  it("surfaces errors and ignores stale responses", async () => {
    let rejectFirst!: (e: Error) => void;
    const calls = [new Promise<string>((_, rej) => { rejectFirst = rej; }), Promise.resolve("second")];
    let i = 0;
    const { result, rerender } = renderHook(({ k }) => useAsync(() => calls[i++], [k]), { initialProps: { k: 1 } });
    rerender({ k: 2 });
    await waitFor(() => expect(result.current.data).toBe("second"));
    rejectFirst(new Error("old request"));
    await new Promise((r) => setTimeout(r, 10));
    expect(result.current.error).toBeUndefined();
    expect(result.current.data).toBe("second");
  });
});
