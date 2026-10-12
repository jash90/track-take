import { Link } from "react-router";
import { useVideos } from "../../api/hooks";
import type { KeySet, VideoFiles } from "../../api/types";
import { Empty, ErrorBox, Loading, StepHeader } from "../../components/ui";
import { FormatBadge, formatRatio, projectFormat, projectOrientation } from "../../lib/orientation";
import { useWorkspace } from "../workspace/context";
import { CompareView } from "./CompareView";
import { SetPlayers } from "./SetPlayers";

export function ResultStep() {
  const { project } = useWorkspace();
  const q = useVideos(project.id);
  const format = projectFormat(project);

  if (q.isPending) return <Loading label="Szukam wyrenderowanych plików…" />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;

  // only the project format; files of the other orientation (from before a switch) stay hidden
  const files: Partial<Record<KeySet, VideoFiles>> = {};
  for (const s of ["codex", "comfy"] as KeySet[]) {
    const f = q.data[s]?.[format];
    if (f && (f.preview || f.master)) files[s] = f;
  }
  const sets = (Object.keys(files) as KeySet[]).sort();

  return (
    <div>
      <StepHeader index="05" title="Wynik" actions={<FormatBadge orientation={projectOrientation(project)} />}>
        Teledysk w formacie {formatRatio(format)}: podgląd do szybkiego obejrzenia i master w pełnej jakości do publikacji.
      </StepHeader>
      {sets.length === 0 ? (
        <Empty title="Jeszcze nic nie wyrenderowano" action={<Link to="../wideo" className="text-sm text-safe hover:underline">→ Render na Vast</Link>}>
          Gdy render się skończy, wideo {formatRatio(format)} pojawi się tutaj.
        </Empty>
      ) : (
        <div className="flex flex-col gap-6">
          {files.codex && files.comfy && <CompareView format={format} a={files.codex} b={files.comfy} />}
          {sets.map((s) => {
            const f = files[s];
            return f ? <SetPlayers key={s} set={s} format={format} files={f} /> : null;
          })}
        </div>
      )}
    </div>
  );
}
