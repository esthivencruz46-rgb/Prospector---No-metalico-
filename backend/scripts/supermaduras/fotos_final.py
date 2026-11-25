"""Selección final revisada a mano (hojas de contacto): descarta recortes malos o no atribuibles, endereza las
fotos giradas y corrige la unidad de las canteras de Cajamarca sin unidad indicada. Salida: fotos_final/ + fotos_final.json"""
import json, os, re, shutil, sys
from PIL import Image
sys.stdout.reconfigure(encoding="utf-8")
ESC = os.path.dirname(os.path.abspath(__file__))
f = json.load(open(os.path.join(ESC, "fotos_bol", "fotos.json"), encoding="utf-8"))
DESCARTAR = {2, 24, 31, 32, 33, 34, 35, 38, 39, 41, 45, 50, 63, 74, 77, 78, 80, 81, 82, 83, 86, 87, 90, 91, 92, 93, 94, 95,
             96, 97, 98, 114, 115, 121, 122}
GIRAR = {25: -90, 29: -90}
SIN_UNIDAD = {104, 108, 112}          # Cabracabra, Gracias Padre Eterno, El Algarrobal: «unidad no indicada» → con Chimú
DST = os.path.join(ESC, "fotos_final")
shutil.rmtree(DST, ignore_errors=True)
os.makedirs(DST)
out = []
for i, x in enumerate(f):
    if i in DESCARTAR:
        continue
    img = Image.open(os.path.join(ESC, "fotos_bol", x["archivo_img"]))
    if i in GIRAR:
        img = img.rotate(GIRAR[i], expand=True)
    img.save(os.path.join(DST, x["archivo_img"]), quality=72, optimize=True)
    x = dict(x)
    if i in SIN_UNIDAD:
        x["unidad"], x["nota"] = "chimu", "Cantera de Cajamarca sin unidad indicada en el boletín."
    x["leyenda"] = re.sub(r"\s+", " ", x["leyenda"]).strip()
    x["px"] = [img.width, img.height]
    x["idx"] = i
    out.append(x)
json.dump(out, open(os.path.join(ESC, "fotos_final.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(out), Counter(x["unidad"] for x in out).most_common())
print("MB:", round(sum(os.path.getsize(os.path.join(DST, x["archivo_img"])) for x in out) / 1e6, 1))
