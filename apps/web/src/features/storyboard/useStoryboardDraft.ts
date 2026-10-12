import { useCallback, useEffect, useRef, useState } from "react";
import type { Shot, Storyboard } from "../../api/types";

/** Local editable copy of the storyboard. Adopts server updates unless the user has unsaved edits. */
export function useStoryboardDraft(server: Storyboard | undefined) {
  const [draft, setDraft] = useState<Storyboard | null>(server ?? null);
  const base = useRef<Storyboard | null>(server ?? null);
  const [stale, setStale] = useState(false);
  const dirty = draft !== base.current;

  useEffect(() => {
    if (!server || server === base.current) return;
    if (draft === base.current) {
      base.current = server;
      setDraft(server);
      setStale(false);
    } else {
      setStale(true);
    }
  }, [server]);

  const adopt = useCallback((doc: Storyboard) => {
    base.current = doc;
    setDraft(doc);
    setStale(false);
  }, []);

  const update = useCallback((patch: Partial<Pick<Storyboard, "style" | "heroine" | "locations" | "props">>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d));
  }, []);

  const updateShot = useCallback((id: string, patch: Partial<Shot>) => {
    setDraft((d) => (d ? { ...d, shots: d.shots.map((s) => (s.id === id ? { ...s, ...patch } : s)) } : d));
  }, []);

  const discard = useCallback(() => {
    if (server) adopt(server);
  }, [server, adopt]);

  return { draft, dirty, stale, adopt, update, updateShot, discard };
}
