# GTA6_PROJET_MONTAGE

Projet de montage complet (reproductible) de la vidéo YouTube **GTA 6 : l'attente touche à sa fin**.
Tout le montage est décrit en code : narration, découpage, timeline, sound design, musique, rendu.

| Livrable | Emplacement |
|---|---|
| Vidéo finale (1920×1080, 30 i/s, H.264 + AAC 320k, −14 LUFS) | `../GTA6_VIDEO_FINALE.mp4` |
| Script voix off (numéroté, minuté) | `../GTA6_VOIX_OFF.txt` |
| Timeline détaillée (plans, transitions, sous-titres, SFX, musique) | `../GTA6_TIMELINE.txt` |
| Projet de montage | ce dossier |

## Inventaire des médias (vérifié avant rendu → `build/media_report.json`)

| Catégorie | Contenu | État |
|---|---|---|
| Images GTA 6 | 14 personnages, 5 lieux, 6 Ultimate Edition, 12 Vintage Vice City Pack (4K) | 36/36 OK |
| Clips vidéo GTA 6 | reveal logo/cover (16 s) + 8 clips personnages (1–1,5 s) | 9/9 OK |
| Enregistrements PS5 | **absents** | remplacés par un habillage graphique (voir plus bas) |
| Sons / musiques | **absents** | tout est synthétisé dans `audio.py` (aucune musique commerciale) |
| Voix off | **absente** | voix de travail TTS (voir plus bas) |

## Adaptations aux ressources manquantes

- **Voix off** : aucune prise fournie. Une voix de travail est générée localement avec le TTS neuronal
  Kokoro (voix française `ff_siwis`). Elle sert de guide de rythme : enregistrez votre voix (une prise par
  ligne, `voice_user/LINE_01.wav` …, numéros dans `GTA6_VOIX_OFF.txt`) puis
  `python build.py --skip-assets --user-voice voice_user` : le montage entier se recale sur vos durées.
- **Captures PS5** : la section « téléchargement » utilise un habillage motion design du préchargement
  (illustration, sans imitation de l'interface Sony). Déposez vos vraies captures dans `ps5_captures/`
  (`boot.mp4`, `page.mp4`, `dl.mp4`, `done.mp4`, `locked.mp4`) : elles remplacent automatiquement l'habillage.
- **Musique / SFX** : 7 ambiances originales (synthwave / Vice City) et 18 effets sonores synthétisés.
- Aucune séquence de gameplay n'est fabriquée : seuls les visuels officiels fournis sont utilisés. La
  narration précise que le créateur n'a pas encore joué au jeu.

## Pipeline

```
assets.py      vérification + préparation des médias, détourage IS-Net, inpainting du décor, ralentis ×3 interpolés
tts.py         voix off (TTS ou vos prises) → durées par phrase
narration.py   script + découpage visuel + sous-titres + SFX (source de vérité éditoriale)
timeline.py    EDL : temps de chaque plan, transitions, sous-titres, SFX → build/edl.json
audio.py       SFX, 7 musiques, ambiances urbaines, mixage avec ducking → build/audio/MIX.wav (+ stems)
fx.py          caméra virtuelle, parallaxe 2.5D, textes 3D, cartes, étalonnage Vice City, grain
render.py      rendu des plans et transitions, image par image
build.py       tout l'enchaînement, rendu parallèle, export final (loudnorm −14 LUFS)
deliverables.py  génère GTA6_VOIX_OFF.txt et GTA6_TIMELINE.txt
```

Dépendances : Python 3.11+, `numpy scipy opencv-python-headless pillow soundfile onnxruntime kokoro-onnx`, ffmpeg.
Modèles (non versionnés, téléchargés depuis GitHub Releases) : `isnet-general-use.onnx` (rembg),
`kokoro-v1.0.onnx` + `voices-v1.0.bin` (kokoro-onnx).

```
python build.py --media <dossier médias décompressés> --models <dossier modèles>
python render.py --preview 12.5 95 210      # images de contrôle
```

## Écriture visuelle

- Ken Burns, dézooms, travellings ; parallaxe 2.5D avec sujet détouré, ombre portée sur le décor et liseré néon ;
  parallaxe par profondeur pour les paysages sans sujet.
- Noms de héros en 3D placés *entre* le décor et le personnage détouré.
- Textes 3D : extrusion ombrée, face en dégradé coucher de soleil, halo néon, ombre portée.
- 12 transitions (cut en mouvement, fondu, fondu au noir, dézoom doux/rapide, whip pan, zoom, flou directionnel,
  fuite de lumière, glitch, flash) : douces par défaut, fortes jamais deux fois de suite, chacune avec son son.
- Étalonnage Vice City (ombres bleutées, hautes lumières roses), vignettage, grain léger, letterbox sur l'intro et le final.
- Polices OFL (Google Fonts) : Anton, Bebas Neue, Montserrat, Pacifico, Monoton (`fonts/OFL.txt`).
