import type { Storyboard, WorldItem } from "../../api/types";
import { useT, type Key } from "../../i18n";

type Kind = "locations" | "props";

interface Props {
  draft: Storyboard;
  disabled: boolean;
  onChange: (patch: Partial<Pick<Storyboard, "locations" | "props">>) => void;
}

function newId(prefix: string, items: WorldItem[]): string {
  let n = items.length + 1;
  while (items.some((i) => i.id === `${prefix}${n}`)) n++;
  return `${prefix}${n}`;
}

/** World bible: recurring locations and props with fixed looks, saved with the storyboard. */
export function WorldPanel({ draft, disabled, onChange }: Props) {
  const t = useT();
  const locations = draft.locations ?? [];
  const props = draft.props ?? [];
  const empty = locations.length === 0 && props.length === 0;

  const edit = (kind: Kind, list: WorldItem[], id: string, patch: Partial<WorldItem>) =>
    onChange({ [kind]: list.map((i) => (i.id === id ? { ...i, ...patch } : i)) });
  const remove = (kind: Kind, list: WorldItem[], id: string) => onChange({ [kind]: list.filter((i) => i.id !== id) });
  const add = (kind: Kind, list: WorldItem[]) =>
    onChange({
      [kind]: [...list, { id: newId(kind === "locations" ? "loc" : "prop", list), name: t(kind === "locations" ? "world.newLocation" : "world.newProp"), look: "" }],
    });

  const section = (kind: Kind, list: WorldItem[], title: Key, addLabel: Key) => (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="label mb-0">{t(title)}</span>
        <button type="button" disabled={disabled} onClick={() => add(kind, list)} className="text-[0.75rem] text-safe hover:underline disabled:opacity-40">
          {t(addLabel)}
        </button>
      </div>
      {list.map((item) => (
        <div key={item.id} className="flex flex-col gap-1.5 rounded-lg border border-ink-700 bg-ink-900 p-2.5">
          <div className="flex items-center gap-2">
            <input
              aria-label={t("world.name")}
              className="field h-8 py-1 text-[0.85rem]"
              value={item.name}
              disabled={disabled}
              onChange={(e) => edit(kind, list, item.id, { name: e.target.value })}
            />
            <span className="shrink-0 font-mono text-[0.62rem] text-ink-500">{item.id}</span>
            <button
              type="button"
              disabled={disabled}
              onClick={() => remove(kind, list, item.id)}
              aria-label={t("world.remove", { name: item.name })}
              className="grid h-7 w-7 shrink-0 place-items-center rounded text-ink-500 hover:bg-ink-750 hover:text-err disabled:opacity-40"
            >
              ✕
            </button>
          </div>
          <textarea
            aria-label={`${t("world.look")} — ${item.name}`}
            rows={2}
            disabled={disabled}
            className="field resize-y text-[0.8rem] leading-relaxed"
            placeholder={t("world.lookPlaceholder")}
            value={item.look}
            onChange={(e) => edit(kind, list, item.id, { look: e.target.value })}
          />
        </div>
      ))}
    </div>
  );

  return (
    <section className="panel flex flex-col gap-4 p-5">
      <div>
        <div className="eyebrow">{t("world.eyebrow")}</div>
        <div className="mt-0.5 font-display text-2xl">{t("world.title")}</div>
        <p className="mt-1 text-[0.75rem] leading-relaxed text-ink-500">{t("world.hint")}</p>
      </div>
      {empty && <p className="rounded-lg border border-dashed border-ink-600 px-3 py-3 text-[0.8rem] text-ink-400">{t("world.empty")}</p>}
      {section("locations", locations, "world.locations", "world.addLocation")}
      {section("props", props, "world.props", "world.addProp")}
    </section>
  );
}
