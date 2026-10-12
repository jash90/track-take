# suno-audio-wideo: plan wdrożenia

**Cel:** „Suno Studio dla wideo”. Bierzesz gotowy utwór z Suno (pełny miks, stemy, MIDI i tekst) i składasz na osi czasu teledysk poklatkowy (stop-motion). Renderuje go ComfyUI, a każde cięcie, zmiana klatki i akcent ruchu są przypięte do siatki rytmicznej utworu.

Data researchu: 2026-10-11. Źródła na końcu dokumentu.

---

## 0. Wybrane rozwiązanie (Twoje wejścia, Twój sprzęt)

**Ograniczenie:** liczy tylko to, co jest: **MacBook M1 Pro (32 GB)** albo **desktop-n0luht3**. Bez nowego sprzętu i bez wynajmowania GPU w chmurze.
**Wejście:** muzyka (jeden plik), tekst piosenki, okładka (kwadrat z Suno), styl teledysku wpisany słowami.
**Wyjście:** ten sam teledysk w **16:9 (1920×1080)** i **9:16 (1080×1920)**.

### 0.1 Główna decyzja: AI rysuje obrazy, renderer je animuje
Na tym sprzęcie nie wygenerujemy 3 minut wideo modelem Wan 2.2. Wersja 14B jest za ciężka i dla Maca, i dla GTX 970. Teledysk poklatkowy nie potrzebuje jednak 24 unikalnych klatek na sekundę, bo stop-motion to z definicji kilka rysunków na sekundę, przytrzymanych i poruszanych. Dlatego:
- **AI (ComfyUI na Macu) generuje tylko obrazy:**
  - klatki kluczowe, mniej więcej jedną na takt, a w refrenie gęściej;
  - ich warianty do „boilu”, czyli drgania charakterystycznego dla ręcznej animacji;
  - tło bez postaci oraz mapę głębi i maskę postaci.

  Na 3-minutowy utwór daje to około 400–500 obrazów zamiast ~4300 klatek wideo.
- **Ruch robi renderer: deterministyczny, bez AI, na CPU:**
  - parallax 2.5D z mapy głębi;
  - postać i tło jako osobne warstwy, poruszane jak lalki w wycinance;
  - ruchy kamery oraz drgnięcia na stopie i werblu;
  - przytrzymania na dwójkach lub trójkach i przejścia na bitach.

  Synchronizacja jest przez to dokładna co do klatki, a liczenie szybkie.
- **Prawdziwe wideo z AI tylko jako opcjonalny dodatek „na noc”:** kilka krótkich ujęć specjalnych, np. intro z okładki. Zrobi je mały model (Wan 2.2 TI2V-5B albo destylowane LTX-Video) w niskiej rozdzielczości, z upscalem. Faza 0 sprawdzi, czy na M1 Pro w ogóle się to opłaca.

### 0.2 Przepływ
```
muzyka  ─► analiza audio (Mac) ─► bity, downbeaty, sekcje, stemy, obwiednie
tekst   ─► wyrównanie do wokalu (Mac) ─► każde słowo z czasem
okładka ─► biblia stylu: paleta, opis świata i postaci, referencja stylu
styl (tekst) ─┐
              ├─► Reżyser (LLM) ─► TREATMENT (JSON): preset, kadencja, ujęcia per sekcja/linijka, prompty
              └─► Ty akceptujesz albo poprawiasz treatment
                        │
                        ▼
  ComfyUI na Macu (MPS): klatki kluczowe SDXL + IPAdapter (okładka) ─► warianty „boil”
                         ─► tło bez postaci (inpainting) ─► głębia + maska postaci ─► upscale 2×
                        │
                        ▼
  Renderer (Python + FFmpeg, Mac): plan rysunków na bitach, warstwy, parallax, kamera,
                                   przytrzymania, przejścia, napisy, audio
                        │
                        ├─► teledysk_16x9.mp4 (+ wersja bez napisów)
                        └─► teledysk_9x16.mp4 (+ wersja bez napisów)
```
Reżyser domyślnie korzysta z Claude API. To usługa tekstowa, a nie GPU, i potrzebuje tylko internetu i klucza. Wariant w pełni offline to lokalny LLM na Macu (Ollama) albo ręczna edycja treatmentu, kosztem jakości planu ujęć.

### 0.3 Tekst piosenki
- Tekst jest dany z góry, więc **nie transkrybujemy, tylko wyrównujemy** go do stemu wokalu. Narzędzie: `stable-ts` (`align()`), które działa na Macu bez CUDA, po polsku i po angielsku.
- Wynik służy do trzech rzeczy:
  - **Treść ujęć:** reżyser buduje obrazy z treści linijek.
  - **Cięcia:** wypadają na początkach fraz i na downbeatach.
  - **Napisy:** opcjonalne, w stylu karaoke.
- Napisy renderujemy **deterministycznie, nie przez AI**: FFmpeg + ASS (libass), podświetlanie słowa w momencie zaśpiewania (`\k`). Każdy format ma osobny layout:
  - 16:9 → dół, środek.
  - 9:16 → strefa bezpieczna: omijamy dolne ~20% i prawą krawędź, gdzie TikTok, Reels i Shorts kładą swoje przyciski.

### 0.4 Okładka jako kotwica wizualna
- **Paleta** (k-means na pikselach) trafia do promptów i do korekcji kolorów w renderze.
- **Opis świata i postaci** (LLM z vision) staje się częścią biblii stylu.
- **Referencja stylu** dla każdej klatki kluczowej: IPAdapter (SDXL) z okładką, opcjonalnie ControlNet. Cięższe modele edycji (Qwen-Image-Edit, FLUX Kontext) odpadają ze względu na czas na M1 Pro.
- **Intro:** „wejście w okładkę”, czyli zoom w okładkę plus kilka klatek img2img z rosnącym denoise od okładki do pierwszego ujęcia. To tanie, a wygląda jak przemiana.
- **Outro:** powrót do okładki + plansza końcowa.
- Miniatury pod YouTube i Shorts powstają z okładki i kadru z refrenu.

### 0.5 Styl wpisany słowami → preset
Reżyser mapuje wpisany tekst na najbliższy preset, a Ty widzisz, co wybrał, i możesz to zmienić. Słowa w stylu, które nie pasują do żadnego presetu, trafiają do promptu jako dodatkowy opis.

| Przykładowy styl | Tryb (sekcja 2.2) | Kadencja | Uwagi |
|---|---|---|---|
| wycinanka z papieru, kolaż | **E** (warstwy jak lalki) | na trójkach | najlepiej pasuje do tego sprzętu |
| plastelina, filc, lalki, claymation | **E** + boil, krótkie fragmenty **A** w refrenie | na dwójkach | LoRA stylu SDXL, jeśli jest dostępna |
| anime, komiks, rysunek tuszem | **E** + **A** | na dwójkach | lineart w ControlNet |
| kinowy, realistyczny | **E** z płynnym ruchem kamery 24 kl./s (parallax, Ken Burns), bez schodkowania | — | uczciwie: na tym sprzęcie bliżej „ożywionych zdjęć” niż filmu |
| glitch, VHS, abstrakcja, wizualizer | **D** + **E** | sterowane onsetami | prawie bez AI, najszybszy |

### 0.6 Dwa formaty z jednego zestawu obrazów
- **Master 1024×1024** to natywna rozdzielczość SDXL i kwadrat jak okładka. Po upscalu 2× (Real-ESRGAN, raz na obraz) daje 2048×2048.
- Z mastera powstają oba formaty: **16:9** to wycinek 2048×1152 przeskalowany do 1920×1080, a **9:16** to wycinek 1152×2048 przeskalowany do 1080×1920.
- Animacja jest składana z warstw w rendererze, więc **każdy format ma własny kadr i rozmieszczenie warstw**. W 9:16 postać stoi w centrum, w 16:9 widać więcej tła. Działa to bez żadnej dodatkowej generacji, bo tło bez postaci jest wygenerowane osobno.
- Ujęcia, w których kwadrat nie wystarcza, np. szeroka panorama w 16:9, dostają opcjonalnie outpainting tła do proporcji formatu. To jeden dodatkowy obraz na takie ujęcie.
- **Koszt AI jest jeden dla obu formatów.** Renderer i kodowanie biegną dwa razy, ale to minuty.
- Oba formaty dzielą **ten sam plan czasowy**: cięcia na tych samych klatkach, ten sam rytm.

### 0.7 Sprzęt: role maszyn
Sprawdzone 2026-10-11.

**MacBook M1 Pro: główna maszyna.** 16-rdzeniowe GPU, 32 GB pamięci wspólnej, macOS 26.6, wolne 76 GB dysku, są `ffmpeg`, `uv` i Homebrew.
- Uruchamia ComfyUI Desktop (Apple Silicon, MPS), aplikację, analizę audio, wyrównanie tekstu i renderer.
- Modele zajmą ~20–25 GB: SDXL + LoRA Lightning/Hyper, IPAdapter, ControlNet, Depth Anything V2, BiRefNet/RMBG do masek, Real-ESRGAN. Mieszczą się na dysku.
- Workflowy używają tylko node'ów działających na MPS: bez fp8, xformers i sageattention.

**desktop-n0luht3: opcjonalny pomocnik, domyślnie nieużywany.** Inwentaryzacja przez SSH z 2026-10-11:

| Element | Stan |
|---|---|
| System | Windows 11 Home 25H2 (build 26200) + WSL2 Ubuntu 24.04 (kernel 6.18, Python 3.12.3, docker, GPU widoczne w WSL) |
| Płyta / CPU | Gigabyte B760 GAMING X DDR4, BIOS F15 / Intel i5-13400F (10 rdzeni, 16 wątków, bez iGPU) |
| RAM | 4×32 GB DDR4-3600, 127,8 GB (maksimum płyty) |
| GPU | GTX 970 4 GB (Maxwell, compute 5.2), PCIe 3.0 x16, sterownik 560.94 |
| Dysk | 1 × NVMe 1 TB, **na C: wolne tylko 39 GB** (dysk WSL to plik na C:, więc 738 GB „wolnego” w WSL fizycznie nie istnieje) |
| Obciążenie | CPU 91%, load average w WSL ~35 na 16 wątkach (runnery CI), WSL zajmuje ~61 GB RAM, po stronie Windows wolne ~58 GB |
| Oprogramowanie | git, Docker Desktop (zatrzymany). Brak prawdziwego Pythona na Windows, ffmpeg i ComfyUI |

- **Nie nadaje się do modeli dyfuzyjnych:** ma 4 GB VRAM, brak szybkiego fp16, a nowe buildy PyTorch prawdopodobnie nie wspierają już Maxwella. 128 GB RAM nie zastąpi karty.
- **Mógłby robić postprocessing bez PyTorcha:** GTX 970 obsługuje Vulkan, więc działałyby upscale (Real-ESRGAN ncnn-vulkan) i interpolacja (RIFE ncnn-vulkan), a NVENC mógłby kodować wideo. Wsparcie NVENC do weryfikacji.
- **Ale:** CPU jest zajęty przez CI, a na dysku zostało 39 GB. Włączamy go jako worker postprocessingu dopiero wtedy, gdy faza 0 pokaże, że Mac nie wyrabia. Nie instalujemy na nim ComfyUI.

### 0.8 Budżet czasu (szacunki, zmierzymy w fazie 0)
3-minutowy utwór przy 120 BPM to około 90 taktów.

| Krok | Liczba obrazów | Czas na M1 Pro (szacunek) |
|---|---|---|
| Klatki kluczowe SDXL Lightning/Hyper 1024², IPAdapter | ~100–130 | ~10–25 s/obraz |
| Warianty „boil” (img2img, niski denoise) | ~200–260 | ~6–15 s/obraz |
| Tło bez postaci (inpainting) | ~100–130 | ~10–20 s/obraz |
| Głębia + maska + upscale 2× | ~400–500 | kilka s/obraz |
| Renderer + kodowanie, 2 formaty | 2 × 3 min | ~10–30 min |
| **Razem: render końcowy** | | **~2–4 h, czyli „na noc”** |
| **Animatik (szkic: 512², bez wariantów i teł)** | ~100 | **~15–30 min** |

### 0.9 Co to zmienia w zakresie
- **MVP = formularz + akceptacja treatmentu + automatyczny render** (tryby E, A, D). Edytor osi czasu w stylu Suno Studio przechodzi do etapu 2 (sekcja 7).
- **Lip-sync:** Wan S2V odpada, bo to model 14B. W etapie 2 zastąpi go klasyczny lip-sync z animacji wycinankowej: **Rhubarb Lip Sync** (offline, CPU, rozpoznawanie fonetyczne niezależne od języka) wyznacza kształty ust z wokalu, a renderer podmienia 6–9 wcześniej wygenerowanych kształtów ust postaci. Pasuje to do stylu stop-motion.
- **Tryby B/B′/C** (pełne wideo z AI) zostają w planie wyłącznie jako opcjonalne ujęcia specjalne albo na przyszłość, gdyby pojawiło się mocniejsze GPU.


---

## 1. Analiza Suno Studio

### 1.1 Czym jest Suno Studio (stan po aktualizacji z 8.10.2026)

| Wersja / data | Funkcje |
|---|---|
| **Studio 1.0** (25.09.2025) | Przeglądarkowa „generatywna stacja robocza audio”. Import sampli lub utworów z biblioteki, podział na stemy, generowanie wariantów stemów (wokal, perkusja, syntezatory) pasujących do istniejącego materiału. Wielościeżkowa oś czasu z kontrolą BPM, głośności i wysokości dźwięku. Eksport stemów jako audio lub MIDI. Tylko w planie Premier. |
| **Studio 1.2** (16.02.2026) | **Remove FX** (usuwa „wypalony” pogłos/delay), **Warp Markers** (ściągają rozjechane generacje z powrotem na siatkę), **metrum** inne niż 4/4, **Alternates** (warianty sekcji do podmiany bez utraty oryginału). |
| **Sounds** (27.01.2026) | One-shoty i pętle w wybranej tonacji i BPM, które można wrzucić do sesji Studio. |
| **Advanced Split** (11.06.2026) | Separacja stemu dla wybranego instrumentu z listy około 100. |
| **Studio 2.0** (13.08.2026) | MIDI na osi czasu (import, nagrywanie, edycja), syntezator wavetable, **chat bar** (generuje instrumenty i wokale, buduje wtyczki i presety, porządkuje sesję), efekty w czasie rzeczywistym (sidechain, pogłos splotowy), **krzywe automatyki**, nielimitowany eksport wielośladów i stemów (32-bit/48 kHz). |
| 2.09 / 17.09.2026 | Chat bar rozumie BPM, a jego zmiany można cofnąć. Przeciąganie wtyczek. Lepsza zamiana MIDI→audio. Import zewnętrznych plików MIDI. Zmiana nazw klipów przez czat. |
| 8.10.2026 | Lepsze wykrywanie „raz” (downbeatu) w nowych klipach, więc take'i trafiają w siatkę. **Rozciąganie klipów** do tempa (Shift+przeciągnięcie). Krzywe fade'ów wykładnicze i logarytmiczne. Okna, które można odpiąć. |

**Główne operacje generatywne:**
- **Extend**: kontynuacja od wybranego miejsca. Model bierze kilka ostatnich sekund jako kontekst i trzyma tonację oraz BPM.
- **Replace (sekcja)**: ponowne wygenerowanie zaznaczonego fragmentu z użyciem audio przed nim i po nim jako kontekstu, tak żeby nowa część łączyła się z obiema stronami.
- **Cover**: ta sama melodia, inne brzmienie.
- **Alternates / take'i**: kilka wersji jednej sekcji, przełączanych bez niszczenia oryginału.
- W praktyce każda generacja to losowanie od nowa. Kosztuje kredyty i zwykle wymaga 2–3 podejść.

**Czego brakuje:** publicznego, samoobsługowego API Suno. Jest program partnerski i doniesienia o `platform.suno.com`, ale bez potwierdzonej publicznej dokumentacji. Suno nie udostępnia też tekstu ze znacznikami czasu ani oficjalnego generatora teledysków; funkcja „Animate” podobno ma znak wodny i daje mało kontroli. Tę lukę wypełnia nasz produkt.

### 1.2 Przełożenie wzorców Suno Studio na narzędzie wideo

| Suno Studio (audio) | suno-audio-wideo (wideo) |
|---|---|
| Oś czasu ze ścieżkami, klipami, BPM i metrum | Oś czasu ze **ścieżkami audio** (miks i stemy) oraz **ścieżkami wideo** (ujęcia), z siatką: takty, bity, podziały i klatki |
| Wykrywanie downbeatu, przyciąganie do siatki | Analiza bitów, downbeatów i sekcji. Każde cięcie i klatka kluczowa przyciąga się do pozycji **bit→klatka** |
| Warp Markers | **Beat-warp**: przeliczenie czasu wygenerowanego klipu tak, żeby akcenty ruchu wypadały na bitach (time remap) |
| Rozciąganie klipu do tempa | **Conform**: rozciągnięcie klipu (np. 81 klatek przy 16 fps z Wan) do długości N taktów w fps projektu |
| Extend | **Extend shot**: następne ujęcie generowane z ostatniej klatki (lub ostatnich N klatek) poprzedniego |
| Replace (sekcja) | **Replace range**: ponowne wygenerowanie zakresu klatek, z klatkami po obu stronach jako warunkami brzegowymi (FLF2V) |
| Cover | **Restyle**: ten sam ruch (ControlNet depth/pose z take'a), nowy styl/LoRA/prompt |
| Alternates | **Take'i**: każda generacja to take ujęcia. Przełączasz aktywny i nic nie ginie |
| Stem split / Advanced Split | Import stemów z Suno albo lokalna separacja. Każdy stem **steruje własnymi parametrami obrazu** |
| Krzywe automatyki | **Ścieżki modulacji**: krzywe dla denoise, zoomu, kamery, wagi IPAdapter, siły LoRA. Rysowane ręcznie albo **sterowane dźwiękiem** (envelope follower, sidechain) |
| Kompresja sidechain | **Wizualny sidechain**: stopa → „pompowanie” zoomu, werbel → drgnięcie kamery, wokal → zbliżenie twarzy |
| Chat bar (rozumie BPM, zmienia nazwy klipów, buduje presety) | **Czat reżysera**: LLM z narzędziami edytującymi oś czasu (lista ujęć z tekstu i struktury, prompty, presety modulacji, masowe zmiany nazw) |
| Krzywe fade'ów (lin/exp/log) | Przejścia między ujęciami (cięcie, przenikanie, morf przez FLF2V, błysk na bicie) z krzywymi wygładzania |
| Eksport wielośladów/stemów do DAW | Eksport MP4/ProRes/sekwencji PNG plus **OpenTimelineIO/FCPXML/EDL** do DaVinci Resolve lub Premiere |
| Kredyty za generację | Budżet GPU-sekund na projekt, z wyceną przed każdym renderem |

---

## 2. Produkt: zakres i tryby

### 2.1 Wejście
Wymagane (sekcja 0):
1. **Muzyka**: jeden plik, WAV albo MP3. Stemy rozdzielamy lokalnie (demucs / audio-separator).
2. **Tekst piosenki**: wklejony tekst.
3. **Okładka**: obraz, zwykle kwadrat z Suno. Z niej powstaje biblia stylu.
4. **Styl teledysku**: wolny tekst, np. „plastelinowe stop-motion, nocne miasto, refren wybucha kolorem”.
5. **Formaty**: 16:9, 9:16 albo oba (domyślnie oba), plus profil jakości (sekcja 0.5).

Opcjonalne:
- **Stemy** z eksportu Suno Studio. Jeśli są, pomijamy separację i dostajemy lepszą jakość.
- **MIDI** ze Studio 2.0. Daje dokładne nuty, więc może wyzwalać zdarzenia precyzyjniej niż onsety z audio.
- **Dodatkowe referencje**, np. zdjęcie postaci.

Suno nie ma publicznego API, więc w MVP **użytkownik ręcznie importuje pliki wyeksportowane z Suno Studio**. Adapter `SunoSource` powstaje jako interfejs, żeby dało się podpiąć oficjalne API, gdy `platform.suno.com` okaże się działać. **Nie scrapujemy suno.com**: to łamie regulamin i jest kruche.

### 2.2 Tryby renderu ujęcia
| Tryb | Co daje | Pipeline w ComfyUI |
|---|---|---|
| **E. Klatki kluczowe + animacja warstw 2.5D** (główny tryb na tym sprzęcie) | Klatka kluczowa na takt lub frazę, warianty „boil”, postać i tło jako osobne warstwy. Ruch, parallax, kamera i akcenty na bitach składa renderer | SDXL + IPAdapter (okładka) → img2img z niskim denoise (warianty) → inpainting tła → Depth Anything V2 + BiRefNet/RMBG → upscale. Animacja poza ComfyUI (Python, NumPy/OpenCV) |
| **A. Stop-motion (klatka po klatce)** | Rysunki w tempie 8–12 unikalnych klatek/s („na dwójkach/trójkach”). Nowe rysunki wypadają na bitach i onsetach, a między nimi jest „boil”. Na M1 Pro tylko krótkie fragmenty (np. refren) | Łańcuch img2img (SDXL Lightning/Hyper) + IPAdapter/referencja + ControlNet z poprzedniej klatki. Transformacje kamery 2D/3D (w stylu Deforum) przed każdym krokiem |
| **B. Klatki kluczowe → animacja** (tylko ujęcia specjalne, patrz 0.1) | Płynny ruch między klatkami kluczowymi ustawionymi na downbeatach lub sekcjach | Klatki kluczowe z txt2img/edycji, potem **Wan 2.2 FLF2V** albo LTX first-last-frame między parami, potem beat-warp i conform |
| **B′. Stop-motion z wideo** (wymaga mocnego GPU, na tym sprzęcie tylko pojedyncze ujęcia) | Płynny wynik FLF2V **zeschodkowany** do 8–12 fps z przytrzymaniami i drobnym drganiem. Wygląda na ręczną animację, a przy tym jest spójny i trzyma rytm | B + post-proces „schodkowania” w rendererze |
| **C. Występ / lip-sync** | Śpiewająca postać zsynchronizowana z wokalem | Na tym sprzęcie: **Rhubarb Lip Sync** + podmiana wygenerowanych kształtów ust w rendererze (etap 2). Wan 2.2 S2V / LTX-2 tylko z mocnym GPU |
| **D. Efekty / wizualizer** | Efekty sterowane audio (glitch, VHS, błyski, aberracja chromatyczna) | Głównie proceduralnie w rendererze, bez AI. AnimateDiff + Yvann-Nodes / RyanOnTheInside opcjonalnie |

### 2.3 Poza zakresem MVP
SaaS, wielu użytkowników i rozliczenia; generowanie samej muzyki; aplikacja mobilna; tryb na żywo (VJ w czasie rzeczywistym).

---

## 3. Analiza audio (kręgosłup synchronizacji)

### 3.1 Pipeline analizy (Python)
| Krok | Narzędzie | Wynik |
|---|---|---|
| Dekodowanie, resampling do 44,1 kHz mono/stereo | `ffmpeg`, `soundfile` | znormalizowany WAV |
| Stemy (jeśli brak) | `demucs` (htdemucs_ft) albo `audio-separator` (BS/MelBand-RoFormer) | wokal/perkusja/bas/reszta |
| Bity + downbeaty | `beat_this` (CPJKU), awaryjnie `madmom` | `beats[]`, `downbeats[]` w sekundach |
| Struktura (intro/zwrotka/refren…) | `allin1` (bity, downbeaty, segmenty i etykiety w jednym modelu), awaryjnie `librosa` + segmentacja nowości przez `ruptures` | `sections[] {start,end,label}` |
| Onsety per stem | `librosa.onset` na perkusji (stopa/werbel/hi-hat rozdzielone pasmami), wokalu, basie | `onsets[stem][]` z siłą |
| Obwiednie | RMS, środek ciężkości widma, pasma (nisko/środek/góra), próbkowane **w fps projektu** | `envelope[stem][feature][frame]` |
| Wyrównanie tekstu | `WhisperX` na stemie wokalu albo wyrównanie wymuszone, gdy tekst jest podany | `words[] {t0,t1,text}`, `lines[]` |
| Kontrola tonacji/BPM | `essentia` (opcjonalnie) | `bpm`, `key`, krzywa tempa |
| MIDI (jeśli jest) | `mido` / `pretty_midi` | `notes[] {t,pitch,vel,track}` jako alternatywne źródło wyzwalaczy |

Wynik to `analysis.json`, wersjonowany hashem pliku audio, więc nic nie liczy się dwa razy.

### 3.2 Matematyka czas → klatka (jedno źródło prawdy)
- Projekt ma `fps` (domyślnie 24; także 12, 25, 30) i `sampleRate`.
- `frame(t) = round(t * fps)`. Wszystkie zdarzenia (bity, onsety, cięcia) przechowujemy w **sekundach** i kwantyzujemy do klatek dopiero przy renderze.
- Siatka: `takt → bit → podział (1/2, 1/4, triole) → klatka`. Przy zmiennym tempie (rzadkie w Suno, ale możliwe po edycjach w Studio) siatka pochodzi z listy `beats[]`, a nie ze stałego BPM.
- Ściąga: 120 BPM przy 24 fps = 12 klatek na bit i 48 klatek na takt 4/4. 128 BPM przy 24 fps = 11,25 klatki na bit, więc kumuluje się błąd zaokrąglenia. Zaokrąglanie każdego zdarzenia osobno z wartości w sekundach zapobiega dryfowi.
- **Kryterium akceptacji:** po 4 minutach każde cięcie leży w granicach ±1 klatki od wykrytego bitu. Pilnuje tego automatyczny test na syntetycznym metronomie.

### 3.3 Macierz modulacji (audio → parametry obrazu)
Modulacja to rekord `{ source, target, curve, range, smoothing, trigger? }`:
- `source`: `stem.feature` (np. `drums.kick.onset`, `vocals.rms`, `bass.low`, `midi.track2.note`, `section.change`, `lyrics.word`)
- `target`: parametr ujęcia albo globalny (`denoise`, `zoom`, `translate_x/y`, `rotate`, `ipadapter_weight`, `lora:<name>.strength`, `cfg`, `seed_jitter`, `frame_advance`, `prompt_weight:<token>`)
- `curve`: liniowa/wykładnicza/logarytmiczna/schodkowa, plus atak/zwolnienie (envelope follower, jak w kompresorze)
- tryb `trigger`: zdarzenie (onset) wyzwala impuls z obwiednią ADSR, np. stopa → zoom +6% wygasający przez 6 klatek.

Wbudowane presety: „Kick pump”, „Snare shake”, „Hat boil”, „Vocal close-up”, „Drop explosion”, „Verse calm”.

---

## 4. Algorytmy stop-motion i synchronizacji

### 4.1 Tryb A: planowanie „rysunków”
Dla każdego ujęcia liczymy listę klatek, na których pojawia się **nowy rysunek**:
1. Bazowa kadencja wg energii sekcji: spokojnie → na trójkach (8 fps), normalnie → na dwójkach (12 fps), drop → na jedynkach (24 fps).
2. **Wymuszone rysunki** na każdym bicie (oraz na onsetach stopy/werbla powyżej progu). Przytrzymania skracamy lub wydłużamy do najbliższego zdarzenia.
3. Na **downbeacie**: większa zmiana (wyższy denoise, skok kamery albo zmiana pozy z listy klatek kluczowych).
4. Na **granicy sekcji**: cięcie, nowe ujęcie, nowa klatka kluczowa.
5. Między rysunkami: przytrzymanie (ten sam obraz), opcjonalnie z „boilem” (drobne drganie/szum) co drugą klatkę dla ręcznie robionego efektu.

Generowanie jest sekwencyjne w obrębie ujęcia (każdy rysunek to img2img z poprzedniego) i równoległe między ujęciami i workerami GPU. Parametry każdego rysunku (denoise, transformacja, seed) pochodzą z macierzy modulacji próbkowanej w klatce tego rysunku.

### 4.2 Tryby B/B′: klatki kluczowe i beat-warp
1. Klatki kluczowe na downbeatach lub granicach sekcji (txt2img albo edycja z referencjami dla spójności).
2. FLF2V między kolejnymi klatkami kluczowymi. Wan 2.2 A14B daje około 81 klatek przy 16 fps (~5 s). Model 5B TI2V działa w 24 fps.
3. **Conform + beat-warp:** mapujemy klatki źródłowe na długość docelowego odcinka (N taktów) krzywą prędkości, która **przyspiesza w stronę bitu** i łagodnie zwalnia po nim. Realizacja przez wybór najbliższej klatki albo mieszanie, z RIFE przy spowalnianiu.
4. B′: próbkujemy wynik w dół do kadencji stop-motion (sekcja 4.1) i dodajemy przytrzymania oraz drganie.

### 4.3 Tryb E: animacja warstw w rendererze
1. Dla każdej klatki kluczowej mamy: obraz, warianty „boil”, tło bez postaci, mapę głębi i maskę postaci.
2. Renderer składa każdą klatkę wyjściową z warstw:
   - tło z parallaxem zależnym od głębi;
   - postać jako „lalka”: przesunięcie, obrót, skala i podskok na bicie, a dla stylu wycinanki także osobne części;
   - kamera: zoom, pan i drgnięcie z macierzy modulacji (sekcja 3.3).
3. Zmiana rysunku (wariant „boil” albo następna klatka kluczowa) następuje według planu rysunków z sekcji 4.1.
4. Kadr i rozmieszczenie warstw liczone są osobno dla 16:9 i 9:16 (sekcja 0.6).
5. Implementacja: NumPy/OpenCV (warp, alpha blending), wyjście jako strumień klatek do FFmpeg, bez zapisywania tysięcy PNG na dysk.

### 4.3a Tryb C: lip-sync (etap 2)
Na tym sprzęcie: **Rhubarb Lip Sync** wyznacza z wokalu i tekstu kształty ust (A–H, X). Wcześniej generujemy 6–9 wariantów ust postaci (inpainting obszaru ust), a renderer je podmienia, tak jak w klasycznej animacji wycinankowej. Wan 2.2 S2V (fragmenty po 77 klatek, conform do fps projektu) wymaga mocnego GPU, więc zostaje jako opcja na przyszłość.

### 4.4 Spójność (największe ryzyko jakościowe)
- Biblia stylu z obrazami referencyjnymi postaci i świata, podawanymi przez IPAdapter (SDXL). Flux Kontext / Qwen-Image-Edit tylko z mocniejszym GPU.
- Opcjonalny trening LoRA postaci (późniejsza faza).
- Stały seed na ujęcie z kontrolowanym drganiem.
- ControlNet (depth/lineart) z poprzedniej klatki w trybie A.
- Krok „wizualnego QA”, który porównuje embeddingi (CLIP/DINO) kolejnych klatek kluczowych i oznacza dryf.

---

## 5. Architektura systemu

```
┌──────────────────────── Aplikacja web (React + Vite + TS) ────────────────────┐
│ Transport (play, BPM, metrum, snap)     │ Podgląd (proxy, scrub)              │
│ Nagłówki ścieżek │ Oś: Miks | Stemy (waveformy+onsety) | Sekcje | Tekst     │
│                  │ Ścieżki wideo (ujęcia + filmstrip) | Ścieżki modulacji    │
│ Inspektor ujęcia (tryb, prompt, referencje, workflow, seed, take'i, modulacje)│
│ Czat reżysera (LLM z narzędziami)       │ Kolejka renderu / budżet GPU        │
└──────────────────────────────┬────────────────────────────────────────────────┘
                               │ REST + WebSocket (postęp, podglądy)
┌──────────────────────────────▼────────────────────────────────────────────────┐
│ API (Python 3.12, FastAPI, Pydantic v2)                                      │
│  ├─ projects  (project.json + assets/ na dysku, SQLite na indeks i zadania)  │
│  ├─ analysis  (sekcja 3, cache po hashu audio)                               │
│  ├─ planner   (sekcja 4: plan rysunków/klatek kluczowych, próbkowanie mod.)  │
│  ├─ director  (Anthropic API, narzędzia = operacje na osi czasu)             │
│  ├─ jobs      (kolejka: SQLite + asyncio w MVP, potem Redis/Arq; ponowienia) │
│  ├─ comfy     (klient: /upload, /prompt, /ws, /history, /view; wiele backend.)│
│  └─ render    (FFmpeg/PyAV: conform, schodkowanie, przytrzymania, przejścia, │
│                muxowanie audio)                                              │
└──────────────────────────────┬────────────────────────────────────────────────┘
                               │ HTTP + WS (workflowy w formacie API)
┌──────────────────────────────▼────────────────────────────────────────────────┐
│ ComfyUI Desktop na Macu (MPS). Klient obsługuje też inne backendy (CUDA,     │
│ Comfy Cloud), gdyby kiedyś pojawiło się mocniejsze GPU                       │
│ Custom nodes: VideoHelperSuite, KJNodes, IPAdapter, ControlNet-aux,          │
│ Frame-Interpolation (RIFE), Wan (natywny + opcjonalnie WanVideoWrapper),     │
│ Yvann-Nodes / RyanOnTheInside (tryb D), [własne: tracktake-nodes, opcjonalnie]  │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Integracja z ComfyUI: kluczowe decyzje
- **Workflowy jako szablony w formacie API** w `comfy/workflows/<id>/workflow_api.json` plus `bindings.yaml`. Bindingi mapują parametry logiczne (`prompt`, `init_image`, `denoise`, `seed`, `first_frame`, `last_frame`, `audio`, `frames`) na `node_id.inputs.name`. Podmiana modelu czy workflowu nie dotyka kodu backendu.
- **Klient ComfyUI** wysyła wejścia (`/upload/image`), zleca zadanie przez `POST /prompt` i nasłuchuje na `/ws?clientId=…` komunikatów `progress`, `executed`, `execution_success` i `execution_error`. Wyniki pobiera przez `/history/{id}` i `/view`. Comfy Cloud ma zgodne API (`/api/prompt`, `X-API-Key`), więc jeden klient obsługuje oba przypadki.
- **Wiele backendów** z harmonogramem: ujęcia rozdzielane na dostępne GPU. Heartbeat sprawdza każdy backend i wznawia pracę po restarcie ComfyUI.
- **Determinizm:** każdy take zapisuje pełny graf promptu, seed oraz wersje modeli i LoRA (hashe), więc da się go dokładnie odtworzyć.
- **Własne node'y (`tracktake-nodes`), opcjonalnie, od fazy 4:** tylko jeśli przekazywanie parametrów per rysunek przez API okaże się niewystarczające. Na przykład node, który przyjmuje JSON harmonogramu i zwraca wartości per klatka albo batche.

### 5.2 Sprzęt
Rozstrzygnięte w sekcji 0.7. Wszystko działa na Macu (M1 Pro): ComfyUI (MPS), aplikacja, analiza i renderer. Desktop jest opcjonalnym workerem postprocessingu. Klient ComfyUI jest wspólny, więc ewentualna zmiana backendu w przyszłości to zmiana konfiguracji, a nie kodu.

### 5.3 Model danych (skrót)
```ts
Project { id, name, fps, resolution, audio: AudioAssets, analysisId, styleBible, tracks: Track[], modulations: Modulation[], renders: Render[] }
AudioAssets { mix, stems: {name, path}[], midi?, lyrics? }
Track { id, kind: 'audio'|'video'|'section'|'lyrics'|'modulation', name, muted, clips: Clip[] }
Shot (Clip) { id, start: Time, end: Time, mode: 'stopmotion'|'animate'|'stepped'|'lipsync'|'loop',
              prompt, negative, refs: AssetId[], workflowId, params, seed,
              keyframes: { time, assetId }[], modulations: ModulationRef[],
              transitionIn: Transition, takes: Take[], activeTakeId }
Take { id, createdAt, graphHash, seed, frames: AssetId[] | videoAssetId, status, costGpuSec }
Time = { seconds: number }   // w UI przyciągany do siatki, przy renderze kwantyzowany do klatek
```
Projekt żyje jako folder (`project.json` + `assets/` + `takes/` + `cache/`), podobnie jak projekt w DAW. Ułatwia to kopie zapasowe, git-lfs i przenoszenie między maszynami.

### 5.4 Stack
- **Frontend:** React 19, Vite, TypeScript, Zustand (stan osi czasu z undo/redo przez historię komend), TanStack Query, Tailwind + shadcn/ui. Oś czasu rysowana na **canvasie** (własna, wirtualizowana), waveformy z `wavesurfer.js` v7 albo z wcześniej policzonych peaków (`audiowaveform`). Odtwarzanie przez WebAudio API z dokładnością do próbki, podgląd wideo synchronizowany z `AudioContext.currentTime`.
- **Backend:** Python 3.12 + `uv`, FastAPI, SQLModel/SQLite, httpx + websockets, librosa, beat_this, allin1, demucs/audio-separator, stable-ts, NumPy/OpenCV (renderer warstw), PyAV/FFmpeg, Real-ESRGAN, OpenTimelineIO.
- **Reżyser LLM:** Anthropic API (domyślnie `claude-sonnet-5-5`, `claude-opus-5-5` do pełnego planu całego teledysku), tool use z operacjami `create_shot`, `update_shot`, `set_modulation`, `split_at_section`, `rename_clips`, `estimate_cost`. Każda operacja LLM trafia do historii undo, jak w chat barze Suno.
- **Repo:** `apps/web`, `services/api`, `comfy/workflows`, `comfy/custom_nodes` (opcjonalnie), `tests/`, `docs/`. pnpm workspace + uv.

---

## 6. UI/UX (wzorowane na Suno Studio)

**MVP (etap 1), formularz:** muzyka + tekst + okładka + pole „styl teledysku” + wybór formatów → animatik i podgląd treatmentu (lista ujęć z miniaturami klatek kluczowych, osobno dla 16:9 i 9:16) → „Renderuj” → postęp → dwa pliki MP4 do pobrania.

**Etap 2, edytor osi czasu:**

1. **Import** → przeciągasz WAV/stemy/MIDI/tekst → automatyczna analiza (pasek postępu) → pojawia się oś czasu z etykietami sekcji.
2. **Reżyser** → „Zrób stop-motion, filcowa postać, nocne miasto, refren wybucha kolorem” → LLM proponuje **listę ujęć** (jedno na sekcję lub frazę), prompty i presety modulacji. Użytkownik akceptuje albo poprawia.
3. **Animatik** (szybki szkic): niska rozdzielczość, szybkie modele (Lightning/destylowane), tylko klatki kluczowe przytrzymywane na bitach. Rytm całego teledysku widać po kilku minutach.
4. **Iteracja per ujęcie:** Generate / Extend / Replace range / Restyle → take'i → wybór najlepszego.
5. **Render końcowy:** pełna rozdzielczość, szacowany czas renderu na Macu, kolejka, postęp, podgląd gotowych ujęć.
6. **Eksport:** MP4 (H.264/H.265), ProRes 422, sekwencja PNG, OTIO/FCPXML ze stemami → wykończenie w Resolve.

Skróty jak w DAW: spacja = play, S = podział w miejscu kursora, ⌘D = duplikat ujęcia, Shift+przeciągnięcie = conform/rozciągnięcie, Alt+przeciągnięcie = kopia, przełącznik przyciągania (takt/bit/1/2/klatka/wył.).

---

## 7. Fazy wdrożenia (każda kończy się działającym przyrostem)

### ETAP 1: automatyczny teledysk (MVP)

#### Faza 0: spike techniczny (≈1 tydzień)
- [ ] ComfyUI Desktop na Macu: SDXL + LoRA Lightning/Hyper, IPAdapter Plus, ControlNet (lineart/depth), Depth Anything V2, BiRefNet/RMBG, Real-ESRGAN. Sprawdzenie, czy wszystkie node'y działają na MPS.
- [ ] Skrypt Python na Macu: Twój utwór → demucs + beat_this + allin1 → `analysis.json`. Tekst → `stable-ts` → słowa z czasem.
- [ ] Skrypt: okładka → 8 klatek kluczowych w stylu okładki + warianty „boil” + tła + głębia/maski przez API ComfyUI.
- [ ] Prototyp renderera trybu E: warstwy, parallax, kamera, przytrzymania na bitach.
- [ ] **Dowód:** 30 s refrenu w trybie E, osobno 16:9 i 9:16, cięcia na downbeatach, napisy karaoke, audio.
- [ ] Pomiar czasu na obraz (keyframe, wariant, inpaint, upscale) na M1 Pro. Opcjonalnie test jednego 3-sekundowego klipu Wan 2.2 5B / LTX-Video. **Wyjście:** synchronizacja ±1 klatka, liczby w `docs/benchmarks.md`, potwierdzony albo skorygowany budżet z sekcji 0.8.

#### Faza 1: analiza audio i tekstu (≈1–1,5 tygodnia)
- [ ] Szkielet FastAPI, model projekt-jako-folder, endpointy `analysis` z cache.
- [ ] Wyrównanie tekstu PL/EN, fallback na transkrypcję, gdy wyrównanie ma niską pewność.
- [ ] Testy jednostkowe matematyki czas→klatka (syntetyczny metronom 90/120/128/174 BPM, metrum 3/4 i 6/8).

#### Faza 2: orkiestracja ComfyUI (≈1,5 tygodnia)
- [ ] Klient ComfyUI (lokalny na Macu; interfejs gotowy na inne backendy), rejestr szablonów z `bindings.yaml` walidowanym względem `/object_info`.
- [ ] Kolejka zadań z ponawianiem, anulowaniem i wznawianiem. Metadane take'a (hash grafu, seed, wersje modeli).
- [ ] Szablony: `keyframe_from_ref`, `boil_variant`, `bg_inpaint`, `depth_and_mask`, `outpaint_to_aspect`, `img2img_step`, `upscale`.

#### Faza 3: okładka, styl i reżyser (≈1,5 tygodnia)
- [ ] Biblia stylu z okładki: paleta, opis vision, referencja.
- [ ] Mapowanie stylu na preset (sekcja 0.5) + treatment JSON z ujęciami per sekcja/linijka i szacowanym czasem renderu na Macu.
- [ ] Walidacja treatmentu przez schemat Pydantic. Ponowienie, gdy LLM zwróci błędny JSON.

#### Faza 4: silnik renderu i dwa formaty (≈2 tygodnie)
- [ ] Tryb E (sekcja 4.3) i krótkie fragmenty A (sekcja 4.1), przytrzymania, boil, efekty D.
- [ ] Osobny kadr i rozmieszczenie warstw dla 16:9 i 9:16 (sekcja 0.6), outpainting tła tam, gdzie kwadrat nie wystarcza.
- [ ] Animatik (512², bez wariantów) jako szybki podgląd przed renderem „na noc”. Render wznawialny po przerwie (np. zamknięcie klapy).
- [ ] Napisy ASS z osobnym layoutem per format, intro i outro z okładki, eksport MP4 z napisami i bez.

#### Faza 5: aplikacja web: formularz i podgląd treatmentu (≈1,5 tygodnia)
- [ ] Upload (muzyka, tekst, okładka), pole stylu, formaty.
- [ ] Podgląd treatmentu: lista ujęć z miniaturami w obu kadrach, edycja promptu i ponowne wygenerowanie klatki kluczowej, akceptacja.
- [ ] Postęp renderu na żywo, pobranie plików. Test E2E: 3-minutowy utwór → dwa MP4.

**Estymacja etapu 1:** ~9–10 tygodni dla jednej osoby. Pierwszy widoczny efekt po fazie 0 (≈1 tydzień).

### ETAP 2: edytor w stylu Suno Studio (≈6–8 tygodni)
- [ ] Oś czasu na canvasie: audio, stemy, sekcje, tekst, ujęcia, przyciąganie do siatki. Transport z WebAudio, scrub.
- [ ] Take'i, Extend / Replace range / Restyle, undo/redo.
- [ ] Ścieżki modulacji (rysowane ręcznie i sterowane audio) z presetami.
- [ ] Czat reżysera jako narzędzia edytujące oś czasu (z diffem i undo).
- [ ] Tryb C (lip-sync: Rhubarb + kształty ust), QA dryfu, opcjonalny trening LoRA postaci (na M1 Pro powolny, do sprawdzenia).
- [ ] Eksport OTIO/FCPXML do Resolve/Premiere.

---

## 8. Ryzyka i sposoby ich ograniczenia

| Ryzyko | Wpływ | Ograniczenie |
|---|---|---|
| Czas renderu na M1 Pro | Wysoki | AI generuje tylko ~400–500 obrazów (tryb E), ruch robi renderer. Animatik przed renderem, LoRA Lightning/Hyper, render „na noc” z wznawianiem. Desktop jako worker postprocessingu, jeśli trzeba |
| Ograniczenia MPS (brak fp8/xformers, część node'ów tylko na CUDA) | Średni | Tylko sprawdzone na MPS node'y, lista w `comfy/requirements.lock`, test w fazie 0 |
| Styl „kinowy” na tym sprzęcie | Średni | Uczciwie komunikowane w presecie: efekt „ożywionych zdjęć” (parallax + kamera), a nie pełne wideo AI |
| Mało miejsca na dysku (Mac: 76 GB, desktop: 39 GB) | Średni | Modele ~20–25 GB, renderer streamuje klatki prosto do FFmpeg zamiast zapisywać PNG, czyszczenie cache po eksporcie |
| Dryf postaci i stylu między ujęciami | Wysoki | Biblia stylu, IPAdapter z okładką, stały seed, warianty „boil” z niskim denoise od wspólnej klatki kluczowej, QA dryfu |
| Brak publicznego API Suno | Średni | Ręczny import eksportów ze Studio. Adapter `SunoSource` gotowy na oficjalne API. Bez scrapowania |
| Zmiany wersji ComfyUI i custom node'ów | Średni | Przypięte wersje (hashe commitów) w `comfy/requirements.lock`, walidacja szablonów względem `/object_info` przy starcie |
| Trudna instalacja (`allin1` wymaga madmom/natten) | Średni | Rozwiązania awaryjne (librosa+ruptures), `stable-ts` zamiast WhisperX (bez CUDA) |
| Wykrywanie bitów zawodzi na utworach bez wyraźnego rytmu | Niski/średni | Ręczne tap-tempo, edycja bitów na osi czasu (jak Warp Markers), MIDI jako źródło prawdy |
| Prawa: utwory z Suno i licencje modeli | Średni | Komercyjne użycie utworów z Suno wymaga płatnego planu. Sprawdzić licencje Wan (Apache-2.0), LTX i Hunyuan przed użyciem komercyjnym |

---

## 9. Decyzje i otwarte pytania

**Rozstrzygnięte:**
- Wejście: muzyka, tekst, okładka i styl wpisany słowami.
- Wyjście: 16:9 i 9:16, 1080p.
- Wygląd: wybierany stylem z mapowaniem na preset (sekcja 0.5).
- Sprzęt: tylko to, co jest. Główna maszyna to Mac M1 Pro, desktop jest opcjonalnym pomocnikiem (sekcja 0.7). Bez chmury GPU.
- Architektura: AI generuje obrazy, ruch składa renderer (tryb E, sekcja 0.1).

**Do potwierdzenia:**
1. **Reżyser:** Claude API (wymaga internetu i klucza) czy w pełni offline (lokalny LLM na Macu, słabszy plan ujęć)? Zakładam Claude API.
2. **Produkt:** narzędzie dla siebie czy później SaaS dla innych twórców? Na razie zakładam narzędzie dla siebie.
3. **Napisy:** domyślnie włączone w 9:16 i wyłączone w 16:9? Zakładam, że tak, a oba warianty i tak są eksportowane.
4. **Typowa długość utworu:** zakładam 2–4 minuty. To wpływa na wycenę i czas renderu.

---

## Źródła
- Release notes Suno: https://suno.com/release-notes
- Suno Studio 2.0 (MusicTech): https://musictech.com/news/gear/suno-studio-2-0-upgrade-new-features/
- Przewodnik po Suno Studio 2026 (Extend/Replace/Cover/eksport): https://www.slstudio.pro/blog/suno-studio-guide-2026
- Status API Suno: https://www.musicbusinessworldwide.com/suno-explores-developer-api-seeking-apps-that-unlock-experiences-generative-music-makes-possible-for-the-first-time/ , https://aireiter.com/blog/does-suno-have-an-api
- ComfyUI audio-reactive: https://github.com/yvann-ba/ComfyUI_Yvann-Nodes , https://github.com/ryanontheinside/ComfyUI_RyanOnTheInside , https://github.com/lum3on/ComfyUI_AudioTools
- Wan 2.2 S2V: https://docs.comfy.org/tutorials/video/wan/wan2-2-s2v
- Wan 2.2 FLF2V: https://blog.comfy.org/p/wan22-flf2v-comfyui-native-support , https://github.com/Well-Made/ComfyUI-Wan-SVI2Pro-FLF
- LTX-2 audio-to-video: https://comfy.org/workflows/video_ltx_2_audio_to_video-5697ddf9182f/
- Porównanie modeli 2026: https://www.aimagicx.com/blog/open-source-ai-video-models-comparison-2026
- API serwera/chmury ComfyUI: https://github.com/comfy-org/docs (development/comfyui-server/comms_routes, development/cloud/api-reference)
