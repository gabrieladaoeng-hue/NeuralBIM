"""Compara quantitativos do NeuralBIM (lote do plugin) com a referencia geometrica
medida no Revit (botao Medir Referencia) e aplica precos SINAPI-PR identicos."""
import json, csv, sys, statistics
D = "/home/claude/validacao/dados/"
lote = json.load(open(D + "lote_2026-10-28_20-39-25.json", encoding="utf-8"))
ref = json.load(open(D + "referencia_CasaMCMV_65m2_VALIDACAO_2026-10-28.json", encoding="utf-8"))
nb = {int(e["ID"]): e for e in lote["elementos"]}
# precos SINAPI-PR 07/2026 nao desonerado (conferidos contra a planilha oficial em 26/10)
P = {"parede14": 186.09, "parede9": 227.14, "piso": 150.49, "laje": 207.51,
     "arm": 11.77, "fab": 129.79, "mont": 129.71, "conc": 1020.68}
linhas = []
for w in ref["paredes"]:
    e = nb[int(w["id"])]
    pr = P["parede14"] if w["espessura_estrutural_cm"] >= 12 else P["parede9"]
    linhas.append(dict(id=w["id"], categoria="Parede", tipo=w["tipo"], unidade="m2", ref=w["area_liquida_eixo_m2"], nb=e["Area_m2"],
                       ref_bruta=w["area_bruta_eixo_m2"], vaos=w["area_vaos_m2"], comp_eixo=w["comprimento_eixo_m"], preco=pr, posicao=e.get("Posicao")))
for f in ref["lajes"]:
    e = nb[int(f["id"])]
    pr = P["piso"] if "Piso" in f["tipo"] else P["laje"]
    linhas.append(dict(id=f["id"], categoria="Laje", tipo=f["tipo"], unidade="m2", ref=f["area_contorno_m2"], nb=e["Area_m2"], preco=pr))
for p in ref["pilares"]:
    e = nb[int(p["id"])]
    linhas.append(dict(id=p["id"], categoria="Pilar", tipo=p["tipo"], unidade="m3", ref=p["volume_m3"], nb=e["Volume_m3"],
                       ref_forma=p["area_forma_m2"], nb_forma=e["Area_Forma_m2"], preco=None))
def custo_pilar(vol, forma):
    return vol * 130 * P["arm"] + forma * (P["fab"] + P["mont"]) + vol * P["conc"]
for l in linhas:
    l["erro_pct"] = round((l["nb"] - l["ref"]) / l["ref"] * 100, 3)
    if l["categoria"] == "Pilar":
        l["custo_ref"] = round(custo_pilar(l["ref"], l["ref_forma"]), 2)
        l["custo_nb"] = round(custo_pilar(l["nb"], l["nb_forma"]), 2)
        l["erro_forma_pct"] = round((l["nb_forma"] - l["ref_forma"]) / l["ref_forma"] * 100, 3)
    else:
        l["custo_ref"] = round(l["ref"] * l["preco"], 2)
        l["custo_nb"] = round(l["nb"] * l["preco"], 2)
res = {"por_elemento": linhas, "por_categoria": {}}
for cat in ("Parede", "Laje", "Pilar"):
    ls = [l for l in linhas if l["categoria"] == cat]
    res["por_categoria"][cat] = dict(n=len(ls), qtd_ref=round(sum(l["ref"] for l in ls), 3), qtd_nb=round(sum(l["nb"] for l in ls), 3),
                                     mape_pct=round(statistics.mean(abs(l["erro_pct"]) for l in ls), 3),
                                     max_abs_pct=round(max(abs(l["erro_pct"]) for l in ls), 3),
                                     acima_5pct=sum(1 for l in ls if abs(l["erro_pct"]) > 5),
                                     custo_ref=round(sum(l["custo_ref"] for l in ls), 2), custo_nb=round(sum(l["custo_nb"] for l in ls), 2))
cr = sum(v["custo_ref"] for v in res["por_categoria"].values()); cn = sum(v["custo_nb"] for v in res["por_categoria"].values())
res["total"] = dict(custo_ref=round(cr, 2), custo_nb=round(cn, 2), dif_rs=round(cn - cr, 2), dif_pct=round((cn - cr) / cr * 100, 3),
                    mape_geral_pct=round(statistics.mean(abs(l["erro_pct"]) for l in linhas), 3),
                    acima_5pct=sum(1 for l in linhas if abs(l["erro_pct"]) > 5))
json.dump(res, open(D + "comparacao_neuralbim_x_referencia.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(D + "comparacao_neuralbim_x_referencia.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["ID", "Categoria", "Tipo", "Unidade", "Qtd referencia", "Qtd NeuralBIM", "Erro %", "Custo referencia (R$)", "Custo NeuralBIM (R$)"])
    for l in linhas:
        w.writerow([l["id"], l["categoria"], l["tipo"], l["unidade"], str(l["ref"]).replace(".", ","), str(l["nb"]).replace(".", ","),
                    str(l["erro_pct"]).replace(".", ","), str(l["custo_ref"]).replace(".", ","), str(l["custo_nb"]).replace(".", ",")])
for l in linhas:
    print(l["categoria"], l["id"], l["tipo"][:22], l["ref"], l["nb"], l["erro_pct"], l.get("posicao"))
print(json.dumps(res["por_categoria"], indent=1, ensure_ascii=False)); print(res["total"])
