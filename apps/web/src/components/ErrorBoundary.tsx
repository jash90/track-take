import { Component, useEffect, type ErrorInfo, type ReactNode } from "react";
import { useRouteError } from "react-router";

// Reports a browser-side error to the server log (data/client_errors.log), so crashes can be diagnosed later.
export function reportClientError(error: unknown, extra: Record<string, string> = {}): void {
  const e = error instanceof Error ? error : new Error(String(error));
  const body = JSON.stringify({ message: e.message, stack: e.stack ?? "", url: location.href, ...extra });
  try {
    navigator.sendBeacon?.("/api/client-error", new Blob([body], { type: "application/json" })) ||
      void fetch("/api/client-error", { method: "POST", headers: { "Content-Type": "application/json" }, body });
  } catch {
    /* reporting must never throw */
  }
}

const TEXT = {
  pl: { title: "Coś poszło nie tak", lead: "Ten widok napotkał błąd. Dane projektu są bezpieczne, a zadania w tle działają dalej.", retry: "Spróbuj ponownie", reload: "Odśwież stronę", details: "Szczegóły" },
  en: { title: "Something went wrong", lead: "This view hit an error. Your project data is safe and background jobs keep running.", retry: "Try again", reload: "Reload page", details: "Details" },
};

function lang(): "pl" | "en" {
  try {
    const saved = localStorage.getItem("tracktake.lang");
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    /* storage may be unavailable */
  }
  return navigator.language.toLowerCase().startsWith("pl") ? "pl" : "en";
}

type State = { error: Error | null };

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportClientError(error, { componentStack: info.componentStack ?? "" });
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return <ErrorView error={error} onRetry={() => this.setState({ error: null })} />;
  }
}

// A render error inside a route is caught by the router before our boundary: same screen, same report.
export function RouteError() {
  const raw = useRouteError();
  const error = raw instanceof Error ? raw : new Error(String((raw as { statusText?: string })?.statusText ?? raw));
  useEffect(() => reportClientError(error, { source: "route" }), [error]);
  return <ErrorView error={error} onRetry={() => location.reload()} />;
}

function ErrorView({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const t = TEXT[lang()];
  return (
    <div className="mx-auto mt-24 max-w-xl rounded-xl border border-white/10 bg-white/[0.03] p-8 text-left">
      <h1 className="font-display text-3xl">{t.title}</h1>
      <p className="mt-3 text-sm opacity-75">{t.lead}</p>
      <div className="mt-6 flex gap-3">
        <button type="button" className="rounded-lg bg-[#ff5a3c] px-4 py-2 text-sm font-semibold text-black"
          onClick={onRetry}>{t.retry}</button>
        <button type="button" className="rounded-lg border border-white/15 px-4 py-2 text-sm"
          onClick={() => location.reload()}>{t.reload}</button>
      </div>
      <details className="mt-6 text-xs opacity-60">
        <summary className="cursor-pointer">{t.details}</summary>
        <pre className="mt-2 whitespace-pre-wrap break-all">{error.message}{"\n"}{error.stack}</pre>
      </details>
    </div>
  );
}
