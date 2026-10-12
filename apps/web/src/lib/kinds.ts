/** Muted, filmic colours per section kind (intro|verse|pre_chorus|chorus|build|break|bridge|breakdown|outro|other). */
const KIND_COLORS: Record<string, string> = {
  intro: "#56687a",
  verse: "#6c7d55",
  pre_chorus: "#937d47",
  chorus: "#b4553c",
  build: "#a06b35",
  break: "#4c5d68",
  bridge: "#735e8a",
  breakdown: "#3f6f6c",
  outro: "#5f5868",
  other: "#5a534c",
};

const KIND_LABELS: Record<string, string> = {
  intro: "Intro",
  verse: "Zwrotka",
  pre_chorus: "Przedrefren",
  chorus: "Refren",
  build: "Narastanie",
  break: "Przerwa",
  bridge: "Bridge",
  breakdown: "Breakdown",
  outro: "Outro",
  other: "Inne",
};

export function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? KIND_COLORS.other ?? "#5a534c";
}

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}
