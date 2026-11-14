# -*- coding: utf-8 -*-
"""Botao 'Auditar Materiais' (somente leitura): lista todos os tipos de
parede, laje e pilar estrutural do modelo aberto, com camadas, materiais,
espessura estrutural e a classificacao que o 'Enviar Dados' faria.
Grava C:\\NeuralBim\\auditoria_materiais.json. Nao altera o modelo."""
import os, sys, io, json, datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Enviar Dados.pushbutton"))

from pyrevit import revit, DB, script
from comum import classificar_material_automatico, obter_nivel, obter_id_como_numero, FATOR_FT_PARA_M, FATOR_FT2_PARA_M2

doc = revit.doc
out = script.get_output()
CM = FATOR_FT_PARA_M * 100


def nome(e):
    if e is None:
        return "?"
    try:
        return e.Name
    except Exception:
        pass
    try:
        return DB.Element.Name.__get__(e)
    except Exception:
        pass
    for bip in (DB.BuiltInParameter.ALL_MODEL_TYPE_NAME, DB.BuiltInParameter.SYMBOL_NAME_PARAM):
        try:
            p = e.get_Parameter(bip)
            if p is not None and p.AsString():
                return p.AsString()
        except Exception:
            pass
    return "id " + str(obter_id_como_numero(e.Id))


def camadas(tipo):
    res = []
    try:
        cs = tipo.GetCompoundStructure()
    except Exception:
        cs = None
    if cs is None:
        return None
    for i, c in enumerate(cs.GetLayers()):
        mat = doc.GetElement(c.MaterialId)
        res.append({"indice": i, "funcao": str(c.Function), "material": nome(mat) if mat else "<sem material / por categoria>",
                    "material_id": obter_id_como_numero(c.MaterialId),
                    "espessura_cm": round(c.Width * CM, 2)})
    return res


def auditar_hospedeiro(categoria, bic):
    tipos = {}
    for el in DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType():
        tid = el.GetTypeId()
        tipo = doc.GetElement(tid)
        if tipo is None:
            continue
        chave = nome(tipo)
        t = tipos.setdefault(chave, {"categoria": categoria, "tipo": chave, "tipo_id": obter_id_como_numero(tid), "familia": getattr(tipo, "FamilyName", ""),
                                      "qtd": 0, "niveis": {}, "area_m2": 0.0, "camadas": camadas(tipo)})
        t["qtd"] += 1
        nv = obter_nivel(doc, el)
        t["niveis"][nv] = t["niveis"].get(nv, 0) + 1
        p = el.get_Parameter(DB.BuiltInParameter.HOST_AREA_COMPUTED)
        t["area_m2"] += (p.AsDouble() * FATOR_FT2_PARA_M2) if p else 0
    for t in tipos.values():
        t["area_m2"] = round(t["area_m2"], 2)
        cs = t["camadas"]
        if cs is None:
            t["classificacao"] = "SEM CompoundStructure (cortina/empilhada) -> dialogo manual"
            continue
        estr = [c for c in cs if c["funcao"] == "Structure"]
        t["espessura_estrutural_cm"] = round(sum(c["espessura_cm"] for c in estr), 2)
        ok, cat, dist = classificar_material_automatico([c["material"] for c in estr])
        t["classificacao"] = cat if ok else "NAO RECONHECIDO -> dialogo manual"
        t["multiplas_categorias"] = dist if len(dist) > 1 else []
    return list(tipos.values())


def auditar_pilares():
    tipos = {}
    for el in DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType():
        tipo = doc.GetElement(el.GetTypeId())
        chave = (getattr(tipo, "FamilyName", "") + " : " + nome(tipo)) if tipo else "?"
        p = el.get_Parameter(DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
        mid = p.AsElementId() if p else DB.ElementId.InvalidElementId
        if mid == DB.ElementId.InvalidElementId and tipo is not None:
            pt = tipo.get_Parameter(DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
            mid = pt.AsElementId() if pt else mid
        mat = doc.GetElement(mid) if mid != DB.ElementId.InvalidElementId else None
        mnome = nome(mat) if mat else "<sem material>"
        t = tipos.setdefault(chave + " | " + mnome, {"categoria": "Pilar", "tipo": chave, "tipo_id": obter_id_como_numero(el.GetTypeId()), "qtd": 0, "niveis": {},
                                                    "material": mnome, "params_tipo": {}})
        t["qtd"] += 1
        nv = obter_nivel(doc, el)
        t["niveis"][nv] = t["niveis"].get(nv, 0) + 1
        if tipo is not None and not t["params_tipo"]:
            for n in ("b", "h", "Largura", "Profundidade", "Width", "Depth"):
                q = tipo.LookupParameter(n)
                if q is not None and q.StorageType == DB.StorageType.Double:
                    t["params_tipo"][n] = round(q.AsDouble() * CM, 1)
            for nbip, n in (("FAMILY_WIDTH_PARAM", "FAMILY_WIDTH"), ("FAMILY_DEPTH_PARAM", "FAMILY_DEPTH")):
                try:
                    q = tipo.get_Parameter(getattr(DB.BuiltInParameter, nbip))
                    if q is not None:
                        t["params_tipo"][n] = round(q.AsDouble() * CM, 1)
                except Exception:
                    pass
    for t in tipos.values():
        ok, cat, dist = classificar_material_automatico([t["material"]] if t["material"] != "<sem material>" else [])
        t["classificacao"] = cat if ok else "NAO RECONHECIDO -> dialogo manual"
    return list(tipos.values())


def contar(bic):
    return DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().GetElementCount()


res = {
    "arquivo": doc.PathName, "titulo": doc.Title, "gerado_em": datetime.datetime.now().isoformat(),
    "niveis": sorted([(nome(l), round(l.Elevation * FATOR_FT_PARA_M, 3)) for l in DB.FilteredElementCollector(doc).OfClass(DB.Level)], key=lambda x: x[1]),
    "paredes": auditar_hospedeiro("Parede", DB.BuiltInCategory.OST_Walls),
    "lajes": auditar_hospedeiro("Laje", DB.BuiltInCategory.OST_Floors),
    "pilares": auditar_pilares(),
    "outros": {"pilares_arquitetonicos": contar(DB.BuiltInCategory.OST_Columns), "vigas": contar(DB.BuiltInCategory.OST_StructuralFraming),
               "fundacoes": contar(DB.BuiltInCategory.OST_StructuralFoundation), "telhados": contar(DB.BuiltInCategory.OST_Roofs),
               "forros": contar(DB.BuiltInCategory.OST_Ceilings), "portas": contar(DB.BuiltInCategory.OST_Doors), "janelas": contar(DB.BuiltInCategory.OST_Windows)},
    "materiais": sorted([(nome(m), obter_id_como_numero(m.Id)) for m in DB.FilteredElementCollector(doc).OfClass(DB.Material)]),
}
caminho = r"C:\NeuralBim\auditoria_materiais.json"
texto = json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: int(str(o)) if str(o).lstrip("-").isdigit() else str(o))
try:
    texto = texto.decode("utf-8")
except Exception:
    pass
with io.open(caminho, "w", encoding="utf-8") as f:
    f.write(texto)

out.print_md("## Auditoria de materiais - " + doc.Title)
for grupo in ("paredes", "lajes", "pilares"):
    out.print_md("### " + grupo.capitalize())
    for t in res[grupo]:
        out.print_md("- **{}** ({} un.) -> {}".format(t["tipo"], t["qtd"], t["classificacao"]))
out.print_md("Arquivo gravado: `" + caminho + "`")
