import { Trans } from "../../i18n";

interface Props {
  value: number;
  onChange: (n: number) => void;
  /** called when the user lets go — save here */
  onCommit: (n: number) => void;
}

/** Number of machines (Vast hosts) rendering in parallel, 1–8. */
export function MachinesSlider({ value, onChange, onCommit }: Props) {
  return (
    <div>
      <label className="label" htmlFor="workers">
        <Trans k="render.workers" values={{ n: <span className="font-mono text-ink-100">{value}</span> }} />
      </label>
      <input
        id="workers"
        type="range"
        min={1}
        max={8}
        step={1}
        value={value}
        onChange={(ev) => onChange(Number(ev.target.value))}
        onPointerUp={(ev) => onCommit(Number((ev.target as HTMLInputElement).value))}
        onKeyUp={(ev) => onCommit(Number((ev.target as HTMLInputElement).value))}
        className="slider mt-3 w-full"
      />
      <div className="mt-1 flex justify-between font-mono text-[0.62rem] text-ink-500">
        {Array.from({ length: 8 }, (_, i) => (
          <span key={i}>{i + 1}</span>
        ))}
      </div>
    </div>
  );
}
