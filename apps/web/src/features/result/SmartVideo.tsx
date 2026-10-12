import { useState, type Ref, type VideoHTMLAttributes } from "react";
import { useT } from "../../i18n";

interface Props extends Omit<VideoHTMLAttributes<HTMLVideoElement>, "src"> {
  /** Tried in order; the next one is used when the browser cannot decode the current (e.g. HEVC preview in Chromium). */
  sources: Array<string | null | undefined>;
  ref?: Ref<HTMLVideoElement>;
}

export function SmartVideo({ sources, ref, className, ...rest }: Props) {
  const list = sources.filter((s): s is string => !!s);
  const key = list.join("|");
  return <Inner key={key} list={list} videoRef={ref} className={className} {...rest} />;
}

function Inner({ list, videoRef, className, ...rest }: Omit<Props, "sources" | "ref"> & { list: string[]; videoRef?: Ref<HTMLVideoElement> }) {
  const [i, setI] = useState(0);
  const t = useT();
  const failed = i >= list.length;
  return (
    <div className="relative">
      <video
        ref={videoRef}
        src={failed ? undefined : list[i]}
        onError={() => setI((n) => n + 1)}
        className={className}
        {...rest}
      />
      {i > 0 && !failed && (
        <span className="pointer-events-none absolute left-2 top-2 rounded bg-ink-950/80 px-2 py-0.5 font-mono text-[0.62rem] text-warn">
          {t("video.hevcFallback")}
        </span>
      )}
      {failed && (
        <span className="absolute inset-0 grid place-items-center p-4 text-center text-[0.8rem] text-ink-400">
          {t("video.unplayable")}
        </span>
      )}
    </div>
  );
}
