import os
import random
import time
import uuid
from threading import Lock

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

PORT = int(os.environ.get("PORT", "10000"))

PRODUTOS = [
    {"id":"shopee-001","plataforma":"shopee","nome":"Fone Bluetooth sem fio","preco":39.90,"preco_anterior":89.90,"imagem":"🎧","categoria":"Eletrônicos","url":"#"},
    {"id":"ml-001","plataforma":"mercadolivre","nome":"Aspirador portátil USB","preco":49.90,"preco_anterior":99.90,"imagem":"🧹","categoria":"Casa","url":"#"},
    {"id":"shopee-002","plataforma":"shopee","nome":"Mini projetor portátil","preco":129.90,"preco_anterior":249.90,"imagem":"📽️","categoria":"Eletrônicos","url":"#"},
    {"id":"ml-002","plataforma":"mercadolivre","nome":"Smartwatch esportivo","preco":79.90,"preco_anterior":159.90,"imagem":"⌚","categoria":"Eletrônicos","url":"#"},
    {"id":"shopee-003","plataforma":"shopee","nome":"Organizador multiuso","preco":24.90,"preco_anterior":54.90,"imagem":"📦","categoria":"Casa","url":"#"},
    {"id":"ml-003","plataforma":"mercadolivre","nome":"Air Fryer 4L","preco":299.90,"preco_anterior":449.90,"imagem":"🍟","categoria":"Casa","url":"#"},
    {"id":"shopee-004","plataforma":"shopee","nome":"Luminária LED de mesa","preco":34.90,"preco_anterior":69.90,"imagem":"💡","categoria":"Casa","url":"#"},
    {"id":"ml-004","plataforma":"mercadolivre","nome":"Caixa de som Bluetooth","preco":89.90,"preco_anterior":149.90,"imagem":"🔊","categoria":"Eletrônicos","url":"#"},
]

jogadores = {}
jogadores_lock = Lock()

def novo_jogador(user_id, nome="Caçador"):
    return {"id":str(user_id),"nome":nome or "Caçador","pontos":0,"moedas":0,"sequencia":0,"partidas":0,"acertos":0,"erros":0,"ofertas_vistas":0,"melhor_sequencia":0,"ultima_partida":None,"_rodadas":{}}

def obter_jogador(user_id="demo", nome="Caçador"):
    jogador_id = str(user_id or "demo")
    with jogadores_lock:
        if jogador_id not in jogadores:
            jogadores[jogador_id] = novo_jogador(jogador_id, nome)
        elif nome:
            jogadores[jogador_id]["nome"] = nome
        return jogadores[jogador_id]

def jogador_publico(jogador):
    return {k:v for k,v in jogador.items() if not k.startswith("_")}

def produto_publico(produto):
    return {k:v for k,v in produto.items() if k != "url"}

def escolher_produtos(quantidade=3):
    return random.sample(PRODUTOS, min(quantidade, len(PRODUTOS)))

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","service":"raposa-mini-game","jogadores":len(jogadores),"produtos":len(PRODUTOS),"timestamp":int(time.time())})

@app.get("/api/player")
def player():
    return jsonify(jogador_publico(obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))))

@app.get("/api/game/hunt")
def hunt():
    jogador = obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))
    produtos = escolher_produtos(3)
    alvo = random.choice(produtos)
    rodada_id = str(uuid.uuid4())
    jogador["_rodadas"][rodada_id] = {"tipo":"hunt","alvo":alvo["id"],"criada":time.time()}
    return jsonify({"rodada_id":rodada_id,"caixas":[{"posicao":i,"produto":produto_publico(p)} for i,p in enumerate(produtos)]})

@app.post("/api/game/hunt/answer")
def hunt_answer():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    rodada = jogador["_rodadas"].pop(dados.get("rodada_id"), None)
    if not rodada:
        return jsonify({"ok":False,"erro":"Rodada expirada."}),400
    produto_id = dados.get("produto_id")
    acertou = produto_id == rodada["alvo"]
    jogador["partidas"] += 1
    if acertou:
        jogador["acertos"] += 1; jogador["pontos"] += 100; jogador["moedas"] += 10; jogador["sequencia"] += 1
        jogador["melhor_sequencia"] = max(jogador["melhor_sequencia"], jogador["sequencia"])
    else:
        jogador["erros"] += 1; jogador["sequencia"] = 0
    jogador["ultima_partida"] = int(time.time())
    alvo = next((p for p in PRODUTOS if p["id"] == rodada["alvo"]), None)
    return jsonify({"ok":True,"acertou":acertou,"pontos_ganhos":100 if acertou else 0,"moedas_ganhas":10 if acertou else 0,"achadinho":produto_publico(alvo),"player":jogador_publico(jogador)})

@app.get("/api/game/price")
def price_game():
    jogador = obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))
    produto = random.choice(PRODUTOS)
    rodada_id = str(uuid.uuid4())
    jogador["_rodadas"][rodada_id] = {"tipo":"price","produto":produto["id"],"criada":time.time()}
    opcoes = {produto["preco"]}
    while len(opcoes) < 3:
        opcoes.add(round(produto["preco"] * (1 + random.choice([-0.35,-0.2,0.2,0.35])), 2))
    opcoes = list(opcoes); random.shuffle(opcoes)
    return jsonify({"rodada_id":rodada_id,"produto":produto_publico(produto),"opcoes":opcoes})

@app.post("/api/game/price/answer")
def price_answer():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    rodada = jogador["_rodadas"].pop(dados.get("rodada_id"), None)
    if not rodada:
        return jsonify({"ok":False,"erro":"Rodada expirada."}),400
    try: resposta = round(float(dados.get("preco")),2)
    except (TypeError,ValueError): return jsonify({"ok":False,"erro":"Preço inválido."}),400
    produto = next((p for p in PRODUTOS if p["id"] == rodada["produto"]),None)
    if not produto: return jsonify({"ok":False,"erro":"Produto não encontrado."}),404
    acertou = resposta == round(produto["preco"],2)
    jogador["partidas"] += 1
    if acertou:
        jogador["acertos"] += 1; jogador["pontos"] += 150; jogador["moedas"] += 15; jogador["sequencia"] += 1
        jogador["melhor_sequencia"] = max(jogador["melhor_sequencia"], jogador["sequencia"])
    else:
        jogador["erros"] += 1; jogador["sequencia"] = 0
    jogador["ultima_partida"] = int(time.time())
    return jsonify({"ok":True,"acertou":acertou,"pontos_ganhos":150 if acertou else 0,"moedas_ganhas":15 if acertou else 0,"preco_real":produto["preco"],"produto":produto_publico(produto),"player":jogador_publico(jogador)})

@app.get("/api/game/duel")
def duel():
    produtos = escolher_produtos(2)
    rodada_id = str(uuid.uuid4())
    jogador = obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))
    jogador["_rodadas"][rodada_id] = {"tipo":"duel","produtos":[p["id"] for p in produtos],"criada":time.time()}
    return jsonify({"rodada_id":rodada_id,"produtos":[produto_publico(p) for p in produtos]})

@app.post("/api/game/duel/answer")
def duel_answer():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    rodada = jogador["_rodadas"].pop(dados.get("rodada_id"), None)
    if not rodada: return jsonify({"ok":False,"erro":"Rodada expirada."}),400
    escolhido = dados.get("produto_id")
    valido = escolhido in rodada["produtos"]
    jogador["partidas"] += 1; jogador["ofertas_vistas"] += 1
    if valido:
        jogador["acertos"] += 1; jogador["pontos"] += 50; jogador["moedas"] += 5; jogador["sequencia"] += 1
        jogador["melhor_sequencia"] = max(jogador["melhor_sequencia"], jogador["sequencia"])
    jogador["ultima_partida"] = int(time.time())
    produto = next((p for p in PRODUTOS if p["id"] == escolhido),None)
    return jsonify({"ok":True,"pontos_ganhos":50 if valido else 0,"produto":produto_publico(produto) if produto else None,"player":jogador_publico(jogador)})

@app.post("/api/offer/view")
def offer_view():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    jogador["ofertas_vistas"] += 1; jogador["moedas"] += 1
    produto = next((p for p in PRODUTOS if p["id"] == dados.get("produto_id")),None)
    return jsonify({"ok":True,"url":produto.get("url","#") if produto else "#","player":jogador_publico(jogador)})

@app.get("/api/ranking")
def ranking():
    with jogadores_lock:
        lista = sorted(jogadores.values(), key=lambda p:(p["pontos"],p["acertos"]), reverse=True)
        return jsonify([{"posicao":i+1,"nome":p["nome"],"pontos":p["pontos"],"sequencia":p["sequencia"]} for i,p in enumerate(lista[:20])])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
