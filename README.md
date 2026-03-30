# PNG planimetria -> SVG vettoriale (OpenCV)

Questa applicazione legge una planimetria di appartamento in PNG, estrae i contorni principali con OpenCV e li esporta in un file SVG vettoriale.

La conversione in coordinate reali usa la scala **1:200** (default) e i DPI del file/scansione (default **300 DPI**).

## Requisiti

- Python 3.9+
- Pacchetti in `requirements.txt`

## Installazione

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso rapido

```bash
python plan2svg.py test-plan.png output_test.svg --scale 200 --dpi 300
```

## Parametri utili

- `--scale`: rapporto scala (200 = scala 1:200)
- `--dpi`: DPI immagine per conversione pixel->metri
- `--min-area-px`: filtra rumore (contorni troppo piccoli)
- `--epsilon-ratio`: semplificazione polilinee (piu' alto = meno punti)
- `--stroke-width-m`: spessore linee SVG in metri reali
- `--invert`: inverte bianco/nero prima dell'estrazione

Esempio con tuning:

```bash
python plan2svg.py input.png output.svg --scale 200 --dpi 300 --min-area-px 400 --epsilon-ratio 0.003 --stroke-width-m 0.02 --invert
```

## Formato SVG

Output:

- Ogni contorno viene esportato come `<polygon>` (chiuso) o `<polyline>`
- Le coordinate nel file sono in **metri reali**
- `viewBox`, `width` e `height` dell'SVG sono impostati in metri

## Nota sulla scala 1:200

Il fattore e':

```text
metri_reali_per_pixel = (0.0254 / dpi) * 200
```

Se il PNG non e' a 300 DPI reali, imposta `--dpi` corretto per avere misure affidabili.
