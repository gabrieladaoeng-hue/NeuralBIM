# Servidor so-leitura para tirar prints do painel NeuralBIM com os dados da validacao (28/10/2026).
# Usa apenas a biblioteca padrao do Python. Abre em http://127.0.0.1:8010/painel/
import json, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = json.load(open(os.path.join(AQUI, "dados.json"), encoding="utf-8"))
PAGINAS = {"/painel/": "index.html", "/painel": "index.html", "/painel/estimativa": "painel.html",
           "/painel/fornecedores": "fornecedores.html", "/painel/obra": "obra.html", "/painel/mercado": "mercado.html"}
class H(BaseHTTPRequestHandler):
    def _env(self, corpo, tipo, cod=200):
        self.send_response(cod); self.send_header("Content-Type", tipo); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(corpo)
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in PAGINAS:
            return self._env(open(os.path.join(AQUI, "static", PAGINAS[p]), "rb").read(), "text/html; charset=utf-8")
        if p.startswith("/static/"):
            f = os.path.join(AQUI, "static", os.path.basename(p))
            if os.path.exists(f):
                return self._env(open(f, "rb").read(), "application/javascript" if f.endswith(".js") else "text/html; charset=utf-8")
        if p in DADOS:
            return self._env(json.dumps(DADOS[p], ensure_ascii=False).encode("utf-8"), "application/json")
        self._env(b'{"detail":"nao encontrado"}', "application/json", 404)
    def do_POST(self):
        self._env(b'{"detail":"servidor de prints: somente leitura"}', "application/json", 405)
    do_DELETE = do_POST
    def log_message(self, *a): pass
print("Painel NeuralBIM (prints) em http://127.0.0.1:8010/painel/  -  feche esta janela para parar.")
ThreadingHTTPServer(("127.0.0.1", 8010), H).serve_forever()
