# Faza 0: pomiary (2026-10-11)

Sprzęt: MacBook M1 Pro (16-rdzeniowe GPU, 32 GB), macOS 26.6, ComfyUI 0.39.0 (MPS), PyTorch 2.14.1.
Warunki: **duże obciążenie pamięci**. Swap zajęty w 21,7 z 23,5 GB; Docker Desktop (~22 GB), voicemode/whisper i inne aplikacje działały w tle. Wszystkie czasy AI są przez to zawyżone.

Utwór testowy: „Where the Silence Hurts – A” (Suno, 4:29, 81 BPM), tekst z tagu ID3, okładka 360×360.

## Analiza audio i tekstu (`tracktake analyze`)
| Krok | Czas | Metoda |
|---|---|---|
| Stemy | 36,6 s | demucs htdemucs (MPS) |
| Bity + downbeaty | 3,4 s | beat_this final0 (MPS) |
| Wyrównanie tekstu | 41,0 s | stable-ts `align()` + MLX whisper large-v3 |
| Cechy (obwiednie, onsety) | 7,0 s | librosa |
| **Razem** | **88 s** (z cache stemów ~60 s) | |

Wynik: 81,08 BPM, 361 bitów, 90 downbeatów, 16 sekcji z tagów Suno. Pierwsze słowo na 14,76 s.

## Generowanie obrazów: Z-Image Turbo Q4 GGUF, 8 kroków
| Wariant | Czas |
|---|---|
| txt2img 1024², pierwszy (z ładowaniem modelu) | 422 s |
| txt2img 1024², kolejny | 375 s |
| img2img z okładki, denoise 0,55 | 297 s |
| txt2img 768² | 408 s |
| 11 assetów dowodu (5 teł + 6 wycinanek z BiRefNet) | średnio **316 s/obraz** (258–401 s) |

Obraz 768² trwał tyle samo co 1024², więc wąskim gardłem jest swap modelu, a nie obliczenia. Krok samplera trwał 32–50 s. Szacunek bez obciążenia pamięci: ~10–15 s na krok, czyli **~1,5–2 min na obraz**. Do potwierdzenia po zwolnieniu RAM-u.

Qwen-Image 2.1 (referencje obrazów) nie był mierzony: przy tym stanie pamięci 25 kroków większego modelu byłoby niepraktyczne.

## Render (tryb E, warstwy 2.5D + napisy, VideoToolbox H.264)
| Format | Klatki | Rysunki | Czas | Wolniej niż czas rzeczywisty |
|---|---|---|---|---|
| 16:9 1920×1080 | 703 (29,3 s) | 342 | 45 s | 1,5× |
| 9:16 1080×1920 | 703 (29,3 s) | 342 | 45 s | 1,5× |

## Dowód: build-up + refren 1 (47,06–76,34 s)
- Pierwszy przebieg (11 assetów + render): **64 min** (18:55:48 → 19:59:48).
- Poprawione tło `dance`: 4,5 min. Render po poprawce układu: 1,5 min.
- **Łącznie z poprawkami: ~72 min** na 30 s teledysku. Około 95% tego czasu to generowanie obrazów AI.

## Prognoza dla całej piosenki (4:29)
| Etap | Przy obecnym RAM-ie | Bez obciążenia pamięci (szacunek) |
|---|---|---|
| Analiza | 1,5 min | 1,5 min |
| ~8 teł + ~20 póz = ~28 obrazów | ~2,5 h | ~45–55 min |
| Render 2 formatów | ~14 min | ~10 min |
| **Razem** | **~2,8 h** | **~1–1,2 h** |

Biblioteka assetów skaluje się z liczbą lokacji i póz, a nie z długością utworu. Kolejne ujęcia to nowe kombinacje tła, pozy i kamery, bez nowych obrazów AI.

# Pełny teledysk (2026-10-11): czasy i koszty

Utwór 4:29, 45 ujęć, 2 formaty. Klatki z Codex (90 + karta postaci), klipy Wan 2.2 14B (fp8, 4 kroki, 832×480)
na 4× RTX 4090 (Vast.ai), render na Macu.

| Etap | Czas |
|---|---|
| Klatki Codex, 4 równolegle | 26 min (90/90, 0 błędów) |
| Klatki ComfyUI Z-Image (porównanie), 4× RTX 4090 | ~3 min (~6–7 s/obraz) |
| Klipy Wan 2.2 (zestaw Codex), 4× RTX 4090 | 28 min (~70–90 s/klip, 81 klatek) |
| Render 16:9 + 9:16 na Macu | ~6 min / format |

## Rachunek Vast.ai (z faktur)
| Pozycja | USD |
|---|---|
| Pobieranie modeli (~60 GB / kartę) | 6,72 |
| GPU | 1,55 |
| Dysk | 0,22 |
| Wysyłanie | 0,20 |
| **Razem** | **8,69** |

Hosty brały za pobieranie od 0,004 do 0,039 $/GB; trzy drogie hosty to 6,25 $ z 6,72 $.
Od teraz: filtr `inet_down_cost <= 0.006`, koszt pobrania modeli liczony w cenie oferty,
a do samych klipów pobierany jest tylko Wan (~38 GB zamiast ~60 GB).
Ta sama praca na tanich hostach: **~2,3 $**; samo GPU za cały teledysk: **~1,35 $**.
Codex: 0 $ ekstra (w ramach subskrypcji ChatGPT, wlicza się w limity planu).
