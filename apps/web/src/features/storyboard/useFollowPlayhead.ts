import { useEffect } from "react";
import type { Shot } from "../../api/types";
import type { Transport } from "./useAudioTransport";
import { useCurrentIndex } from "./useCurrentIndex";

/** While playing with "follow" on, select the shot under the playhead — unless the editor holds unsaved edits. */
export function useFollowPlayhead(transport: Transport, shots: Shot[], follow: boolean, hold: boolean, select: (id: string) => void) {
  const idx = useCurrentIndex(transport, shots);
  useEffect(() => {
    const s = shots[idx];
    if (!s || !follow || !transport.playing || hold) return;
    select(s.id);
  }, [idx, follow, transport.playing, hold, shots]);
}
