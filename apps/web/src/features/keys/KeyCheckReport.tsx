import type { KeyCheck, KeyCheckIssue, ShotKeys } from "../../api/types";
import { Chip } from "../../components/ui";
import { useT } from "../../i18n";
import { formatClock, formatDate } from "../../lib/format";
import { isFlipped, keyIssue } from "./stale";

type Fixed = "flipped" | "pending" | "redrawn";

/** What became of a reported error: mirrored → flipped; a correction note still waiting → pending; otherwise redrawn. */
function fixedState(issue: KeyCheckIssue, k: ShotKeys | undefined, check: KeyCheck): Fixed {
  if (keyIssue(k, check.orientation)) return "pending";
  if (issue.kind === "mirrored" && isFlipped(k, check.orientation)) return "flipped";
  return "redrawn";
}

interface Props {
  check: KeyCheck;
  codex: Record<string, ShotKeys> | undefined;
  onJump: (shotId: string) => void;
}

/** Result of the last visual keyframe check: when, how many errors, and what happened to each. */
export function KeyCheckReport({ check, codex, onJump }: Props) {
  const t = useT();
  const issues = check.issues;
  return (
    <section className="panel flex flex-col gap-3 p-5">
      <div>
        <div className="eyebrow">{t("keys.report.eyebrow")}</div>
        <div className="mt-0.5 text-[0.85rem] text-ink-200">
          {t("keys.report.checked", { time: `${formatDate(check.checked)} ${formatClock(check.checked)}`, count: issues.length })}
        </div>
      </div>
      {issues.length === 0 && <p className="text-[0.78rem] text-ok">{t("keys.report.none")}</p>}
      {issues.length > 0 && (
        <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
          {issues.map((it, i) => {
            const state = fixedState(it, codex?.[it.shot], check);
            return (
              <li key={`${it.shot}-${i}`} className="flex items-start gap-3 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-[0.78rem]">
                <button
                  type="button"
                  onClick={() => onJump(it.shot)}
                  aria-label={t("keys.report.jump", { id: it.shot })}
                  className="shrink-0 font-mono text-safe-hi underline-offset-4 hover:underline"
                >
                  {it.shot}
                </button>
                <div className="min-w-0 flex-1">
                  <span className="mr-2 inline-block rounded-full border border-ink-600 bg-ink-800 px-1.5 py-px align-[1px] font-mono text-[0.62rem] text-ink-300">
                    {t(`keys.kind.${it.kind}`)}
                  </span>
                  <span className="text-ink-300">{it.problem}</span>
                  {it.fix && (
                    <p className="mt-0.5 text-[0.72rem] italic text-ink-500">
                      {t("keys.report.fix")}: {it.fix}
                    </p>
                  )}
                </div>
                {state === "pending" ? (
                  <Chip tone="warn" className="shrink-0" title={t("keys.report.pendingTip")}>{t("keys.report.pending")}</Chip>
                ) : state === "flipped" ? (
                  <Chip tone="ok" className="shrink-0" title={t("keys.flippedTip")}>⇋ {t("keys.report.flipped")}</Chip>
                ) : (
                  <Chip tone="ok" className="shrink-0" title={t("keys.report.redrawnTip")}>↻ {t("keys.report.redrawn")}</Chip>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
