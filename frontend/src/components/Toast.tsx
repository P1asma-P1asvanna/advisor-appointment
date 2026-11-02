import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { ApiError } from "../api/client";

type Kind = "ok" | "err";
interface T { id: number; kind: Kind; text: string }
const Ctx = createContext<{ ok(m: string): void; fail(e: unknown): void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const push = useCallback((kind: Kind, text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === "err" ? 6000 : 3500);
  }, []);
  const ok = useCallback((m: string) => push("ok", m), [push]);
  const fail = useCallback((e: unknown) => push("err", e instanceof ApiError ? e.message : "เกิดข้อผิดพลาด ลองใหม่อีกครั้ง"), [push]);
  return (
    <Ctx.Provider value={{ ok, fail }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={"toast " + i.kind}>{i.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast outside ToastProvider");
  return v;
};
