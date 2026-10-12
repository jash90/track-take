import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import type { Project, ProjectSettings } from "../../api/types";
import { useToast } from "../../components/Toaster";
import { useT, type Key } from "../../i18n";
import { errorMessage } from "../../lib/format";

/** Optimistic PATCH of project settings (partial merge); reverts and toasts on failure. */
export function useSaveSettings(project: Project, errorKey: Key) {
  const qc = useQueryClient();
  const toast = useToast();
  const t = useT();
  const key = qk.project(project.id);
  return useMutation({
    mutationFn: (patch: Partial<ProjectSettings>) => api.patchProject(project.id, { settings: patch }),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<Project>(key);
      if (prev) qc.setQueryData<Project>(key, { ...prev, settings: { ...prev.settings, ...patch } });
      return { prev };
    },
    onError: (err, _patch, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      toast(t(errorKey, { error: errorMessage(err) }), "err");
    },
    onSuccess: (p) => {
      qc.setQueryData(key, p);
      void qc.invalidateQueries({ queryKey: qk.projects });
    },
  });
}
