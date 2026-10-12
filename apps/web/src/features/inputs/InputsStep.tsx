import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { api, qk } from "../../api/client";
import { useLyrics, useStartJob } from "../../api/hooks";
import type { Project } from "../../api/types";
import { Dropzone } from "../../components/Dropzone";
import { useToast } from "../../components/Toaster";
import { Button, Hint, InlineError, ProgressBar, StepHeader } from "../../components/ui";
import { useObjectUrl } from "../../lib/useObjectUrl";
import { activeJob, useWorkspace } from "../workspace/context";
import { AnalysisSummary } from "./AnalysisSummary";
import { OrientationField } from "./OrientationField";
import { Trans, useT, type Key } from "../../i18n";
import { jobTitle } from "../jobs/jobTitle";

const LANGS: { value: string; label: Key }[] = [
  { value: "en", label: "lang.en" },
  { value: "pl", label: "lang.pl" },
];

export function InputsStep() {
  const { project, jobs, openJobs } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const navigate = useNavigate();
  const lyricsQ = useLyrics(project.id, project.inputs.lyrics);

  const [name, setName] = useState(project.name);
  const [style, setStyle] = useState(project.style);
  const [language, setLanguage] = useState(project.language || "en");
  const [lyrics, setLyrics] = useState<string | null>(null);
  const [song, setSong] = useState<File | null>(null);
  const [cover, setCover] = useState<File | null>(null);
  const [bust, setBust] = useState(0);

  // adopt server lyrics until the user starts typing
  useEffect(() => {
    if (lyrics === null && lyricsQ.data) setLyrics(lyricsQ.data.text);
  }, [lyricsQ.data, lyrics]);

  const songUrl = useObjectUrl(song);
  const coverUrl = useObjectUrl(cover);
  const withBust = (u: string | null) => (u && bust ? `${u}${u.includes("?") ? "&" : "?"}v=${bust}` : u);
  const shownCover = coverUrl ?? withBust(project.inputs.cover);
  const shownSong = songUrl ?? withBust(project.inputs.song);

  const serverLyrics = lyricsQ.data?.text ?? "";
  const lyricsDirty = lyrics !== null && lyrics !== serverLyrics;
  const metaDirty = name !== project.name || style !== project.style || language !== project.language;
  const dirty = metaDirty || lyricsDirty || !!song || !!cover;

  const save = useMutation({
    mutationFn: async () => {
      let p: Project = project;
      if (metaDirty) p = await api.patchProject(project.id, { name: name.trim() || project.name, style, language });
      if (song || cover || lyricsDirty) {
        p = await api.uploadInputs(project.id, {
          song: song ?? undefined,
          cover: cover ?? undefined,
          lyrics: lyricsDirty ? (lyrics ?? "") : undefined,
        });
      }
      return p;
    },
    onSuccess: (p) => {
      qc.setQueryData(qk.project(project.id), p);
      void qc.invalidateQueries({ queryKey: qk.projects });
      if (lyricsDirty) void qc.invalidateQueries({ queryKey: qk.lyrics(project.id) });
      setSong(null);
      setCover(null);
      setBust(Date.now());
      toast(t("inputs.savedToast"), "ok");
    },
  });

  const analyze = useStartJob(project.id, () => api.analyze(project.id), () => {
    toast(t("inputs.analysisStarted"), "info");
    openJobs();
  });
  const running = activeJob(jobs, "analyze");
  const canAnalyze = !!project.inputs.song && !dirty;

  return (
    <div className="mx-auto max-w-[1180px]">
      <StepHeader
        index="01"
        title={t("step.inputs")}
        actions={
          <>
            <Button variant="secondary" busy={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
              {dirty ? t("inputs.saveChanges") : t("common.saved")}
            </Button>
            <Button
              variant="primary"
              busy={analyze.isPending || !!running}
              disabled={!canAnalyze}
              title={!project.inputs.song ? t("inputs.uploadSongFirst") : dirty ? t("inputs.saveFirst") : undefined}
              onClick={() => analyze.mutate(undefined)}
            >
              {project.stage.analysis ? t("inputs.reanalyze") : t("inputs.analyze")}
            </Button>
          </>
        }
      >
        {t("inputs.lead")}
      </StepHeader>
      <InlineError error={save.error ?? analyze.error} />

      {running && (
        <div className="mb-6 rounded-xl border border-safe/40 bg-safe/[0.05] px-5 py-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span>{jobTitle(running, t)}</span>
            <span className="truncate font-mono text-[0.75rem] text-ink-400">{running.message}</span>
          </div>
          {running.progress && <ProgressBar className="mt-2" value={running.progress.done} total={running.progress.total} />}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)] xl:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-5">
          <Dropzone
            accept="image/*"
            match={["image/"]}
            label={project.inputs.cover ? t("inputs.changeCover") : t("inputs.pickCover")}
            hint={t("inputs.coverHint")}
            file={cover}
            onFile={setCover}
          >
            <div className="relative aspect-square bg-ink-950">
              {shownCover ? (
                <img src={shownCover} alt={t("inputs.coverAlt")} className="h-full w-full object-cover" />
              ) : (
                <div className="grid h-full place-items-center font-display text-3xl italic text-ink-600">{t("inputs.coverEmpty")}</div>
              )}
            </div>
          </Dropzone>
          <Dropzone
            accept="audio/mpeg,audio/wav,audio/x-wav,.mp3,.wav"
            match={["audio/", ".mp3", ".wav"]}
            label={project.inputs.song ? t("inputs.changeSong") : t("inputs.pickSong")}
            hint={t("inputs.songHint")}
            file={song}
            onFile={setSong}
          >
            <div className="px-4 pt-4">
              {shownSong ? (
                <audio controls preload="metadata" src={shownSong} className="w-full" aria-label={t("inputs.songPreview")} />
              ) : (
                <div className="py-3 font-display text-xl italic text-ink-600">{t("inputs.songEmpty")}</div>
              )}
            </div>
          </Dropzone>
        </div>

        <div className="flex flex-col gap-5">
          <OrientationField project={project} />
          <div className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_200px]">
            <div>
              <label className="label" htmlFor="in-name">{t("inputs.name")}</label>
              <input id="in-name" className="field" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="in-lang">{t("inputs.lyricsLang")}</label>
              <select id="in-lang" className="field" value={language} onChange={(e) => setLanguage(e.target.value)}>
                {LANGS.map((l) => (
                  <option key={l.value} value={l.value}>{t(l.label)}</option>
                ))}
                {!LANGS.some((l) => l.value === language) && <option value={language}>{language}</option>}
              </select>
            </div>
          </div>
          <div>
            <label className="label" htmlFor="in-style">{t("inputs.style")}</label>
            <textarea
              id="in-style"
              rows={3}
              className="field resize-y leading-relaxed"
              placeholder={t("inputs.stylePlaceholder")}
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            />
          </div>
          <div className="flex min-h-0 flex-1 flex-col">
            <label className="label" htmlFor="in-lyrics">{t("inputs.lyrics")}</label>
            <textarea
              id="in-lyrics"
              rows={16}
              className="field min-h-[280px] flex-1 resize-y font-mono text-[0.82rem] leading-relaxed"
              placeholder={lyricsQ.isPending && project.inputs.lyrics ? t("inputs.lyricsLoading") : t("inputs.lyricsPlaceholder")}
              value={lyrics ?? ""}
              onChange={(e) => setLyrics(e.target.value)}
            />
            <InlineError error={lyricsQ.error} />
          </div>
        </div>
      </div>

      <div className="mt-8 flex flex-col gap-4">
        {project.stage.analysis ? (
          <>
            <AnalysisSummary projectId={project.id} />
            <div className="flex justify-end">
              <Button variant="ghost" onClick={() => navigate("../storyboard")}>{t("inputs.next")}</Button>
            </div>
          </>
        ) : (
          <Hint>
            <Trans k="inputs.hint" values={{ analyze: <b>{t("inputs.analyze")}</b>, jobs: <b>{t("jobs.title")}</b> }} />
          </Hint>
        )}
      </div>
    </div>
  );
}
