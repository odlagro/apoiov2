
from flask import Flask, render_template, jsonify, request
import requests, csv, io, datetime, json, os, time

app = Flask(__name__)

# --------------------------------------------------------------------
# CONFIGURAÇÕES DAS PLANILHAS
# --------------------------------------------------------------------
URL_PROD = "https://docs.google.com/spreadsheets/d/1Ycsc6ksvaO5EwOGq_w-N8awTKUyuo7awwu2IzRNfLVg/export?format=csv&gid=0"
URL_FRETE = "https://docs.google.com/spreadsheets/d/1Ycsc6ksvaO5EwOGq_w-N8awTKUyuo7awwu2IzRNfLVg/export?format=csv&gid=117017797"

# --------------------------------------------------------------------
# CONFIGURAÇÃO DO CHATGURU (CARREGADO DA TELA DE CONFIG)
# --------------------------------------------------------------------
CONFIG_PATH = "config_chatguru.json"


def default_chatguru_config():
    """Valores padrão. Pode ser alterado pela tela /config."""
    return {
        # endpoint padrão igual ao sistema de importação
        "api_endpoint": "https://app3.zap.guru/api/v1",
        "chatguru_key": "N64RWGMFP98HRZEPUX3WA72F86G1U9UXF4DMSU0IUDDQ4ERNCKUOR201A3RWBRZM",
        "chatguru_account_id": "5eb1a70a822d431767b96d80",
        # compat: phone_id "antigo"
        "chatguru_phone_id": "643ea3236481871e692f0983",
        # novos parâmetros: dois aparelhos
        "chatguru_phone_id_1": "643ea3236481871e692f0983",
        "chatguru_phone_id_1_label": "(33) 9943-1200",
        "chatguru_phone_id_2": "",
        "chatguru_phone_id_2_label": "",
        "chatguru_dialog_id": "64318160366d4a5562f9333e",
        # mensagens de encerramento
        "msg_final_um": "Qual desse modelo lhe interessa?",
        "msg_final_varios": "Qual desses modelos lhe interessa?",
        # desconto padrão à vista (%)
        "desconto_padrao": 12.0,
    }


def load_chatguru_config():
    if not os.path.exists(CONFIG_PATH):
        save_chatguru_config(default_chatguru_config())
        return default_chatguru_config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    cfg = default_chatguru_config()
    cfg.update(data or {})
    # compat: se phone_id_1 estiver vazio, copia do antigo
    if not cfg.get("chatguru_phone_id_1") and cfg.get("chatguru_phone_id"):
        cfg["chatguru_phone_id_1"] = cfg["chatguru_phone_id"]
    return cfg


def save_chatguru_config(data):
    cfg = default_chatguru_config()
    cfg.update(data or {})
    # mantém compat: campo antigo sempre igual ao phone_id_1
    if cfg.get("chatguru_phone_id_1"):
        cfg["chatguru_phone_id"] = cfg["chatguru_phone_id_1"]
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# --------------------------------------------------------------------
# FUNÇÕES DE APOIO
# --------------------------------------------------------------------
def fetch_rows(url):
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    text = r.content.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    return list(csv.reader(io.StringIO(text)))


def to_float_brl(s):
    s = (s or "").strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def chatguru_post(extra_params, phone_id=None):
    """Envia POST para o ChatGuru já incluindo key, account_id e phone_id.

    phone_id: se informado, usa esse. Caso contrário, usa o phone_id_1 ou o antigo.
    """
    cfg = load_chatguru_config()
    endpoint = (cfg.get("api_endpoint") or "").strip() or "https://app3.zap.guru/api/v1"
    final_phone = (phone_id
                   or cfg.get("chatguru_phone_id_1")
                   or cfg.get("chatguru_phone_id")
                   or "").strip()
    base = {
        "key": (cfg.get("chatguru_key") or "").strip(),
        "account_id": (cfg.get("chatguru_account_id") or "").strip(),
        "phone_id": final_phone,
    }
    data = {**base, **(extra_params or {})}

    resp = requests.post(endpoint, data=data, timeout=30)
    try:
        js = resp.json()
    except Exception:
        js = {"raw": resp.text}
    return resp.status_code, js


# --------------------------------------------------------------------
# PÁGINAS
# --------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config_view():
    return render_template("config.html")


# --------------------------------------------------------------------
# APIs DE PRODUTOS / FRETE
# --------------------------------------------------------------------
@app.route("/api/produtos")
def api_produtos():
    rows = fetch_rows(URL_PROD)
    if len(rows) < 5:
        return jsonify(ok=False, error="CSV de produtos vazio")

    header = [c.strip().upper() for c in rows[3]]

    def col(name, fb):
        try:
            return header.index(name)
        except ValueError:
            return fb

    i_modelo = col("MODELO", 2)
    i_avista = col("A VISTA", 3)
    i_cartao = col("CARTÃO", 4)
    i_10x = col("PARCELA EM 10X", 5)
    i_ind = col("INDICADA", 6)
    i_img = 8

    data = []
    for r in rows[4:]:
        if len(r) < 9:
            r += [""] * (9 - len(r))
        nome = (r[i_modelo] or "").strip()
        if not nome:
            continue
        produto = {
            "produto": nome,
            "cartao": to_float_brl(r[i_cartao]),
            "avista": to_float_brl(r[i_avista]),
            "dezx": to_float_brl(r[i_10x]),
            "indicada": r[i_ind],
            "imagem": (r[i_img] or "").strip(),
        }
        data.append(produto)
    return jsonify(ok=True, data=data)


@app.route("/api/fretes")
def api_fretes():
    rows = fetch_rows(URL_FRETE)
    out = []
    start = 4
    uf_col = 1
    val_col = 2
    for r in rows[start:]:
        if len(r) <= uf_col:
            continue
        uf = (r[uf_col] or "").strip()
        if not uf:
            continue
        val = to_float_brl(r[val_col] if len(r) > val_col else "0")
        out.append({"uf": uf, "valor": val})
    return jsonify(ok=True, data=out)


# --------------------------------------------------------------------
# API: CONFIG CHATGURU (GET/POST) + TESTE
# --------------------------------------------------------------------
@app.route("/api/chatguru_config", methods=["GET", "POST"])
def api_chatguru_config():
    if request.method == "GET":
        cfg = load_chatguru_config()
        return jsonify(ok=True, data=cfg)

    data = request.get_json(silent=True) or {}
    cfg = {
        "api_endpoint": (data.get("api_endpoint") or "").strip(),
        "chatguru_key": (data.get("chatguru_key") or "").strip(),
        "chatguru_account_id": (data.get("chatguru_account_id") or "").strip(),
        # telefones
        "chatguru_phone_id_1": (data.get("chatguru_phone_id_1") or "").strip(),
        "chatguru_phone_id_1_label": (data.get("chatguru_phone_id_1_label") or "").strip(),
        "chatguru_phone_id_2": (data.get("chatguru_phone_id_2") or "").strip(),
        "chatguru_phone_id_2_label": (data.get("chatguru_phone_id_2_label") or "").strip(),
        "chatguru_dialog_id": (data.get("chatguru_dialog_id") or "").strip(),
        "msg_final_um": (data.get("msg_final_um") or "").strip(),
        "msg_final_varios": (data.get("msg_final_varios") or "").strip(),
        "desconto_padrao": float(data.get("desconto_padrao") or 0),
    }
    # compat: campo antigo
    if cfg.get("chatguru_phone_id_1"):
        cfg["chatguru_phone_id"] = cfg["chatguru_phone_id_1"]
    return jsonify(ok=True, data=save_chatguru_config(cfg))


@app.route("/api/chatguru_test", methods=["POST"])
def api_chatguru_test():
    """Botão 'Testar conexão'. Usa phone_id_1 por padrão."""
    payload = request.get_json(silent=True) or {}
    numero_teste = (payload.get("numero_teste") or "").strip()
    if not numero_teste:
        return jsonify(ok=False, error="Informe um número para teste."), 400

    numero_teste = "".join(ch for ch in numero_teste if ch.isdigit())
    if not numero_teste:
        return jsonify(ok=False, error="Número de teste inválido."), 400

    cfg = load_chatguru_config()
    dialog_id = (cfg.get("chatguru_dialog_id") or "").strip()
    phone_id_1 = (cfg.get("chatguru_phone_id_1") or cfg.get("chatguru_phone_id") or "").strip()

    extra = {
        "action": "chat_add",
        "name": "Teste de conexão APOIOV2",
        "text": "Teste de conexão da integração APOIOV2 com ChatGuru.",
        "chat_number": numero_teste,
    }
    if dialog_id:
        extra["dialog_id"] = dialog_id

    try:
        status, js = chatguru_post(extra, phone_id=phone_id_1)
    except Exception as e:
        return jsonify(ok=False, error=f"Erro de requisição: {e}"), 500

    description = ""
    if isinstance(js, dict):
        description = js.get("description") or js.get("error") or ""
    ok = isinstance(js, dict) and js.get("result") == "success"

    hint = None
    if not ok:
        if "Conta não encontrada" in description:
            hint = "Conta não encontrada: verifique se KEY, account_id e phone_id são exatamente os mesmos mostrados no ChatGuru."
        elif "phone" in description.lower():
            hint = "Verifique se o phone_id realmente pertence a esse account_id e se está ativo."
        elif "Número" in description and "informado" in description:
            hint = "A API reclamou do número: mesmo assim, isso indica que a autenticação funcionou."

    return jsonify(
        ok=ok,
        status=status,
        resposta=js,
        description=description,
        hint=hint,
    )


# --------------------------------------------------------------------
# API: ENVIO DE MENSAGENS + DIÁLOGO
# --------------------------------------------------------------------
@app.route("/api/enviar_chatguru", methods=["POST"])
def api_enviar_chatguru():
    """Envia imagens dos produtos + executa diálogo + mensagem final."""
    payload = request.get_json(silent=True) or {}
    numero = (payload.get("numero") or "").strip()
    mensagens = payload.get("mensagens") or []
    phone_slot = (payload.get("phone_slot") or "").strip()  # "1" ou "2"

    if not numero:
        return jsonify(ok=False, error="Número do WhatsApp não informado."), 400
    if not mensagens:
        return jsonify(ok=False, error="Nenhum produto selecionado para envio."), 400
    if phone_slot not in ("1", "2"):
        return jsonify(ok=False, error="Selecione o aparelho pelo qual será enviada a mensagem (phone_id 1 ou 2)."), 400

    # Remove tudo que não for dígito, a API espera apenas números (DDI+DDD+número)
    numero = "".join(ch for ch in numero if ch.isdigit())

    cfg = load_chatguru_config()
    dialog_id = (cfg.get("chatguru_dialog_id") or "").strip()
    msg_final_um = (cfg.get("msg_final_um") or "").strip() or "Qual desse modelo lhe interessa?"
    msg_final_varios = (cfg.get("msg_final_varios") or "").strip() or "Qual desses modelos lhe interessa?"

    if phone_slot == "1":
        chosen_phone = (cfg.get("chatguru_phone_id_1") or cfg.get("chatguru_phone_id") or "").strip()
        phone_label = cfg.get("chatguru_phone_id_1_label") or "Aparelho 1"
    else:
        chosen_phone = (cfg.get("chatguru_phone_id_2") or "").strip()
        phone_label = cfg.get("chatguru_phone_id_2_label") or "Aparelho 2"

    if not chosen_phone:
        return jsonify(ok=False, error=f"O {phone_label} não está configurado nas Configurações ChatGuru."), 400

    qtd_produtos = len(mensagens)

    resultados = []
    sucesso = False
    primeira_descricao_erro = None

    try:
        # 1) Envia imagens dos produtos (com preço no caption)
        for m in mensagens:
            img_url = (m.get("imagem_url") or "").strip()
            texto = (m.get("texto") or "").strip()

            if img_url:
                caption = texto or "Imagem do produto"
                status, resp_js = chatguru_post(
                    {
                        "action": "message_file_send",
                        "chat_number": numero,
                        "file_url": img_url,
                        "caption": caption,
                    },
                    phone_id=chosen_phone,
                )
                resultados.append(
                    {"tipo": "arquivo_com_caption", "status": status, "resposta": resp_js}
                )
                if isinstance(resp_js, dict):
                    if resp_js.get("result") == "success":
                        sucesso = True
                    else:
                        desc = resp_js.get("description") or resp_js.get("error") or ""
                        if desc and not primeira_descricao_erro:
                            primeira_descricao_erro = desc

                # Aguarda 3 segundos antes do próximo produto
                time.sleep(3)
            else:
                # fallback: sem imagem, envia apenas texto
                if texto:
                    send_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    status, resp_js = chatguru_post(
                        {
                            "action": "message_send",
                            "chat_number": numero,
                            "send_date": send_date,
                            "text": texto,
                        },
                        phone_id=chosen_phone,
                    )
                    resultados.append(
                        {"tipo": "mensagem", "status": status, "resposta": resp_js}
                    )
                    if isinstance(resp_js, dict):
                        if resp_js.get("result") == "success":
                            sucesso = True
                        else:
                            desc = resp_js.get("description") or resp_js.get("error") or ""
                            if desc and not primeira_descricao_erro:
                                primeira_descricao_erro = desc
                    time.sleep(3)

        # 2) Executa o DIÁLOGO configurado
        if dialog_id:
            status, resp_js = chatguru_post(
                {
                    "action": "dialog_execute",
                    "dialog_id": dialog_id,
                    "chat_number": numero,
                },
                phone_id=chosen_phone,
            )
            resultados.append(
                {"tipo": "dialogo", "status": status, "resposta": resp_js}
            )
            if isinstance(resp_js, dict):
                if resp_js.get("result") == "success":
                    sucesso = True
                else:
                    desc = resp_js.get("description") or resp_js.get("error") or ""
                    if desc and not primeira_descricao_erro:
                        primeira_descricao_erro = desc

        # 3) Mensagem de encerramento (5s após TUDO)
        msg_final = ""
        if qtd_produtos == 1:
            msg_final = msg_final_um
        elif qtd_produtos > 1:
            msg_final = msg_final_varios

        if msg_final:
            time.sleep(5)
            send_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            status, resp_js = chatguru_post(
                {
                    "action": "message_send",
                    "chat_number": numero,
                    "send_date": send_date,
                    "text": msg_final,
                },
                phone_id=chosen_phone,
            )
            resultados.append(
                {"tipo": "mensagem_final", "status": status, "resposta": resp_js}
            )
            if isinstance(resp_js, dict):
                if resp_js.get("result") == "success":
                    sucesso = True
                else:
                    desc = resp_js.get("description") or resp_js.get("error") or ""
                    if desc and not primeira_descricao_erro:
                        primeira_descricao_erro = desc

    except Exception as e:
        return jsonify(ok=False, error=f"Erro ao enviar via ChatGuru: {e}"), 500

    if not sucesso:
        msg_erro = primeira_descricao_erro or "Nenhuma das chamadas foi aceita pela API ChatGuru."
        return jsonify(ok=False, error=msg_erro, detalhes=resultados)

    return jsonify(ok=True, detalhes=resultados)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6060, debug=True)
