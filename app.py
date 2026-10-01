import os
import random
import time
import uuid
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

PORT = int(os.environ.get("PORT", "10000"))

# Economia do jogo: pontos = ranking; moedas = moeda virtual para a futura loja.
RECOMPENSAS = {
    "hunt": {"pontos": 100, "moedas": 10},
    "price": {"pontos": 150, "moedas": 15},
    "duel": {"pontos": 50, "moedas": 5},
    "offer_view": {"pontos": 0, "moedas": 1},
    "daily": {"pontos": 25, "moedas": 20},
    "streak_3": {"pontos": 50, "moedas": 25},
    "streak_7": {"pontos": 150, "moedas": 100},
}

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


SHOP_ITEMS = {
    "double_points": {"id":"double_points","nome":"🔥 2x Pontos","descricao":"Dobre os pontos da próxima partida.","preco_moedas":150,"tipo":"boost"},
    "second_chance": {"id":"second_chance","nome":"❤️ Segunda Chance","descricao":"Item para continuar após um erro.","preco_moedas":50,"tipo":"utility"},
    "hint": {"id":"hint","nome":"🎯 Dica","descricao":"Revela uma pista em um desafio.","preco_moedas":30,"tipo":"utility"},
    "mystery_box": {"id":"mystery_box","nome":"📦 Baú Surpresa","descricao":"Receba um prêmio aleatório em moedas.","preco_moedas":100,"tipo":"random"},
}

jogadores = {}
jogadores_lock = Lock()

def hoje():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def novo_jogador(user_id, nome="Caçador"):
    return {
        "id":str(user_id),"nome":nome or "Caçador","pontos":0,"moedas":0,
        "sequencia":0,"partidas":0,"acertos":0,"erros":0,"ofertas_vistas":0,
        "melhor_sequencia":0,"ultima_partida":None,"ultimo_login":None,
        "bonus_diario_data":None,"bonus_diario_recebido":False,
        "ofertas_recompensadas":0,"inventario":{},"_rodadas":{}
    }

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

def aplicar_bonus_diario(jogador):
    dia = hoje()
    if jogador["bonus_diario_data"] == dia:
        return {"recebeu": False, "pontos": 0, "moedas": 0}
    jogador["bonus_diario_data"] = dia
    jogador["ultimo_login"] = int(time.time())
    jogador["bonus_diario_recebido"] = True
    jogador["pontos"] += RECOMPENSAS["daily"]["pontos"]
    jogador["moedas"] += RECOMPENSAS["daily"]["moedas"]
    return {"recebeu": True, **RECOMPENSAS["daily"]}

def registrar_acerto(jogador, modo):
    recompensa = RECOMPENSAS[modo]
    jogador["partidas"] += 1
    jogador["acertos"] += 1
    jogador["pontos"] += recompensa["pontos"]
    jogador["moedas"] += recompensa["moedas"]
    jogador["sequencia"] += 1
    jogador["melhor_sequencia"] = max(jogador["melhor_sequencia"], jogador["sequencia"])
    bonus = {"pontos": 0, "moedas": 0, "tipo": None}
    if jogador["sequencia"] == 3:
        jogador["pontos"] += RECOMPENSAS["streak_3"]["pontos"]
        jogador["moedas"] += RECOMPENSAS["streak_3"]["moedas"]
        bonus = {"pontos": RECOMPENSAS["streak_3"]["pontos"], "moedas": RECOMPENSAS["streak_3"]["moedas"], "tipo": "streak_3"}
    elif jogador["sequencia"] == 7:
        jogador["pontos"] += RECOMPENSAS["streak_7"]["pontos"]
        jogador["moedas"] += RECOMPENSAS["streak_7"]["moedas"]
        bonus = {"pontos": RECOMPENSAS["streak_7"]["pontos"], "moedas": RECOMPENSAS["streak_7"]["moedas"], "tipo": "streak_7"}
    return bonus

def registrar_erro(jogador):
    jogador["partidas"] += 1
    jogador["erros"] += 1
    jogador["sequencia"] = 0

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","service":"raposa-mini-game","jogadores":len(jogadores),"produtos":len(PRODUTOS),"timestamp":int(time.time())})

@app.get("/api/player")
def player():
    jogador = obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))
    bonus = aplicar_bonus_diario(jogador)
    resposta = jogador_publico(jogador)
    resposta["bonus_diario"] = bonus
    return jsonify(resposta)

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
    if not rodada: return jsonify({"ok":False,"erro":"Rodada expirada."}),400
    acertou = dados.get("produto_id") == rodada["alvo"]
    if acertou:
        bonus = registrar_acerto(jogador, "hunt")
    else:
        registrar_erro(jogador); bonus = {"pontos":0,"moedas":0,"tipo":None}
    jogador["ultima_partida"] = int(time.time())
    alvo = next((p for p in PRODUTOS if p["id"] == rodada["alvo"]), None)
    base = RECOMPENSAS["hunt"]
    return jsonify({"ok":True,"acertou":acertou,"pontos_ganhos":base["pontos"]+bonus["pontos"] if acertou else 0,"moedas_ganhas":base["moedas"]+bonus["moedas"] if acertou else 0,"bonus_sequencia":bonus,"achadinho":produto_publico(alvo),"player":jogador_publico(jogador)})

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
    if not rodada: return jsonify({"ok":False,"erro":"Rodada expirada."}),400
    try: resposta = round(float(dados.get("preco")),2)
    except (TypeError,ValueError): return jsonify({"ok":False,"erro":"Preço inválido."}),400
    produto = next((p for p in PRODUTOS if p["id"] == rodada["produto"]),None)
    if not produto: return jsonify({"ok":False,"erro":"Produto não encontrado."}),404
    acertou = resposta == round(produto["preco"],2)
    if acertou: bonus = registrar_acerto(jogador, "price")
    else: registrar_erro(jogador); bonus = {"pontos":0,"moedas":0,"tipo":None}
    jogador["ultima_partida"] = int(time.time())
    base = RECOMPENSAS["price"]
    return jsonify({"ok":True,"acertou":acertou,"pontos_ganhos":base["pontos"]+bonus["pontos"] if acertou else 0,"moedas_ganhas":base["moedas"]+bonus["moedas"] if acertou else 0,"bonus_sequencia":bonus,"preco_real":produto["preco"],"produto":produto_publico(produto),"player":jogador_publico(jogador)})

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
    if escolhido not in rodada["produtos"]: return jsonify({"ok":False,"erro":"Escolha inválida."}),400
    bonus = registrar_acerto(jogador, "duel")
    jogador["ofertas_vistas"] += 1
    jogador["ultima_partida"] = int(time.time())
    base = RECOMPENSAS["duel"]
    produto = next((p for p in PRODUTOS if p["id"] == escolhido),None)
    return jsonify({"ok":True,"pontos_ganhos":base["pontos"]+bonus["pontos"],"moedas_ganhas":base["moedas"]+bonus["moedas"],"bonus_sequencia":bonus,"produto":produto_publico(produto) if produto else None,"player":jogador_publico(jogador)})

@app.post("/api/offer/view")
def offer_view():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    produto = next((p for p in PRODUTOS if p["id"] == dados.get("produto_id")),None)
    if not produto: return jsonify({"ok":False,"erro":"Oferta não encontrada."}),404
    # Apenas 5 ofertas recompensadas por dia para evitar farming infinito de moedas.
    dia = hoje()
    chave = f"offer_day_{dia}"
    contador = jogador.get(chave, 0)
    recompensa = 0
    if contador < 5:
        jogador[chave] = contador + 1
        jogador["ofertas_vistas"] += 1
        jogador["ofertas_recompensadas"] += 1
        recompensa = RECOMPENSAS["offer_view"]["moedas"]
        jogador["moedas"] += recompensa
    return jsonify({"ok":True,"url":produto.get("url","#"),"moedas_ganhas":recompensa,"limite_diario":5,"player":jogador_publico(jogador)})

@app.get("/api/shop")
def shop():
    return jsonify(list(SHOP_ITEMS.values()))

@app.get("/api/inventory")
def inventory():
    jogador = obter_jogador(request.args.get("user_id","demo"), request.args.get("name","Caçador"))
    return jsonify({"moedas": jogador["moedas"], "inventario": jogador.get("inventario", {})})

@app.post("/api/shop/buy")
def shop_buy():
    dados = request.get_json(silent=True) or {}
    jogador = obter_jogador(dados.get("user_id","demo"), dados.get("name","Caçador"))
    item = SHOP_ITEMS.get(dados.get("item_id"))
    if not item: return jsonify({"ok":False,"erro":"Item não encontrado."}),404
    with jogadores_lock:
        if jogador["moedas"] < item["preco_moedas"]:
            return jsonify({"ok":False,"erro":"Você não tem moedas suficientes."}),400
        jogador["moedas"] -= item["preco_moedas"]
        if item["tipo"] == "random":
            premio = random.randint(50, 200)
            jogador["moedas"] += premio
            mensagem = f"🎉 O baú premiou você com {premio} moedas!"
            recebido = {"tipo":"moedas","quantidade":premio}
        else:
            inv = jogador.setdefault("inventario", {})
            inv[item["id"]] = inv.get(item["id"], 0) + 1
            mensagem = f"{item['nome']} adicionado ao seu inventário."
            recebido = {"tipo":"item","item_id":item["id"],"quantidade":inv[item["id"]]}
    return jsonify({"ok":True,"mensagem":mensagem,"recebido":recebido,"player":jogador_publico(jogador)})

@app.get("/api/ranking")
def ranking():
    with jogadores_lock:
        lista = sorted(jogadores.values(), key=lambda p:(p["pontos"],p["acertos"]), reverse=True)
        return jsonify([{"posicao":i+1,"nome":p["nome"],"pontos":p["pontos"],"moedas":p["moedas"],"sequencia":p["sequencia"]} for i,p in enumerate(lista[:20])])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
