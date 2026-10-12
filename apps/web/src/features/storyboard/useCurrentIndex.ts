import { useEffect, useState } from "react";
import type { Transport } from "./useAudioTransport";

type Span = { start: number; end: number };

/** Index of the item (shot / lyric line) under the playhead; re-renders only when it changes. */
export function useCurrentIndex(transport: Transport, items: readonly Span[]): number {
  const [idx, setIdx] = useState(-1);
  useEffect(() => {
    const find = (t: number) => {
      // items are sorted by start — binary search keeps this cheap at 60 fps
      let lo = 0;
      let hi = items.length - 1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const it = items[mid]!;
        if (t < it.start) hi = mid - 1;
        else if (t >= it.end) lo = mid + 1;
        else return mid;
      }
      return -1;
    };
    const tick = (t: number) => setIdx(find(t));
    tick(transport.time());
    return transport.subscribe(tick);
  }, [transport, items]);
  return idx;
}
