/* Funcoes de formatacao compartilhadas entre as 4 paginas do painel
   (index.html, painel.html, fornecedores.html, obra.html) -- arquivo
   estatico separado, servido pela mesma StaticFiles em /static (sem build
   step). Incluir com <script src="/static/formatadores.js"></script> ANTES
   do <script> proprio de cada pagina. */
(function (global) {
  "use strict";

  function fmtBRL(valor) {
    if (typeof valor !== "number" || isNaN(valor)) return "—";
    return valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function fmtNum(valor, casas) {
    if (typeof valor !== "number" || isNaN(valor)) return "—";
    return valor.toLocaleString("pt-BR", {
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    });
  }

  function fmtData(iso) {
    if (!iso) return "—";
    var data = String(iso).slice(0, 10);
    var partes = data.split("-");
    if (partes.length !== 3) return iso;
    return partes[2] + "/" + partes[1] + "/" + partes[0];
  }

  // Casas decimais por unidade SINAPI (regra do projeto: R$ = 2, ver fmtBRL;
  // m2/m3 = 3; kg = 1). Usado onde quantidade e unidade aparecem juntas,
  // como nos componentes detalhados de painel.html.
  function casasPorUnidade(unidade) {
    var chave = String(unidade || "").toUpperCase();
    if (chave === "KG") return 1;
    if (chave === "M2" || chave === "M3") return 3;
    return 2;
  }

  function fmtQtd(valor, unidade) {
    return fmtNum(valor, casasPorUnidade(unidade));
  }

  var MAPA_ESCAPE = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  // Escapa texto de origem externa (resposta da IA, notas de configuracao)
  // antes de entrar em innerHTML -- usado em painel.html no bloco
  // "Considerações da análise" (memoria_calculo/suposicoes vem do Bedrock).
  function escapeHtml(valor) {
    return String(valor == null ? "" : valor).replace(/[&<>"']/g, function (c) {
      return MAPA_ESCAPE[c];
    });
  }

  // Le um valor digitado no formato brasileiro ou com ponto decimal e devolve
  // Number (ou NaN se o texto nao for um numero valido). Aceita:
  //   "1500"  "1500,50"  "1.500,50"  "30.000"  "12.50"  "R$ 1.234,56"
  // Rejeita texto com sobra (ex.: "12abc") e formatos ambiguos/ingleses
  // ("1,234.56"). Ponto seguido de exatamente 3 digitos (em grupos) e
  // separador de milhar; virgula e sempre decimal.
  function lerValorBR(texto) {
    var t = String(texto == null ? "" : texto).replace(/R\$/i, "").replace(/\s+/g, "");
    if (/^\d+$/.test(t)) return Number(t);
    if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(t)) return Number(t.replace(/\./g, "").replace(",", "."));
    if (/^\d+,\d+$/.test(t)) return Number(t.replace(",", "."));
    if (/^\d+\.\d+$/.test(t)) return Number(t);
    return NaN;
  }

  global.fmtBRL = fmtBRL;
  global.fmtNum = fmtNum;
  global.fmtData = fmtData;
  global.fmtQtd = fmtQtd;
  global.escapeHtml = escapeHtml;
  global.lerValorBR = lerValorBR;
})(window);
