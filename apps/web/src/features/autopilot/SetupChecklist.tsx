import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useSetup } from "../../api/hooks";
import type { SetupCheck } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { Button, ErrorBox, Loading } from "../../components/ui";
import { VastKeyForm } from "../../components/VastKeyForm";
import { useT, type Key } from "../../i18n";
import { cx } from "../../lib/cx";
import { errorMessage } from "../../lib/format";

const ROWS: SetupCheck[] = ["claude", "codex", "codex_login", "ffmpeg", "vast_key", "ssh_key", "ssh_key_on_vast"];

/** Text with `inline code` rendered as <code>. */
function WithCode({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/g).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") ? (
          <code key={i} className="rounded bg-ink-950 px-1 py-px font-mono text-[0.95em] text-ink-100">
            {part.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/** What the app needs on this Mac and on Vast, with plain-language fixes. */
export function SetupChecklist() {
  const t = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const setup = useSetup();
  const ssh = useMutation({
    mutationFn: api.setupSshKey,
    onSuccess: (s) => {
      qc.setQueryData(qk.setup, s);
      if (s.checks.ssh_key && s.checks.ssh_key_on_vast) toast(t("setup.sshDone"), "ok");
    },
    onError: (err) => toast(t("setup.sshError", { error: errorMessage(err) }), "err"),
  });

  if (setup.isPending) return <Loading label={t("setup.loading")} />;
  if (setup.isError) return <ErrorBox error={setup.error} onRetry={() => void setup.refetch()} />;
  const checks = setup.data.checks;
  const missing = ROWS.filter((r) => checks[r] === false).length;
  const sshShownOn = ROWS.find((r) => (r === "ssh_key" || r === "ssh_key_on_vast") && checks[r] !== true);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[0.82rem] leading-relaxed text-ink-400">{t("setup.lead")}</p>
        <Button size="sm" variant="ghost" busy={setup.isFetching} onClick={() => void setup.refetch()}>
          {t("setup.recheck")}
        </Button>
      </div>
      <div className={cx("rounded-lg px-3 py-2 text-sm", setup.data.ready ? "bg-ok/10 text-ok" : "bg-warn/10 text-warn")}>
        {setup.data.ready ? `✓ ${t("setup.ready")}` : t("setup.missingCount", { count: Math.max(1, missing) })}
      </div>
      <ul className="flex flex-col divide-y divide-ink-800 rounded-lg border border-ink-700 bg-ink-900">
        {ROWS.map((r) => {
          const v = checks[r];
          return (
            <li key={r} className="flex gap-3 px-4 py-3">
              <span
                aria-hidden
                className={cx(
                  "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[0.7rem] font-bold",
                  v === true && "bg-ok text-ink-950",
                  v === false && "bg-err/80 text-ink-950",
                  v === null && "border border-ink-500 text-ink-400",
                )}
              >
                {v === true ? "✓" : v === false ? "!" : "?"}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-baseline gap-2">
                  <span className="text-[0.9rem] text-ink-100">{t(`setup.${r}` as Key)}</span>
                  <span className={cx("font-mono text-[0.65rem]", v === true ? "text-ok" : v === false ? "text-err" : "text-ink-500")}>
                    {v === true ? t("setup.ok") : v === false ? t("setup.missing") : t("setup.unknown")}
                  </span>
                </div>
                <span className="text-[0.75rem] text-ink-400">{t(`setup.${r}.why` as Key)}</span>
                {v !== true && (
                  <span className="text-[0.75rem] text-ink-300">
                    <WithCode text={t(`setup.${r}.fix` as Key)} />
                  </span>
                )}
                {r === "vast_key" && v !== true && (
                  <div className="mt-2">
                    <VastKeyForm />
                  </div>
                )}
                {r === sshShownOn && checks.vast_key === true && (
                  <Button size="sm" variant="secondary" className="mt-2 self-start" busy={ssh.isPending} onClick={() => ssh.mutate()}>
                    {t("setup.auto")}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
