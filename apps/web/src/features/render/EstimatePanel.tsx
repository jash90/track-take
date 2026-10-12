import type { Estimate } from "../../api/types";
import { ErrorBox, Spinner } from "../../components/ui";
import { formatMinutes, formatUsd } from "../../lib/format";
import { useT } from "../../i18n";

export function EstimatePanel({ estimate, loading, error, ready }: { estimate: Estimate | undefined; loading: boolean; error: unknown; ready: boolean }) {
  const t = useT();
  if (!ready) return <p className="py-4 text-sm text-ink-400">{t("est.notReady")}</p>;
  if (error) return <ErrorBox title={t("est.error")} error={error} />;
  if (!estimate) return <div className="flex items-center gap-2 py-6 text-sm text-ink-400"><Spinner small /> {t("est.loading")}</div>;
  const e = estimate;
  return (
    <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-ink-700 bg-ink-700 sm:grid-cols-4">
        {[
          { k: t("est.cost"), v: formatUsd(e.usd), big: true },
          { k: t("est.time"), v: formatMinutes(e.minutes) },
          { k: t("est.clips"), v: String(e.clips) },
          { k: t("est.models"), v: `${e.models_gb} GB` },
        ].map((x) => (
          <div key={x.k} className="bg-ink-900 px-4 py-3">
            <dt className="eyebrow">{x.k}</dt>
            <dd className={`mt-1 tabular ${x.big ? "font-display text-4xl text-safe-hi" : "font-display text-3xl"}`}>{x.v}</dd>
          </div>
        ))}
      </dl>
      {e.alternatives?.length > 1 && (
        <div className="mt-3">
          <div className="label">{t("est.alternatives")}</div>
          <div className="flex flex-wrap gap-2">
            {e.alternatives.map((a) => {
              const cheapest = Math.min(...e.alternatives.map((x) => x.usd));
              return (
                <div key={a.workers}
                  className={`rounded-lg border px-3 py-2 font-mono text-[0.75rem] ${a.workers === e.workers ? "border-safe/60 text-ink-100" : "border-ink-700 text-ink-300"}`}>
                  {t("est.cards", { count: a.workers })} · {formatMinutes(a.minutes)} · <span className="tabular">{formatUsd(a.usd)}</span>
                  {a.usd === cheapest && <span className="ml-1.5 text-ok">{t("est.cheapest")}</span>}
                </div>
              );
            })}
          </div>
          <p className="mt-1.5 text-[0.75rem] text-ink-500">{t("est.altNote")}</p>
        </div>
      )}
      {e.missing_keys > 0 && (
        <div role="alert" className="mt-3 rounded-lg border border-warn/40 bg-warn/[0.07] px-4 py-2.5 text-[0.85rem] text-warn">
          {t("est.missing", { count: e.missing_keys })}
        </div>
      )}
      <div className="mt-5">
        <div className="label">{t("est.offers")}</div>
        {e.offers.length === 0 ? (
          <p className="text-[0.82rem] text-ink-500">{t("est.noOffers")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-ink-700">
            <table className="w-full text-left font-mono text-[0.75rem]">
              <thead className="bg-ink-900 text-ink-500">
                <tr>
                  <th className="px-3 py-2 font-normal">GPU</th>
                  <th className="px-3 py-2 text-right font-normal">$/h</th>
                  <th className="px-3 py-2 text-right font-normal">{t("est.col.download")}</th>
                  <th className="px-3 py-2 text-right font-normal">{t("est.col.inet")}</th>
                  <th className="px-3 py-2 font-normal">{t("est.col.location")}</th>
                </tr>
              </thead>
              <tbody>
                {e.offers.map((o) => (
                  <tr key={o.id} className="border-t border-ink-800 text-ink-200">
                    <td className="px-3 py-1.5">{o.gpu}</td>
                    <td className="px-3 py-1.5 text-right tabular">{formatUsd(o.dph, 3)}</td>
                    <td className="px-3 py-1.5 text-right tabular">{formatUsd(o.download_usd)}</td>
                    <td className="px-3 py-1.5 text-right tabular">{Math.round(o.inet_down)} Mb/s</td>
                    <td className="px-3 py-1.5 text-ink-400">{o.location}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
