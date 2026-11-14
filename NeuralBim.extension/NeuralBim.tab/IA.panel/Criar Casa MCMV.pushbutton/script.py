# -*- coding: utf-8 -*-
"""Botao 'Criar Casa MCMV': gera um projeto Revit NOVO com uma casa terrea de
~65 m2 (padrao Minha Casa Minha Vida: sala, cozinha, area de servico,
2 quartos, banheiro, circulacao), ja com tipos e materiais no padrao do
checklist do NeuralBIM. Nao altera o projeto aberto (so copia dele a familia
de pilar, e de porta/janela se o template nao tiver).
Salva em ...\\TCC\\CasaMCMV_65m2.rvt e grava C:\\NeuralBim\\casa_mcmv_log.json."""
import os, sys, io, json, math, datetime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Enviar Dados.pushbutton"))
import clr
from System.Collections.Generic import List
from pyrevit import revit, DB, forms, script
from comum import obter_id_como_numero

app = __revit__.Application
uiapp = __revit__
src = revit.doc
out = script.get_output()
M = 1 / 0.3048            # metro -> pe
CM = M / 100
TEMPLATE = r"C:\ProgramData\Autodesk\RVT 2026\Templates\Portuguese\DefaultBRAPTB.rte"
PASTA = os.path.dirname(src.PathName) if src.PathName else r"C:\Users\GABRI\OneDrive\Documentos\TCC"
DESTINO = os.path.join(PASTA, "CasaMCMV_65m2.rvt")
LOG = {"inicio": datetime.datetime.now().isoformat(), "acoes": [], "erros": []}


def log(m):
    LOG["acoes"].append(m); out.print_md("- " + m)


def erro(m):
    LOG["erros"].append(m); out.print_md("- **ERRO:** " + m)


def nome(e):
    try:
        return e.Name
    except Exception:
        return DB.Element.Name.__get__(e)


def gravar_log():
    LOG["fim"] = datetime.datetime.now().isoformat()
    t = json.dumps(LOG, ensure_ascii=False, indent=1, default=str)
    try:
        t = t.decode("utf-8")
    except Exception:
        pass
    with io.open(r"C:\NeuralBim\casa_mcmv_log.json", "w", encoding="utf-8") as f:
        f.write(t)


if os.path.exists(DESTINO):
    forms.alert("Ja existe {}. Nada foi feito.".format(DESTINO), exitscript=True)

out.print_md("## Criar casa MCMV 65 m²")
doc = app.NewProjectDocument(TEMPLATE)
log("Novo projeto a partir de `{}`".format(TEMPLATE))


def P(x, y, z=0):
    return DB.XYZ(x * M, y * M, z * M)


def etapa(titulo):
    def deco(fn):
        t = DB.Transaction(doc, "MCMV - " + titulo)
        t.Start()
        try:
            r = fn()
            t.Commit()
            return r
        except Exception as ex:
            t.RollBack()
            erro("{}: {}".format(titulo, ex))
            return None
    return deco


# ---------------- geometria (metros) ----------------
LX, LY = 8.00, 8.15                   # dimensoes externas: 65,2 m2
E_EXT = 0.185                         # parede externa: 2,5 + 14 + 2,0 cm
c = E_EXT / 2
X0, Y0, X1, Y1 = c, c, LX - c, LY - c  # eixos das paredes externas
XA, XB = 3.10, 4.80                   # eixos internos verticais
YA, YB, YC = 2.80, 4.20, 5.70         # eixos internos horizontais
PE_DIREITO = 2.80


# ---------------- 1. niveis ----------------
@etapa("niveis")
def niveis():
    lv = sorted(DB.FilteredElementCollector(doc).OfClass(DB.Level), key=lambda l: l.Elevation)
    ter, cob = lv[0], lv[1]
    vistas = list(DB.FilteredElementCollector(doc).OfClass(DB.ViewPlan))
    for l, novo, elev in ((ter, u"TÉRREO", 0.0), (cob, u"COBERTURA", PE_DIREITO)):
        antigo = nome(l)
        l.Elevation = elev * M
        l.Name = novo
        for v in vistas:
            if not v.IsTemplate and nome(v) == antigo:
                try:
                    v.Name = novo
                except Exception:
                    pass
    log(u"Níveis: TÉRREO (0,00 m) e COBERTURA (2,80 m)")
    return ter, cob

ter, cob = niveis


# ---------------- 2. materiais e tipos ----------------
@etapa("materiais e tipos")
def tipos():
    def mat(n, rgb):
        mid = DB.Material.Create(doc, n)
        m = doc.GetElement(mid)
        m.Color = DB.Color(*rgb)
        return mid
    m = {
        "b14": mat(u"Alvenaria - Bloco Cerâmico 14cm", (178, 92, 60)),
        "b9": mat(u"Alvenaria - Bloco Cerâmico 9cm", (190, 110, 80)),
        "rext": mat(u"Reboco externo (chapisco + emboço)", (235, 230, 220)),
        "rint": mat(u"Reboco interno (chapisco + emboço)", (245, 245, 240)),
        "piso": mat(u"PISO SOBRE SOLO - Concreto 10cm", (160, 160, 160)),
        "laje": mat(u"LAJE TRELICADA - h12 (EPS 8 + capa 4)", (150, 150, 155)),
        "forro": mat(u"Reboco teto", (250, 250, 250)),
    }
    F = DB.MaterialFunctionAssignment
    base_w = [w for w in DB.FilteredElementCollector(doc).OfClass(DB.WallType) if w.Kind == DB.WallKind.Basic][0]
    base_f = list(DB.FilteredElementCollector(doc).OfClass(DB.FloorType))
    base_f = [f for f in base_f if f.GetCompoundStructure() is not None][0]

    def tipo(base, novo, camadas, n_ext, n_int, i_estr):
        t = base.Duplicate(novo)
        cs = base.GetCompoundStructure()
        lst = List[DB.CompoundStructureLayer]()
        for w, fn, mid in camadas:
            lst.Add(DB.CompoundStructureLayer(w * CM, fn, mid))
        cs.SetLayers(lst)
        cs.SetNumberOfShellLayers(DB.ShellLayerType.Exterior, n_ext)
        cs.SetNumberOfShellLayers(DB.ShellLayerType.Interior, n_int)
        cs.StructuralMaterialIndex = i_estr
        t.SetCompoundStructure(cs)
        return t
    w_ext = tipo(base_w, u"Parede Externa - Bloco Cerâmico 14cm", [(2.5, F.Finish1, m["rext"]), (14, F.Structure, m["b14"]), (2.0, F.Finish2, m["rint"])], 1, 1, 1)
    w_int = tipo(base_w, u"Parede Interna - Bloco Cerâmico 9cm", [(1.5, F.Finish1, m["rint"]), (9, F.Structure, m["b9"]), (1.5, F.Finish2, m["rint"])], 1, 1, 1)
    f_piso = tipo(base_f, u"Piso sobre solo 10cm", [(10, F.Structure, m["piso"])], 0, 0, 0)
    f_laje = tipo(base_f, u"Laje trelicada cobertura h12", [(12, F.Structure, m["laje"]), (1.5, F.Finish2, m["forro"])], 0, 1, 0)
    log(u"Tipos criados: parede externa 14 cm, parede interna 9 cm, piso sobre solo 10 cm, laje treliçada h12 (cada um com 1 camada Estrutura)")
    return w_ext, w_int, f_piso, f_laje

w_ext, w_int, f_piso, f_laje = tipos


# ---------------- 3. familias copiadas do projeto aberto ----------------
def simbolos(d, bic):
    return list(DB.FilteredElementCollector(d).OfCategory(bic).OfClass(DB.FamilySymbol))


@etapa("copiar familias")
def copiar():
    ids = List[DB.ElementId]()
    if not [s for s in simbolos(doc, DB.BuiltInCategory.OST_StructuralColumns) if "Concreto" in s.FamilyName]:
        for s in simbolos(src, DB.BuiltInCategory.OST_StructuralColumns):
            if s.FamilyName == "M_Concreto-Quadrado-Coluna":
                ids.Add(s.Id); break
    for bic in (DB.BuiltInCategory.OST_Doors, DB.BuiltInCategory.OST_Windows):
        if not simbolos(doc, bic):
            ss = simbolos(src, bic)
            if ss:
                ids.Add(ss[0].Id)
    if ids.Count:
        opt = DB.CopyPasteOptions()
        DB.ElementTransformUtils.CopyElements(src, ids, doc, DB.Transform.Identity, opt)
    log(u"Famílias copiadas do projeto aberto: {}".format(ids.Count))

copiar


def ajustar(sym, novo, pares):
    """Duplica o tipo e ajusta parametros (nome builtin ou nome de parametro) em metros."""
    t = sym.Duplicate(novo)
    for chaves, valor in pares:
        for k in chaves:
            p = None
            if k.isupper():
                b = getattr(DB.BuiltInParameter, k, None)
                p = t.get_Parameter(b) if b is not None else None
            else:
                p = t.LookupParameter(k)
            if p is not None and not p.IsReadOnly:
                p.Set(valor * M); break
    return t


# ---------------- 4. paredes ----------------
PAREDES = [  # (x1, y1, x2, y2, externa?)
    (X0, Y0, X1, Y0, True), (X1, Y0, X1, Y1, True), (X1, Y1, X0, Y1, True), (X0, Y1, X0, Y0, True),
    (XB, Y0, XB, Y1, False),            # sala|cozinha, circ|quarto2, banheiro|quarto2
    (XA, YB, XA, Y1, False),            # quarto1 | circulacao + banheiro
    (X0, YB, XA, YB, False),            # sala | quarto1
    (XB, YB, X1, YB, False),            # area de servico | quarto2
    (XB, YA, X1, YA, False),            # cozinha | area de servico
    (XA, YC, XB, YC, False),            # circulacao | banheiro
]


@etapa("paredes")
def paredes():
    res = []
    for x1, y1, x2, y2, ext in PAREDES:
        w = DB.Wall.Create(doc, DB.Line.CreateBound(P(x1, y1), P(x2, y2)), (w_ext if ext else w_int).Id, ter.Id, PE_DIREITO * M, 0, False, False)
        w.get_Parameter(DB.BuiltInParameter.WALL_HEIGHT_TYPE).Set(cob.Id)
        res.append(w)
    log(u"Paredes: {} (4 externas de 14 cm, {} internas de 9 cm), do TÉRREO à COBERTURA".format(len(res), len(res) - 4))
    return res

ws = paredes


# ---------------- 5. piso e laje ----------------
def contorno(x0, y0, x1, y1):
    cl = DB.CurveLoop()
    pts = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
    for i in range(4):
        cl.Append(DB.Line.CreateBound(pts[i], pts[(i + 1) % 4]))
    l = List[DB.CurveLoop](); l.Add(cl)
    return l


@etapa("piso e laje")
def lajes():
    DB.Floor.Create(doc, contorno(0, 0, LX, LY), f_piso.Id, ter.Id)
    DB.Floor.Create(doc, contorno(0, 0, LX, LY), f_laje.Id, cob.Id)
    log(u"Piso sobre solo (TÉRREO) e laje treliçada (COBERTURA): {:.2f} m² cada".format(LX * LY))

lajes


# ---------------- 6. pilares ----------------
PILARES = [(X0, Y0), (X1, Y0), (X0, Y1), (X1, Y1), (XB, Y0), (XB, Y1), (X0, YB), (X1, YB)]


@etapa("pilares")
def pilares():
    ss = [s for s in simbolos(doc, DB.BuiltInCategory.OST_StructuralColumns) if "Concreto" in s.FamilyName]
    if not ss:
        raise Exception("nenhuma familia de pilar de concreto disponivel")
    sym = ajustar(ss[0], "190 x 190 mm", [(("b", "Largura", "Width"), 0.19), (("h", "Profundidade", "Depth"), 0.19)])
    sym.Activate()
    for x, y in PILARES:
        col = doc.Create.NewFamilyInstance(P(x, y), sym, ter, DB.Structure.StructuralType.Column)
        col.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_PARAM).Set(cob.Id)
        col.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_OFFSET_PARAM).Set(0.0)
    log(u"Pilares: {} de concreto 19x19 cm ({}), do TÉRREO à COBERTURA".format(len(PILARES), ss[0].FamilyName))

pilares


# ---------------- 7. portas e janelas ----------------
def parede_em(x, y):
    for w in ws or []:
        ln = w.Location.Curve
        pr = ln.Project(P(x, y))
        if pr is not None and pr.Distance < 0.02 * M:
            return w
    return None


PORTAS = [("Porta 90x210", 0.90, 2.10, 2.00, Y0, "Entrada (sala)"), ("Porta 80x210", 0.80, 2.10, XB, 3.40, "Sala - cozinha"),
          ("Porta 80x210", 0.80, 2.10, 5.60, YA, u"Cozinha - área de serviço"), ("Porta 80x210", 0.80, 2.10, X1, 3.50, u"Área de serviço - externa"),
          ("Porta 80x210", 0.80, 2.10, XA, 4.95, "Quarto 1"), ("Porta 80x210", 0.80, 2.10, XB, 4.95, "Quarto 2"),
          ("Porta 70x210", 0.70, 2.10, 3.95, YC, "Banheiro")]
JANELAS = [("Janela 150x120", 1.50, 1.20, 1.00, 3.60, Y0, "Sala (frente)"), ("Janela 120x120", 1.20, 1.20, 1.00, X0, 2.10, "Sala (lateral)"),
           ("Janela 120x100", 1.20, 1.00, 1.10, 6.40, Y0, "Cozinha"), ("Janela 120x120", 1.20, 1.20, 1.00, 1.60, Y1, "Quarto 1"),
           ("Janela 120x120", 1.20, 1.20, 1.00, 6.40, Y1, "Quarto 2"), ("Janela 60x60", 0.60, 0.60, 1.50, 3.95, Y1, "Banheiro")]


@etapa("portas e janelas")
def esquadrias():
    feitos = {"porta": 0, "janela": 0}
    doc.Regenerate()
    for bic, lista, chave_w, chave_h, tipo in ((DB.BuiltInCategory.OST_Doors, PORTAS, "DOOR_WIDTH", "DOOR_HEIGHT", "porta"),
                                                (DB.BuiltInCategory.OST_Windows, JANELAS, "WINDOW_WIDTH", "WINDOW_HEIGHT", "janela")):
        ss = simbolos(doc, bic)
        if not ss:
            erro(u"nenhuma família de {} no template nem no projeto aberto".format(tipo))
            continue
        base = ss[0]
        LOG.setdefault("familias_esquadria", []).append(base.FamilyName + " : " + nome(base))
        criados = {}
        for item in lista:
            tn, w, h = item[0], item[1], item[2]
            if tn not in criados:
                criados[tn] = ajustar(base, tn, [((chave_w, "FAMILY_WIDTH_PARAM", "Largura", "Width"), w), ((chave_h, "FAMILY_HEIGHT_PARAM", "Altura", "Height"), h)])
                criados[tn].Activate()
            x, y = (item[3], item[4]) if tipo == "porta" else (item[4], item[5])
            host = parede_em(x, y)
            if host is None:
                erro(u"{} '{}': parede não encontrada em ({}, {})".format(tipo, item[-1], x, y)); continue
            doc.Regenerate()
            fi = doc.Create.NewFamilyInstance(P(x, y), criados[tn], host, ter, DB.Structure.StructuralType.NonStructural)
            doc.Regenerate()
            if tipo == "janela":
                p = fi.get_Parameter(DB.BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
                if p is not None:
                    p.Set(item[3] * M)
            feitos[tipo] += 1
    doc.Regenerate()
    cortes = sum(len(list(w.FindInserts(True, False, False, False))) for w in ws)
    if cortes < feitos["porta"] + feitos["janela"]:
        erro(u"só {} de {} esquadrias cortam as paredes".format(cortes, feitos["porta"] + feitos["janela"]))
    log(u"Esquadrias: {} portas e {} janelas ({})".format(feitos["porta"], feitos["janela"], "; ".join(LOG.get("familias_esquadria", []))))

esquadrias


# ---------------- 8. ambientes ----------------
AMBIENTES = [("Sala", 2.40, 2.10), ("Cozinha", 6.40, 1.40), (u"Área de Serviço", 6.40, 3.50), ("Quarto 1", 1.60, 6.10),
             ("Quarto 2", 6.40, 6.10), ("Banheiro", 3.95, 6.90), (u"Circulação", 3.95, 4.95)]


@etapa("ambientes")
def ambientes():
    doc.Regenerate()
    vista = [v for v in DB.FilteredElementCollector(doc).OfClass(DB.ViewPlan)
             if not v.IsTemplate and v.GenLevel is not None and v.GenLevel.Id == ter.Id and v.ViewType == DB.ViewType.FloorPlan][0]
    sp = DB.SketchPlane.Create(doc, ter.Id)
    ca = DB.CurveArray(); ca.Append(DB.Line.CreateBound(P(XA, YB), P(XB, YB)))
    doc.Create.NewRoomBoundaryLines(sp, ca, vista)
    doc.Regenerate()
    areas = []
    for n, x, y in AMBIENTES:
        r = doc.Create.NewRoom(ter, DB.UV(x * M, y * M))
        r.Name = n
        areas.append((n, r))
    doc.Regenerate()
    LOG["ambientes"] = [(n, round(r.Area * 0.092903, 2)) for n, r in areas]
    log(u"Ambientes: " + ", ".join(u"{} {:.2f} m²".format(n, a) for n, a in LOG["ambientes"]))

ambientes


# ---------------- 9. telhado (so visual) ----------------
@etapa("telhado")
def telhado():
    rts = list(DB.FilteredElementCollector(doc).OfClass(DB.RoofType))
    rt = ([r for r in rts if u"telha" in nome(r).lower()] or rts)[0]
    ca = DB.CurveArray()
    pts = [P(-0.5, -0.5), P(LX + 0.5, -0.5), P(LX + 0.5, LY + 0.5), P(-0.5, LY + 0.5)]
    for i in range(4):
        ca.Append(DB.Line.CreateBound(pts[i], pts[(i + 1) % 4]))
    caixa = clr.StrongBox[DB.ModelCurveArray](DB.ModelCurveArray())
    roof = doc.Create.NewFootPrintRoof(ca, cob, rt, caixa)
    mapa = caixa.Value
    if mapa is not None:
        for mc in mapa:
            d = mc.GeometryCurve.Direction
            inclina = abs(d.X) > 0.9            # bordas paralelas a X: duas aguas
            try:
                roof.DefinesSlope[mc] = inclina
                if inclina:
                    roof.SlopeAngle[mc] = 0.30
            except Exception:
                roof.set_DefinesSlope(mc, inclina)
                if inclina:
                    roof.set_SlopeAngle(mc, 0.30)
    p = roof.get_Parameter(DB.BuiltInParameter.ROOF_LEVEL_OFFSET_PARAM)
    if p is not None:
        p.Set(0.15 * M)
    log(u"Telhado de duas águas ({}), 30%, beiral de 50 cm (não entra no orçamento do NeuralBIM)".format(nome(rt)))

telhado

# ---------------- 10. salvar e abrir ----------------
opt = DB.SaveAsOptions()
opt.OverwriteExistingFile = False
doc.SaveAs(DESTINO, opt)
LOG["arquivo"] = DESTINO
log(u"Projeto salvo: `{}`".format(DESTINO))
gravar_log()
doc.Close(False)
uiapp.OpenAndActivateDocument(DESTINO)
