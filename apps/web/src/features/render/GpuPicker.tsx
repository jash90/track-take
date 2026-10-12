import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { VastGpu, VastGpus } from "../../api/types";
import { Spinner } from "../../components/ui";
import { useI18n, type Key, type TFn } from "../../i18n";
import { cx } from "../../lib/cx";
import { formatUsd } from "../../lib/format";

type Sort = "popular" | "cheapest" | "fastest";
const SORTS: { v: Sort; label: Key }[] = [
  { v: "popular", label: "gpu.sort.popular" },
  { v: "cheapest", label: "gpu.sort.cheapest" },
  { v: "fastest", label: "gpu.sort.fastest" },
];

const norm = (s: string) => s.toLowerCase().replace(/[\s_-]+/g, "");

export function formatSpeed(speed: number, locale: string): string {
  return new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(speed);
}

function unsuitableReason(g: VastGpu, minVram: number, t: TFn): string {
  return g.vram_gb < minVram ? t("gpu.reasonVram", { gb: g.vram_gb, min: minVram }) : t("gpu.reasonArch");
}

/** The suitable card with the lowest cost of the same work, among cards with matching offers. */
function cheapestVideo(gpus: VastGpu[]): string | null {
  let best: VastGpu | null = null;
  for (const g of gpus) {
    if (!g.suitable || g.matching <= 0 || g.usd_per_4090_hour === null) continue;
    if (!best || g.usd_per_4090_hour < (best.usd_per_4090_hour ?? Infinity)) best = g;
  }
  return best?.gpu ?? null;
}

function sorted(gpus: VastGpu[], sort: Sort): VastGpu[] {
  if (sort === "popular") return gpus;
  const rank = (g: VastGpu) => (g.suitable ? (g.matching > 0 ? 0 : 1) : 2);
  return [...gpus].sort((a, b) => {
    const r = rank(a) - rank(b);
    if (r !== 0) return r;
    if (sort === "fastest") return b.speed - a.speed;
    return (a.usd_per_4090_hour ?? Infinity) - (b.usd_per_4090_hour ?? Infinity);
  });
}

interface Props {
  value: string;
  data: VastGpus | undefined;
  loading: boolean;
  failed: boolean;
  onPick: (gpu: string, card: VastGpu | null) => void;
}

/** Combobox over live Vast offers: type to filter, arrows + Enter to pick, Esc to close. */
export function GpuPicker({ value, data, loading, failed, onPick }: Props) {
  const { t, locale } = useI18n();
  const id = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("popular");
  const [active, setActive] = useState(0);

  const gpus = useMemo(() => data?.gpus ?? [], [data]);
  const selected = gpus.find((g) => g.gpu === value) ?? null;
  const cheapest = useMemo(() => cheapestVideo(gpus), [gpus]);
  const items = useMemo(() => {
    const q = norm(query);
    const hits = q ? gpus.filter((g) => norm(g.label).includes(q) || norm(g.gpu).includes(q)) : gpus;
    return sorted(hits, sort);
  }, [gpus, query, sort]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    list.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const openList = () => {
    setOpen(true);
    setQuery("");
    setActive(Math.max(0, gpus.findIndex((g) => g.gpu === value)));
  };
  const pick = (g: VastGpu) => {
    if (!g.suitable) return;
    onPick(g.gpu, g);
    setOpen(false);
    setQuery("");
  };
  const move = (dir: 1 | -1) => {
    if (!items.length) return;
    let i = active;
    for (let n = 0; n < items.length; n++) {
      i = (i + dir + items.length) % items.length;
      if (items[i]?.suitable) break;
    }
    setActive(i);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (failed) {
      if (e.key === "Enter" && query.trim()) onPick(query.trim(), null);
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) openList();
      else move(e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const g = items[active];
      if (open && g) pick(g);
      else openList();
    } else if (e.key === "Escape") {
      if (open) {
        e.stopPropagation();
        setOpen(false);
      }
    } else if (e.key === "Tab") setOpen(false);
  };

  const listId = `${id}-list`;
  const shown = open || failed ? query : (selected?.label ?? value);

  return (
    <div ref={wrap} className="relative">
      <div className="relative">
        <input
          id="gpu"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && items[active] ? `${id}-opt-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          className="field pr-9 font-mono"
          placeholder={failed ? value : t("gpu.placeholder")}
          value={shown}
          onFocus={() => !failed && openList()}
          onClick={() => !failed && !open && openList()}
          onChange={(e) => {
            const q = norm(e.target.value);
            setQuery(e.target.value);
            // highlight the first suitable match so Enter picks it
            const hits = sorted(q ? gpus.filter((g) => norm(g.label).includes(q) || norm(g.gpu).includes(q)) : gpus, sort);
            setActive(Math.max(0, hits.findIndex((g) => g.suitable)));
            if (!open && !failed) setOpen(true);
          }}
          onBlur={() => {
            if (failed && query.trim()) onPick(query.trim(), null);
          }}
          onKeyDown={onKey}
        />
        <span aria-hidden className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400">
          {loading ? <Spinner small /> : "▾"}
        </span>
      </div>
      {failed && <p className="mt-1 text-[0.72rem] text-warn">{t("gpu.loadError")}</p>}

      {open && !failed && (
        <div className="absolute left-0 top-full z-30 mt-1 w-[min(640px,calc(100vw-3rem))] overflow-hidden rounded-lg border border-ink-600 bg-ink-850 shadow-[0_24px_60px_-12px_rgb(0_0_0/0.85)]">
          <div className="flex items-center justify-between gap-3 border-b border-ink-700 px-3 py-2">
            <span className="eyebrow">{t("gpu.sort")}</span>
            <div role="radiogroup" aria-label={t("gpu.sort")} className="flex rounded-md border border-ink-600 p-0.5">
              {SORTS.map((s) => (
                <button
                  key={s.v}
                  type="button"
                  role="radio"
                  aria-checked={sort === s.v}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    setSort(s.v);
                    setActive(0);
                  }}
                  className={cx("rounded px-2.5 py-1 text-[0.72rem]", sort === s.v ? "bg-ink-100 text-ink-950" : "text-ink-300 hover:text-ink-100")}
                >
                  {t(s.label)}
                </button>
              ))}
            </div>
          </div>
          {loading && !data && <div className="flex items-center gap-2 px-3 py-4 text-sm text-ink-400"><Spinner small /> {t("gpu.loading")}</div>}
          <ul ref={list} id={listId} role="listbox" aria-label={t("gpu.listAria")} className="max-h-[340px] overflow-y-auto py-1">
            {data && items.length === 0 && <li className="px-3 py-4 text-sm text-ink-500">{t("gpu.noResults", { q: query })}</li>}
            {items.map((g, i) => (
              <GpuOption
                key={g.gpu}
                id={`${id}-opt-${i}`}
                idx={i}
                g={g}
                active={i === active}
                selected={g.gpu === value}
                cheapest={g.gpu === cheapest}
                reason={g.suitable ? null : unsuitableReason(g, data?.min_vram_gb ?? 24, t)}
                locale={locale}
                t={t}
                onHover={() => setActive(i)}
                onPick={() => pick(g)}
              />
            ))}
          </ul>
          {data && (
            <p className="border-t border-ink-700 px-3 py-2 text-[0.68rem] text-ink-500">
              {t("gpu.filtersNote", {
                rel: String(data.filters.min_reliability),
                inet: data.filters.min_inet_down_mbps,
                dl: formatUsd(data.filters.max_download_usd_per_gb, 3),
              })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

interface OptionProps {
  id: string;
  idx: number;
  g: VastGpu;
  active: boolean;
  selected: boolean;
  cheapest: boolean;
  reason: string | null;
  locale: string;
  t: TFn;
  onHover: () => void;
  onPick: () => void;
}

function GpuOption({ id, idx, g, active, selected, cheapest, reason, locale, t, onHover, onPick }: OptionProps) {
  return (
    <li
      id={id}
      data-idx={idx}
      role="option"
      aria-selected={selected}
      aria-disabled={!g.suitable}
      onMouseEnter={onHover}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onPick}
      className={cx(
        "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-0.5 px-3 py-2",
        g.suitable ? "cursor-pointer" : "cursor-not-allowed opacity-45",
        active && g.suitable && "bg-ink-750",
        selected && "border-l-2 border-safe",
      )}
    >
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-[0.92rem] text-ink-100">{g.label}</span>
        <span className="shrink-0 font-mono text-[0.68rem] text-ink-500">{t("gpu.vram", { gb: g.vram_gb })}</span>
        {cheapest && (
          <span className="shrink-0 rounded-full border border-ok/50 bg-ok/10 px-2 py-px font-mono text-[0.6rem] text-ok">
            {t("gpu.cheapestVideo")}
          </span>
        )}
      </div>
      <div className="text-right font-mono text-[0.75rem] text-ink-200 tabular">
        {g.suitable ? t("gpu.from", { usd: formatUsd(g.min_dph_per_gpu, 3) }) : ""}
      </div>
      <div className="font-mono text-[0.7rem] text-ink-400">
        {reason ?? (
          <>
            {t("gpu.speed", { speed: formatSpeed(g.speed, locale) })}
            {!g.speed_measured && <span className="ml-1 text-ink-500">({t("gpu.speedEst")})</span>}
          </>
        )}
      </div>
      <div className={cx("text-right font-mono text-[0.7rem]", g.matching > 0 ? "text-ink-400" : "text-ink-600")}>
        {g.suitable && (g.matching > 0 ? t("gpu.offers", { count: g.matching }) : t("gpu.noMatching"))}
      </div>
    </li>
  );
}
