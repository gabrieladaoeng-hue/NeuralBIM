# -*- coding: utf-8 -*-
"""Envio do lote de dados para a API NeuralBIM (Fase 2).

Usa System.Net.WebClient via clr (IronPython) - NAO usa a lib requests, que
nao existe no engine do pyRevit. Toda falha de rede e engolida: a funcao
sempre retorna (sucesso: bool, mensagem: str) e nunca deixa o script
principal quebrar por causa do envio."""

import os
import json


# URL da API. Sobrescreva com a variavel de ambiente NEURALBIM_API_URL.
# Padrao: API local na porta 8000, endpoint de ingestao.
_URL_PADRAO = "http://127.0.0.1:8000/elementos"


def _descrever_erro_envio(url, erro):
    """Traduz a excecao .NET/Python num texto util pra quem esta no Revit."""
    texto = str(erro)
    baixo = texto.lower()

    if ("unable to connect" in baixo
            or "actively refused" in baixo
            or "no connection could be made" in baixo):
        dica = "Nao foi possivel conectar a API - ela esta rodando?"
    elif "(404)" in texto:
        dica = "A API respondeu 404 - confira a URL ({}).".format(url)
    elif "(400)" in texto or "(422)" in texto:
        dica = "A API rejeitou os dados (payload fora do formato esperado)."
    elif ("timed out" in baixo or "timeout" in baixo
            or "operation has timed out" in baixo):
        # .NET lanca WebException com "The operation has timed out" quando o
        # HttpWebRequest.Timeout estoura -> o texto contem "timed out", cai aqui.
        limite = os.environ.get("NEURALBIM_API_TIMEOUT_MS", "5000")
        dica = ("A API aceitou a conexao mas nao respondeu dentro de {} ms "
                "(limite configuravel em NEURALBIM_API_TIMEOUT_MS). Ela pode "
                "estar travada ou sobrecarregada.".format(limite))
    else:
        dica = "Falha no envio para {}.".format(url)

    return "{}\nDetalhe tecnico: {}".format(dica, texto)


def _normalizar_unicode(valor):
    """Garante que toda string do payload seja unicode antes do json.dumps.

    NAO usa valor.decode(): o .decode() do IronPython estava lancando erro
    nesse texto ate com errors="replace". Aqui os bytes crus do str (1 char
    = 1 byte no Python 2) sao convertidos pelo System.Text.Encoding do .NET
    via clr - o mesmo caminho do WebClient. O GetString do .NET substitui
    bytes invalidos silenciosamente, nao lanca. Ordem: UTF-8 -> Windows-1252.
    """
    if isinstance(valor, (int, long)) and not isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, unicode):
        return valor
    if isinstance(valor, str):
        try:
            dados_brutos = bytearray(ord(c) & 0xFF for c in valor)
        except Exception:
            return valor

        try:
            import clr
            clr.AddReference("System")
            from System.Text import Encoding
            from System import Array, Byte
            array_bytes = Array[Byte](dados_brutos)
            return Encoding.UTF8.GetString(array_bytes)
        except Exception:
            pass

        try:
            array_bytes = Array[Byte](dados_brutos)
            return Encoding.GetEncoding(1252).GetString(array_bytes)
        except Exception:
            return valor
    if isinstance(valor, dict):
        return {_normalizar_unicode(k): _normalizar_unicode(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_normalizar_unicode(item) for item in valor]

    # float e None ja sao serializaveis pelo json - passam direto.
    # (Sem esta linha, o int(valor) abaixo truncaria floats: 2.45 -> 2.)
    if isinstance(valor, float) or valor is None:
        return valor

    # Tipos numericos do .NET (ex.: Int64) que isinstance(valor, (int, long))
    # nao reconhece: tenta int, depois float; se nem isso, devolve como veio.
    try:
        return int(valor)
    except Exception:
        pass
    try:
        return float(valor)
    except Exception:
        pass
    return valor


def enviar_dados_para_api(timestamp_inicio, timestamp_fim, dados_finais):
    """Monta o payload, serializa com json.dumps e envia via WebClient (POST).

    Retorna sempre uma tupla (sucesso: bool, mensagem: str):
    - sucesso=True  -> mensagem e a resposta que a API devolveu;
    - sucesso=False -> mensagem descreve o problema (API fora do ar, sem
      conexao, timeout, erro de formato, etc). A excecao NUNCA sobe.
    """
    url = os.environ.get("NEURALBIM_API_URL", _URL_PADRAO)

    payload = {
        "timestamp_inicio_execucao": timestamp_inicio,
        "timestamp_fim_execucao": timestamp_fim,
        "elementos": dados_finais,
    }

    try:
        payload = _normalizar_unicode(payload)
        payload_json = json.dumps(payload, ensure_ascii=False)
    except Exception as erro:
        return (False, "Falha ao montar o JSON do envio.\nDetalhe tecnico: {}".format(erro))

    try:
        import clr
        clr.AddReference("System")
        from System.Net import WebClient, HttpRequestHeader
        from System.Text import Encoding

        # Timeout de rede em ms (padrao 5000). Sem sobrescrever, o .NET usa
        # ~100000 ms (100 s), o que pode travar o Revit se a API aceitar a
        # conexao mas nao responder.
        timeout_ms = int(os.environ.get("NEURALBIM_API_TIMEOUT_MS", "5000"))

        class _WebClientComTimeout(WebClient):
            """WebClient com timeout: o WebClient padrao nao expoe Timeout,
            entao sobrescrevemos GetWebRequest pra setar no HttpWebRequest."""
            def GetWebRequest(self, address):
                request = WebClient.GetWebRequest(self, address)
                request.Timeout = timeout_ms
                return request

        cliente = _WebClientComTimeout()
        cliente.Encoding = Encoding.UTF8
        cliente.Headers[HttpRequestHeader.ContentType] = "application/json; charset=utf-8"

        resposta = cliente.UploadString(url, "POST", payload_json)
        return (True, "API respondeu:\n{}".format(resposta))
    except Exception as erro:
        return (False, _descrever_erro_envio(url, erro))
