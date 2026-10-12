import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "./api/client";
import { createBrowserRouter, Navigate, RouterProvider, useParams } from "react-router";
import { AppShell } from "./components/AppShell";
import { Toaster } from "./components/Toaster";
import { ProjectsPage } from "./features/projects/ProjectsPage";
import { WorkspacePage, WorkspaceIndex } from "./features/workspace/WorkspacePage";
import { InputsStep } from "./features/inputs/InputsStep";
import { StoryboardStep } from "./features/storyboard/StoryboardStep";
import { KeysStep } from "./features/keys/KeysStep";
import { RenderStep } from "./features/render/RenderStep";
import { ResultStep } from "./features/result/ResultStep";
import { NotFound } from "./components/NotFound";
import { RouteError } from "./components/ErrorBoundary";
import { I18nProvider } from "./i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: true,
      // client errors (4xx) are answers, not glitches — don't hammer the backend with retries
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
});

const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { path: "/", element: <ProjectsPage /> },
      {
        path: "/p/:id",
        element: <WorkspacePage />,
        children: [
          { index: true, element: <WorkspaceIndex /> },
          { path: "wejscie", element: <InputsStep /> },
          { path: "storyboard", element: <StoryboardStep /> },
          { path: "klatki", element: <KeysStep /> },
          { path: "wideo", element: <RenderStep /> },
          { path: "wynik", element: <ResultStep /> },
          { path: "*", element: <ToInputs /> },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function App() {
  return (
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <Toaster>
          <RouterProvider router={router} />
        </Toaster>
      </QueryClientProvider>
    </I18nProvider>
  );
}

// an unknown step: back to the first one; absolute, because a relative target would nest under the bad path forever
function ToInputs() {
  const { id = "" } = useParams();
  return <Navigate to={`/p/${encodeURIComponent(id)}/wejscie`} replace />;
}
