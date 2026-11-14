# -*- coding: utf-8 -*-
"""Medicao de referencia (somente leitura): mede cada parede, laje e pilar
direto da geometria, SEM usar HOST_AREA_COMPUTED/HOST_VOLUME_COMPUTED, e grava
C:\\NeuralBim\\referencia_<titulo>.json. Convencoes registradas no arquivo."""
import os, sys, io, json, datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Enviar Dados.pushbutton"))
from pyrevit import revit, DB, script
from comum import obter_id_como_numero, obter_nivel
doc = revit.doc
FT, FT2, FT3 = 0.3048, 0.092903, 0.0283168


def nome(e):
    try:
        return e.Name
    except Exception:
        return DB.Element.Name.__get__(e)


def dim(t, nomes):
    for n in nomes:
        p = t.LookupParameter(n) if t is not None else None
        if p is not None and p.StorageType == DB.StorageType.Double and p.AsDouble() > 0:
            return p.AsDouble() * FT
    return None


res = {"arquivo": doc.PathName, "titulo": doc.Title, "gerado_em": datetime.datetime.now().isoformat(),
       "convencoes": {
           "parede": "comprimento pelo eixo (LocationCurve) x altura (nivel base ate nivel topo + offsets) - soma largura x altura de cada porta/janela hospedada (todas descontadas)",
           "laje": "area do contorno do esboco (sketch) do elemento, pela formula do poligono",
           "pilar": "largura x profundidade (parametros do tipo) x altura (nivel topo - nivel base); forma = perimetro x altura"},
       "paredes": [], "lajes": [], "pilares": []}

for w in DB.FilteredElementCollector(doc).OfClass(DB.Wall):
    c = w.Location.Curve
    base = doc.GetElement(w.get_Parameter(DB.BuiltInParameter.WALL_BASE_CONSTRAINT).AsElementId())
    topo_id = w.get_Parameter(DB.BuiltInParameter.WALL_HEIGHT_TYPE).AsElementId()
    topo = doc.GetElement(topo_id) if topo_id != DB.ElementId.InvalidElementId else None
    off_b = w.get_Parameter(DB.BuiltInParameter.WALL_BASE_OFFSET).AsDouble()
    off_t = w.get_Parameter(DB.BuiltInParameter.WALL_TOP_OFFSET).AsDouble()
    if topo is not None:
        h = (topo.Elevation + off_t) - (base.Elevation + off_b)
    else:
        h = w.get_Parameter(DB.BuiltInParameter.WALL_USER_HEIGHT_PARAM).AsDouble()
    vaos = []
    for e in DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance):
        if e.Host is None or e.Host.Id != w.Id:
            continue
        t = doc.GetElement(e.GetTypeId())
        lw = dim(t, ("Largura", "Width")) or 0
        lh = dim(t, ("Altura", "Height")) or 0
        vaos.append({"id": obter_id_como_numero(e.Id), "categoria": e.Category.Name, "tipo": nome(t), "largura_m": round(lw, 3), "altura_m": round(lh, 3), "area_m2": round(lw * lh, 4)})
    cs = w.WallType.GetCompoundStructure()
    estr = sum(l.Width for l in cs.GetLayers() if l.Function == DB.MaterialFunctionAssignment.Structure) * FT * 100 if cs else None
    bruta = c.Length * FT * h * FT
    res["paredes"].append({"id": obter_id_como_numero(w.Id), "tipo": nome(w.WallType), "nivel": obter_nivel(doc, w),
                           "comprimento_eixo_m": round(c.Length * FT, 4), "altura_m": round(h * FT, 4),
                           "espessura_total_cm": round(w.Width * FT * 100, 2), "espessura_estrutural_cm": round(estr, 2) if estr else None,
                           "area_bruta_eixo_m2": round(bruta, 4), "area_vaos_m2": round(sum(v["area_m2"] for v in vaos), 4),
                           "area_liquida_eixo_m2": round(bruta - sum(v["area_m2"] for v in vaos), 4), "vaos": vaos})

for f in DB.FilteredElementCollector(doc).OfClass(DB.Floor):
    sk = doc.GetElement(f.SketchId) if hasattr(f, "SketchId") else None
    area = None
    if sk is not None:
        tot = 0.0
        for laco in sk.Profile:
            pts = [cv.GetEndPoint(0) for cv in laco]
            s = 0.0
            for i in range(len(pts)):
                a, b = pts[i], pts[(i + 1) % len(pts)]
                s += a.X * b.Y - b.X * a.Y
            tot += s / 2.0
        area = abs(tot) * FT2
    t = doc.GetElement(f.GetTypeId())
    cs = t.GetCompoundStructure()
    res["lajes"].append({"id": obter_id_como_numero(f.Id), "tipo": nome(t), "nivel": obter_nivel(doc, f),
                         "area_contorno_m2": round(area, 4) if area else None,
                         "espessura_total_cm": round(cs.GetWidth() * FT * 100, 2) if cs else None})

for col in DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType():
    t = doc.GetElement(col.GetTypeId())
    b = dim(t, ("b", "Largura", "Width"))
    hh = dim(t, ("h", "Profundidade", "Depth")) or b
    base = doc.GetElement(col.get_Parameter(DB.BuiltInParameter.FAMILY_BASE_LEVEL_PARAM).AsElementId())
    topo = doc.GetElement(col.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_PARAM).AsElementId())
    ob = col.get_Parameter(DB.BuiltInParameter.FAMILY_BASE_LEVEL_OFFSET_PARAM).AsDouble()
    ot = col.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_OFFSET_PARAM).AsDouble()
    alt = ((topo.Elevation + ot) - (base.Elevation + ob)) * FT
    res["pilares"].append({"id": obter_id_como_numero(col.Id), "tipo": t.FamilyName + " : " + nome(t), "nivel": obter_nivel(doc, col),
                           "b_m": round(b, 4), "h_m": round(hh, 4), "altura_m": round(alt, 4),
                           "volume_m3": round(b * hh * alt, 5), "area_forma_m2": round(2 * (b + hh) * alt, 4)})

txt = json.dumps(res, ensure_ascii=False, indent=1, default=str)
try:
    txt = txt.decode("utf-8")
except Exception:
    pass
caminho = r"C:\NeuralBim\referencia_{}.json".format(doc.Title)
with io.open(caminho, "w", encoding="utf-8") as fh:
    fh.write(txt)
out = script.get_output()
out.print_md("## Referencia geometrica - {}".format(doc.Title))
out.print_md("- {} paredes, {} lajes, {} pilares".format(len(res["paredes"]), len(res["lajes"]), len(res["pilares"])))
out.print_md("- Gravado em `{}`".format(caminho))
