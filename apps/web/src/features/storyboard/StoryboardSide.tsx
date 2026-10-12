import type { Job, Storyboard } from "../../api/types";
import { ContinuityBox } from "./ContinuityBox";
import { DirectorPanel } from "./DirectorPanel";
import { WorldPanel } from "./WorldPanel";

type Patch = Partial<Pick<Storyboard, "style" | "heroine" | "locations" | "props">>;

interface Props {
  projectId: string;
  draft: Storyboard;
  dirty: boolean;
  writing: boolean;
  checking: Job | undefined;
  instructions: string;
  onInstructions: (v: string) => void;
  onChange: (patch: Patch) => void;
  selectedCount: number;
  rewriteBusy: boolean;
  onRewrite: () => void;
  onJump: (shotId: string) => void;
  onJobStarted: () => void;
}

/** Right column of the storyboard: style bible + director, world bible, continuity. */
export function StoryboardSide(p: Props) {
  return (
    <div className="flex flex-col gap-5">
      <DirectorPanel
        draft={p.draft}
        disabled={p.writing}
        instructions={p.instructions}
        onInstructions={p.onInstructions}
        onChange={p.onChange}
        selectedCount={p.selectedCount}
        busy={p.rewriteBusy}
        onRewrite={p.onRewrite}
      />
      <WorldPanel draft={p.draft} disabled={p.writing} onChange={p.onChange} />
      <ContinuityBox
        projectId={p.projectId}
        continuity={p.draft.continuity}
        running={p.checking}
        dirty={p.dirty}
        onJump={p.onJump}
        onStarted={p.onJobStarted}
      />
    </div>
  );
}
