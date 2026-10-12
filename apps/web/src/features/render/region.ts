import type { Key, TFn } from "../../i18n";

export const DEFAULT_REGION = "US";
export const REGIONS: { value: string; label: Key }[] = [
  { value: "US", label: "region.US" },
  { value: "US,CA", label: "region.USCA" },
  { value: "any", label: "region.any" },
];

const norm = (r: string | undefined) => (r ?? DEFAULT_REGION).replace(/\s+/g, "").toUpperCase();

/** Canonical value for the select ("any" stays lowercase). */
export function regionValue(r: string | undefined): string {
  const n = norm(r);
  return n === "ANY" ? "any" : n;
}

/** One short line under the preset cards. */
export function regionLine(r: string | undefined, t: TFn): string {
  const v = regionValue(r);
  if (v === "US") return t("region.line.US");
  if (v === "US,CA" || v === "CA,US") return t("region.line.USCA");
  if (v === "any") return t("region.line.any");
  return t("region.line.other", { list: v });
}
