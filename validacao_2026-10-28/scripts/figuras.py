import json, glob, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D = "/home/claude/validacao/dados/"; O = "/home/claude/validacao/figuras/"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": SURF, "axes.facecolor": SURF})
brl = lambda v: ("R$ {:,.2f}".format(v)).replace(",", "X").replace(".", ",").replace("X", ".")
def estilo(ax, grid_axis="y"):
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8); ax.set_axisbelow(True)

cmp = json.load(open(D + "comparacao_neuralbim_x_referencia.json", encoding="utf-8"))
ai = json.load(open(D + "execucoes_ia_2026-10-28.json", encoding="utf-8"))

# F1 - erro por parede
par = [l for l in cmp["por_elemento"] if l["categoria"] == "Parede"]
fig, ax = plt.subplots(figsize=(8, 4.6))
nomes = ["{} ({})".format(l["id"], "ext." if "Externa" in l["tipo"] else "int.") for l in par]
vals = [l["erro_pct"] for l in par]
ax.barh(nomes, vals, color=BLUE, height=0.6)
ax.axvline(0, color=INK2, linewidth=1)
for i, v in enumerate(vals):
    ax.text(v + (0.25 if v >= 0 else -0.25), i, "{:+.2f}%".format(v).replace(".", ","), va="center", ha="left" if v >= 0 else "right", color=INK, fontsize=9)
ax.invert_yaxis(); ax.set_xlim(-13, 6); estilo(ax, "x")
ax.set_xlabel("Diferença NeuralBIM × referência pelo eixo (%)")
ax.set_title("Área de parede por elemento: NeuralBIM × medição pelo eixo", loc="left", fontsize=12)
fig.text(0.01, 0.01, "Referência: comprimento de eixo × altura − vãos. O Revit não conta duas vezes os encontros de paredes; a diferença total\n(−4,05% nas internas, 0,01% nas externas) equivale à sobreposição nos encontros.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(O + "fig01_erro_paredes_por_elemento.png", dpi=200); plt.close(fig)

# F2 - custo por categoria
cats = ["Parede", "Laje", "Pilar"]
merc = json.load(open(D + "estimativa_mercado_lote_2026-10-28_20-39-25_2026-10-28_20-43-06.json", encoding="utf-8"))
m = {c: [0, 0, 0] for c in cats}
for x in merc["estimativa_por_elemento"]:
    m[x["categoria"]][0] += x["custo_minimo_rs"]; m[x["categoria"]][1] += x["custo_provavel_rs"]; m[x["categoria"]][2] += x["custo_maximo_rs"]
nbv = [cmp["por_categoria"][c]["custo_nb"] for c in cats]; rfv = [cmp["por_categoria"][c]["custo_ref"] for c in cats]; mkv = [m[c][1] for c in cats]
fig, ax = plt.subplots(figsize=(8, 4.6)); w = 0.26; xs = range(3)
b1 = ax.bar([x - w for x in xs], nbv, w - 0.02, color=BLUE, label="NeuralBIM (SINAPI)")
b2 = ax.bar(list(xs), rfv, w - 0.02, color=ORANGE, label="Referência pelo eixo (SINAPI)")
b3 = ax.bar([x + w for x in xs], mkv, w - 0.02, color=AQUA, label="IA sem tabela (mercado, provável)")
ax.errorbar([x + w for x in xs], mkv, yerr=[[mkv[i] - m[c][0] for i, c in enumerate(cats)], [m[c][2] - mkv[i] for i, c in enumerate(cats)]], fmt="none", ecolor=INK2, capsize=4, linewidth=1)
tops = {id(b3[i]): m[c][2] for i, c in enumerate(cats)}
for bars in (b1, b2, b3):
    for r in bars:
        ax.text(r.get_x() + r.get_width() / 2, tops.get(id(r), r.get_height()) + 400, "{:.1f}k".format(r.get_height() / 1000).replace(".", ","), ha="center", fontsize=8, color=INK)
ax.set_xticks(list(xs)); ax.set_xticklabels(cats); ax.set_ylabel("Custo (R$)"); estilo(ax)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: "{:,.0f}".format(v).replace(",", ".")))
ax.legend(frameon=False, fontsize=9, loc="upper right")
ax.set_title("Custo por categoria — CasaMCMV 65 m² (SINAPI-PR 07/2026)", loc="left", fontsize=12)
fig.text(0.01, 0.01, "Barra de erro do modo mercado = faixa mínima–máxima declarada pela IA.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(O + "fig02_custo_por_categoria.png", dpi=200); plt.close(fig)

# F3 - repetibilidade dos totais
sin = [("26/10", 56269.11)] * 3 + [("28/10", x["total"]) for x in ai["ai"]["sinapi"]]
mer = []
for f in sorted(glob.glob(D + "estimativa_mercado_*.json")):
    d = json.load(open(f, encoding="utf-8")); mer.append((f.split("_")[-2][5:].replace("-", "/")[::-1][::-1], d["custo_total_provavel_rs"], d["custo_total_minimo_rs"], d["custo_total_maximo_rs"]))
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.plot(range(1, len(sin) + 1), [v for _, v in sin], "o-", color=BLUE, linewidth=2, markersize=8, label="Modo SINAPI (NeuralBIM)")
xm = list(range(1, len(mer) + 1))
ax.plot(xm, [v[1] for v in mer], "s-", color=ORANGE, linewidth=2, markersize=8, label="Modo mercado (IA sem tabela), provável")
ax.fill_between(xm, [v[2] for v in mer], [v[3] for v in mer], color=ORANGE, alpha=0.12, linewidth=0)
ax.annotate(brl(56269.11) + " em todas as 8 execuções", (len(sin), 56269.11), xytext=(-10, 10), textcoords="offset points", ha="right", fontsize=9, color=INK)
ax.annotate(brl(mer[0][1]) + " (26/10)", (1, mer[0][1]), xytext=(8, -16), textcoords="offset points", fontsize=9, color=INK)
ax.annotate(brl(mer[-1][1]) + " (28/10)", (len(mer), mer[-1][1]), xytext=(-8, 10), textcoords="offset points", ha="right", fontsize=9, color=INK)
ax.set_ylim(0, 65000); ax.set_xlabel("Execução (mesmo modelo, mesmos 20 elementos)"); ax.set_ylabel("Custo total (R$)")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: "{:,.0f}".format(v).replace(",", "."))); estilo(ax)
ax.legend(frameon=False, fontsize=9, loc="lower right")
ax.set_title("Repetibilidade do custo total entre execuções", loc="left", fontsize=12)
fig.tight_layout(); fig.savefig(O + "fig03_repetibilidade.png", dpi=200); plt.close(fig)

# F4 - tempos
plug = [("26/10 20:16", 24), ("26/10 20:41", 20), ("28/10 20:34", 49), ("28/10 20:36", 32), ("28/10 20:37", 28), ("28/10 20:39", 29)]
ia_s = [x["seg"] for x in ai["ai"]["sinapi"]]; ia_m = [x["seg"] for x in ai["ai"]["mercado"]]
fig, ax = plt.subplots(figsize=(8, 3.8))
grupos = [("Plugin (seleção + extração + envio)", [v for _, v in plug], BLUE), ("IA modo SINAPI (5 chamadas)", ia_s, ORANGE), ("IA modo mercado (5 chamadas)", ia_m, AQUA)]
for i, (n, vs, c) in enumerate(grupos):
    ax.scatter(vs, [i] * len(vs), s=70, color=c, edgecolor=SURF, linewidth=2, zorder=3)
    med = sum(vs) / len(vs)
    ax.text(max(vs) + 1.5, i, "média {:.1f} s (n={})".format(med, len(vs)).replace(".", ","), va="center", fontsize=9, color=INK)
ax.set_yticks(range(3)); ax.set_yticklabels([g[0] for g in grupos]); ax.invert_yaxis(); ax.set_xlim(0, 70)
ax.set_xlabel("Tempo (s)"); estilo(ax, "x")
ax.set_title("Tempo de execução por etapa", loc="left", fontsize=12)
fig.text(0.01, 0.01, "Plugin: carimbos de início/fim gravados no lote (inclui o tempo humano de seleção). IA: tempo da requisição medido no navegador.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(O + "fig04_tempos.png", dpi=200); plt.close(fig)
print("ok")
