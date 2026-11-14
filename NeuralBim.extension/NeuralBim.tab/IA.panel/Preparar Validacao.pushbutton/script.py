# -*- coding: utf-8 -*-
"""Botao 'Preparar Validacao': aplica no Projeto1 os passos 1-3 do Protocolo
da Etapa 8 + checklist de materiais, SEMPRE numa copia salva antes
(Projeto1_VALIDACAO_<data>.rvt). O arquivo original nao e alterado.
Grava o log em C:\\NeuralBim\\preparar_validacao_log.json."""
import os, sys, io, json, datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Enviar Dados.pushbutton"))

import clr
from System.Collections.Generic import List
from pyrevit import revit, DB, forms, script
from comum import obter_nivel, obter_id_como_numero

doc = revit.doc
out = script.get_output()
CM = 1.0 / 30.48           # cm -> pes
LOG = {"inicio": datetime.datetime.now().isoformat(), "acoes": [], "erros": []}


def log(msg):
    LOG["acoes"].append(msg)
    out.print_md("- " + msg)


def erro(msg):
    LOG["erros"].append(msg)
    out.print_md("- **ERRO:** " + msg)


def nome(e):
    try:
        return e.Name
    except Exception:
        return DB.Element.Name.__get__(e)


def gravar_log():
    LOG["fim"] = datetime.datetime.now().isoformat()
    texto = json.dumps(LOG, ensure_ascii=False, indent=1, default=str)
    try:
        texto = texto.decode("utf-8")
    except Exception:
        pass
    with io.open(r"C:\NeuralBim\preparar_validacao_log.json", "w", encoding="utf-8") as f:
        f.write(texto)


# ---------- 0. salvar copia ----------
niveis0 = [nome(l) for l in DB.FilteredElementCollector(doc).OfClass(DB.Level)]
if doc.IsModified:
    forms.alert("O arquivo aberto tem alteracoes nao salvas. Salve ou descarte antes de rodar.", exitscript=True)
out.print_md("## Preparar validacao")
if doc.Title == "Projeto1":
    pasta = os.path.dirname(doc.PathName)
    destino = os.path.join(pasta, "Projeto1_VALIDACAO_{}.rvt".format(datetime.date.today().isoformat()))
    if os.path.exists(destino):
        forms.alert("Ja existe {}. Abra esse arquivo e rode de novo.".format(destino), exitscript=True)
    LOG["original"] = doc.PathName
    opt = DB.SaveAsOptions()
    opt.OverwriteExistingFile = False
    doc.SaveAs(destino, opt)
    LOG["copia"] = destino
    log("Copia salva: `{}` (o Projeto1.rvt original nao e alterado)".format(destino))
elif doc.Title.startswith("Projeto1_VALIDACAO") and u"1º PAVIMENTO" in niveis0:
    LOG["copia"] = doc.PathName
    log("Trabalhando na copia ja aberta, ainda nao preparada: `{}`".format(doc.PathName))
else:
    forms.alert("Abra o Projeto1.rvt (ou a copia de validacao ainda nao preparada) antes de rodar.", exitscript=True)

niveis = dict((nome(l), l) for l in DB.FilteredElementCollector(doc).OfClass(DB.Level))


def por_categoria(bic):
    return list(DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType())


def material_por_nome(n):
    for m in DB.FilteredElementCollector(doc).OfClass(DB.Material):
        if nome(m) == n:
            return m
    return None


def tipo_por_nome(classe, n):
    for t in DB.FilteredElementCollector(doc).OfClass(classe):
        if nome(t) == n:
            return t
    return None


t = DB.Transaction(doc, "NeuralBIM - preparar modelo de validacao")
t.Start()
try:
    # ---------- 1. remover paredes e pilares do 1o PAVIMENTO (teste multipavimento) ----------
    paredes_1p = [e for e in por_categoria(DB.BuiltInCategory.OST_Walls) if obter_nivel(doc, e) == u"1º PAVIMENTO"]
    pilares_1p = [e for e in por_categoria(DB.BuiltInCategory.OST_StructuralColumns) if obter_nivel(doc, e) == u"1º PAVIMENTO"]
    ids = List[DB.ElementId]([e.Id for e in paredes_1p + pilares_1p])
    LOG["removidos"] = [obter_id_como_numero(i) for i in ids]
    if ids.Count:
        doc.Delete(ids)
    log("Removidos do 1º PAVIMENTO: {} paredes e {} pilares".format(len(paredes_1p), len(pilares_1p)))

    # ---------- 2. parede 15cm INTERNO: so o bloco como Estrutura, bloco 9 cm, espessura total mantida ----------
    wt = tipo_por_nome(DB.WallType, "15cm INTERNO")
    if wt is None:
        erro("Tipo de parede '15cm INTERNO' nao encontrado")
    else:
        cs = wt.GetCompoundStructure()
        camadas = list(cs.GetLayers())
        total_antes = sum(c.Width for c in camadas)
        i_bloco = [i for i, c in enumerate(camadas) if nome(doc.GetElement(c.MaterialId)) == "ALVENARIA DE BLOCO"]
        mat9 = material_por_nome("Alvenaria - Bloco de Cerâmico - 09cm")
        if len(i_bloco) != 1 or mat9 is None:
            erro("Parede 15cm INTERNO: camada de bloco ou material 9 cm nao encontrado")
        else:
            ib = i_bloco[0]
            n = len(camadas)
            cs.SetNumberOfShellLayers(DB.ShellLayerType.Exterior, ib)
            cs.SetNumberOfShellLayers(DB.ShellLayerType.Interior, n - ib - 1)
            ganho = 9 * CM - camadas[ib].Width                    # 7 -> 9 cm
            cs.SetLayerWidth(ib, 9 * CM)
            cs.SetMaterialId(ib, mat9.Id)
            embocos = [i for i, c in enumerate(camadas) if nome(doc.GetElement(c.MaterialId)) == u"EMBOÇO"]
            for i in embocos:                                       # compensa no emboco: espessura total igual
                cs.SetLayerWidth(i, camadas[i].Width - ganho / len(embocos))
            for i, c in enumerate(camadas):
                if i != ib and c.Function == DB.MaterialFunctionAssignment.Structure:
                    cs.SetLayerFunction(i, DB.MaterialFunctionAssignment.Finish1 if i < ib else DB.MaterialFunctionAssignment.Finish2)
            cs.StructuralMaterialIndex = ib
            wt.SetCompoundStructure(cs)
            total_depois = sum(c.Width for c in wt.GetCompoundStructure().GetLayers())
            log("Parede '15cm INTERNO': bloco 7 -> 9 cm (material 'Alvenaria - Bloco de Cerâmico - 09cm'), emboço ajustado, "
                "massa/reboco/emboço/chapisco viraram Acabamento; espessura total {:.1f} -> {:.1f} cm".format(total_antes / CM, total_depois / CM))

    # ---------- 3. lajes: piso sobre solo (TERREO) e laje trelicada (cobertura) ----------
    ft = tipo_por_nome(DB.FloorType, "Lage/PREMOLDADA h5 (TETO)")
    mat_conc = material_por_nome("CONCRETO")
    mat_pre = material_por_nome("PRE MOLDADO")
    if ft is None or mat_conc is None or mat_pre is None:
        erro("Tipo de laje ou materiais CONCRETO / PRE MOLDADO nao encontrados")
    else:
        m_piso = material_por_nome("PISO SOBRE SOLO - Concreto 10cm") or mat_conc.Duplicate("PISO SOBRE SOLO - Concreto 10cm")
        m_trel = material_por_nome("LAJE TRELICADA - h12 (EPS 8 + capa 4)") or mat_pre.Duplicate("LAJE TRELICADA - h12 (EPS 8 + capa 4)")
        log("Materiais criados: 'PISO SOBRE SOLO - Concreto 10cm' e 'LAJE TRELICADA - h12 (EPS 8 + capa 4)'")

        t_piso = tipo_por_nome(DB.FloorType, "Piso sobre solo 10cm") or ft.Duplicate("Piso sobre solo 10cm")
        cs_p = ft.GetCompoundStructure()
        unica = List[DB.CompoundStructureLayer]()
        unica.Add(DB.CompoundStructureLayer(10 * CM, DB.MaterialFunctionAssignment.Structure, m_piso.Id))
        cs_p.SetLayers(unica)
        cs_p.SetNumberOfShellLayers(DB.ShellLayerType.Exterior, 0)
        cs_p.SetNumberOfShellLayers(DB.ShellLayerType.Interior, 0)
        cs_p.StructuralMaterialIndex = 0
        t_piso.SetCompoundStructure(cs_p)
        log("Tipo de laje 'Piso sobre solo 10cm': uma camada Estrutura de 10 cm")

        t_trel = tipo_por_nome(DB.FloorType, "Laje trelicada cobertura h12") or ft.Duplicate("Laje trelicada cobertura h12")
        cs_t = ft.GetCompoundStructure()
        orig = list(cs_t.GetLayers())
        resto = [c for c in orig if c.Function != DB.MaterialFunctionAssignment.Structure]
        novas = List[DB.CompoundStructureLayer]()
        novas.Add(DB.CompoundStructureLayer(12 * CM, DB.MaterialFunctionAssignment.Structure, m_trel.Id))
        for c in resto:
            novas.Add(DB.CompoundStructureLayer(c.Width, c.Function, c.MaterialId))
        cs_t.SetLayers(novas)
        cs_t.SetNumberOfShellLayers(DB.ShellLayerType.Exterior, 0)
        cs_t.SetNumberOfShellLayers(DB.ShellLayerType.Interior, len(resto))
        cs_t.StructuralMaterialIndex = 0
        t_trel.SetCompoundStructure(cs_t)
        log("Tipo de laje 'Laje trelicada cobertura h12': uma camada Estrutura de 12 cm + acabamentos de forro mantidos")

        for f in por_categoria(DB.BuiltInCategory.OST_Floors):
            nv = obter_nivel(doc, f)
            if nv == u"TÉRREO":
                f.ChangeTypeId(t_piso.Id)
                log("Laje {} (TÉRREO) -> Piso sobre solo 10cm".format(obter_id_como_numero(f.Id)))
            elif nv == u"1º PAVIMENTO":
                f.ChangeTypeId(t_trel.Id)
                log("Laje {} (1º PAVIMENTO -> COBERTURA) -> Laje trelicada cobertura h12".format(obter_id_como_numero(f.Id)))

    # ---------- 4. niveis: o 1o PAVIMENTO (topo das paredes, 3,00 m) passa a se chamar COBERTURA ----------
    if u"COBERTURA" in niveis and u"1º PAVIMENTO" in niveis:
        niveis[u"COBERTURA"].Name = u"COBERTURA ANTIGA 18m (sem uso)"
        niveis[u"1º PAVIMENTO"].Name = u"COBERTURA"
        log("Níveis renomeados: 'COBERTURA' (18 m) -> 'COBERTURA ANTIGA 18m (sem uso)'; '1º PAVIMENTO' (3 m) -> 'COBERTURA'")
    t.Commit()
except Exception as ex:
    t.RollBack()
    erro("Transacao desfeita: {}".format(ex))
    gravar_log()
    forms.alert("Erro, nada foi aplicado na copia: {}".format(ex))
    raise

doc.Save()
log("Copia de validacao salva.")
gravar_log()
