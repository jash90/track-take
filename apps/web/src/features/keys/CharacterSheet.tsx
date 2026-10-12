import { Button } from "../../components/ui";

interface Props {
  src: string | null;
  busy: boolean;
  running: boolean;
  onGenerate: () => void;
  onOpen: () => void;
}

export function CharacterSheet({ src, busy, running, onGenerate, onOpen }: Props) {
  return (
    <section className="panel flex flex-col gap-4 overflow-hidden p-5 md:flex-row md:items-center">
      {src ? (
        <button type="button" onClick={onOpen} aria-label="Powiększ arkusz postaci" className="shrink-0 overflow-hidden rounded-lg border border-ink-600 hover:border-safe">
          <img src={src} alt="Arkusz postaci" className="h-44 w-auto max-w-[420px] object-contain" />
        </button>
      ) : (
        <div className="grid h-44 w-72 shrink-0 place-items-center rounded-lg border border-dashed border-ink-600 font-display text-xl italic text-ink-600">
          brak arkusza
        </div>
      )}
      <div className="flex flex-col gap-2">
        <div className="eyebrow">Postać</div>
        <h2 className="font-display text-3xl leading-none">Arkusz postaci</h2>
        <p className="max-w-md text-[0.85rem] leading-relaxed text-ink-400">
          Codex rysuje bohaterkę z okładki i opisu „Bohaterka” ze storyboardu. Ten arkusz jest referencją dla każdej klatki — dzięki
          niemu postać wygląda tak samo w całym teledysku.
        </p>
        <div>
          <Button variant={src ? "secondary" : "primary"} busy={busy || running} onClick={onGenerate}>
            {src ? "Wygeneruj ponownie" : "Wygeneruj arkusz postaci"}
          </Button>
        </div>
      </div>
    </section>
  );
}
