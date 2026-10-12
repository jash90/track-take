import type { Shot, WorldItem } from "../../api/types";
import { useT } from "../../i18n";
import { cx } from "../../lib/cx";

interface Props {
  shot: Shot;
  locations: WorldItem[];
  props: WorldItem[];
  disabled: boolean;
  onChange: (patch: Partial<Shot>) => void;
}

/** Location select + props chips of one shot, from the storyboard's world bible. */
export function ShotWorldFields({ shot, locations, props, disabled, onChange }: Props) {
  const t = useT();
  if (locations.length === 0 && props.length === 0) {
    return <p className="mt-4 text-[0.75rem] text-ink-500">{t("shot.noWorld")}</p>;
  }
  const chosen = new Set(shot.props ?? []);
  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange({ props: props.map((p) => p.id).filter((pid) => next.has(pid)) });
  };
  const loc = locations.find((l) => l.id === shot.location);

  return (
    <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
      <div>
        <label className="label" htmlFor="shot-location">{t("shot.location")}</label>
        <select
          id="shot-location"
          className="field text-[0.85rem]"
          disabled={disabled}
          value={shot.location ?? ""}
          onChange={(e) => onChange({ location: e.target.value || undefined })}
        >
          <option value="">{t("shot.noLocation")}</option>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
          {shot.location && !loc && <option value={shot.location}>{shot.location}</option>}
        </select>
        {loc?.look && <p className="mt-1 line-clamp-3 text-[0.7rem] italic leading-snug text-ink-500">{loc.look}</p>}
      </div>
      <div>
        <div className="label" id="shot-props">{t("shot.props")}</div>
        <div role="group" aria-labelledby="shot-props" className="flex flex-wrap gap-1.5">
          {props.map((p) => {
            const on = chosen.has(p.id);
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={on}
                disabled={disabled}
                title={p.look}
                onClick={() => toggle(p.id)}
                className={cx(
                  "rounded-full border px-2.5 py-1 text-[0.75rem] transition-colors disabled:opacity-50",
                  on ? "border-safe bg-safe/15 text-ink-100" : "border-ink-600 text-ink-400 hover:border-ink-400 hover:text-ink-200",
                )}
              >
                {on ? "✓ " : ""}
                {p.name}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
