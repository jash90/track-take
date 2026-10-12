import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/instrument-serif";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/jetbrains-mono";
import "./index.css";
import { App } from "./App";
import { ErrorBoundary, reportClientError } from "./components/ErrorBoundary";

const root = document.getElementById("root");
if (!root) throw new Error("#root missing");
window.addEventListener("error", (e) => reportClientError(e.error ?? e.message, { kind: "window.error" }));
window.addEventListener("unhandledrejection", (e) => reportClientError(e.reason, { kind: "unhandledrejection" }));

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
