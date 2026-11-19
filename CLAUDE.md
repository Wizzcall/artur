# Mémoire du projet — montages vidéo

## À refaire : montage YouTube « cinématographique » type GTA6_PROJET_MONTAGE

Quand l'utilisateur demande un montage vidéo (YouTube gaming ou autre), **repartir de la méthode et du code de
`GTA6_PROJET_MONTAGE/`** (voir son README.md) au lieu de repartir de zéro. Copier le dossier, puis remplacer
`narration.py` (script + découpage) et le catalogue de médias dans `assets.py`.

### Méthode qui a été validée
1. **Inventaire d'abord** : décompresser, classer (images / clips / captures perso / sons), vérifier chaque fichier
   (ffprobe, lecture), faire une planche contact et regarder les visuels avant d'écrire.
   Ressource manquante → ne pas l'inventer, adapter et le dire.
2. **Script narratif** dans `narration.py` : sections minutées selon le brief, chaque ligne porte ses plans,
   sous-titres dynamiques (mot déclencheur) et SFX. Ne jamais allonger artificiellement : ajouter du vrai contenu.
   Ne jamais laisser croire que le créateur a fait quelque chose qu'il n'a pas fait (ex. jouer au jeu).
3. **Voix** : TTS Kokoro (`kokoro-onnx`, voix FR `ff_siwis`, vitesse 0.9, respellings dans `SAY`) comme voix de
   travail ; remplaçable par les prises de l'utilisateur (`tts.py --user`). Une **version sans voix** est
   possible : `audio.py --no-voice` (supprime aussi le ducking).
4. **Timeline** (`timeline.py`) calculée sur les durées réelles de la voix ; coupes calées sur les débuts de phrase ;
   transitions douces par défaut, fortes jamais deux fois de suite, chacune avec son SFX.
5. **Audio** (`audio.py`) entièrement synthétisé (aucune musique commerciale) : une ambiance musicale par section,
   SFX (whoosh, impacts, risers, UI, glitch), ambiances urbaines, ducking sous la voix, master −14 LUFS / −1 dBTP.
6. **Visuel** (`fx.py`, `render.py`) : Ken Burns, parallaxe 2.5D avec détourage IS-Net (rembg `isnet-general-use`)
   et décor inpainté, nom 3D placé entre décor et sujet, textes 3D (extrusion, dégradé, néon, ombre), cartes
   superposées, chapitres synthwave, étalonnage, grain, letterbox. Rendu parallèle (4 processus) → concat → ffmpeg.
7. **Contrôle qualité avant l'export** : une image au milieu de chaque plan + une par type de transition, planches
   contact, vérification des niveaux audio (voix vs musique, crêtes, LUFS) et du nombre d'images par segment.
8. **Export** : master H.264 CRF 18 preset slow + AAC 320k ; une copie d'envoi < 400 Mio (2 passes) pour le chat.

### Préférences de l'utilisateur (relevées)
- Communication et contenus en **français**.
- Ajouts à un montage existant : **ne pas recommencer de zéro**, ne pas modifier les passages déjà validés
  (les nouveaux plans « capture » sont exclus du calcul des transitions pour ne rien décaler).
- Ne pas répéter les mêmes écrans ; recadrer si utile ; **ne jamais déformer** une vidéo ; garder la synchro audio.
- Durée cible respectée (ici 8–10 min), qualité maximale à l'export.
- Dernière livraison GTA 6 : version **sans voix** (`GTA6_VIDEO_FINALE_SANS_VOIX.mp4`).

### Pièges connus
- Les vidéos finales (> 100 Mo) ne vont pas sur GitHub : elles sont dans `.gitignore`, `build.py` les régénère.
- Limite d'envoi de fichier dans le chat : ~400 Mio.
- Modèles et médias téléchargés hors dépôt (HuggingFace bloqué ; GitHub Releases accessible pour Kokoro et rembg).

## Shorts (format vertical)
- Modèle : `SHORT_GTA6/short.py` (réutilise `fx.py` en vertical via `fx.W, fx.H = 1080, 1920`).
- Recette validée : remplir les bandes noires (fond flou de la même image), stabiliser (vidstab 2 passes),
  étalonner, masquer l'ancien texte incrusté et le réécrire en 3D lisible (corriger les fautes),
  zoom/flash/aberration synchronisés sur le drop et les temps forts détectés dans l'audio, son d'origine conservé,
  pub de fin (miniature + avatar + « regarde-la ici ») pour la vidéo longue. Zones sûres Shorts : éviter le bas (UI)
  et le bord droit (boutons).
- Livraison sur iPhone : le bouton de téléchargement du chat ne marche pas → passer par le lien GitHub « raw ».
- Short autonome « GTA 6 de minuit » : `MINUIT_SHORT/minuit.py` — source paysage mise en vertical (fond agrandi flouté,
  échelle uniforme, jamais déformée), caméra par images-clés, bande-son originale calée image par image sur un
  compte à rebours relevé à l'écran (tic-tac, accélération, « suck-out » 0,12 s puis impact au zéro). Si la source
  finit par un fondu au noir, figer la dernière image nette pour le texte final.
