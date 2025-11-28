import json
import os
import requests

CONFIG_PATH = "config_chatguru.json"


def load_chatguru_config():
    """
    Lê o config_chatguru.json.
    Se não existir, dá erro amigável.
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Arquivo {CONFIG_PATH} não encontrado. "
            "Abra o sistema, configure e salve os parâmetros do ChatGuru primeiro."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def executar_dialogo(numero: str, dialog_id: str):
    """
    Faz um POST direto na API do ChatGuru só para testar o dialog_execute.
    """
    cfg = load_chatguru_config()

    endpoint = (cfg.get("api_endpoint") or "https://app3.zap.guru/api/v1").strip()
    key = (cfg.get("chatguru_key") or "").strip()
    account_id = (cfg.get("chatguru_account_id") or "").strip()
    # usa o phone_id_1 como padrão
    phone_id = (
        cfg.get("chatguru_phone_id_1")
        or cfg.get("chatguru_phone_id")
        or ""
    ).strip()

    if not (key and account_id and phone_id):
        print("ERRO: key, account_id ou phone_id não configurados no config_chatguru.json.")
        return

    # só dígitos no número
    numero = "".join(ch for ch in numero if ch.isdigit())

    data = {
        "action": "dialog_execute",
        "dialog_id": dialog_id,
        "key": key,
        "account_id": account_id,
        "phone_id": phone_id,
        "chat_number": numero,
    }

    print("=== Enviando requisição para o ChatGuru ===")
    print("URL:", endpoint)
    print("Payload:", data)
    print("===========================================")

    resp = requests.post(endpoint, data=data, timeout=30)

    print("\n=== RESPOSTA ===")
    print("Status HTTP:", resp.status_code)
    try:
        print("JSON:", resp.json())
    except Exception:
        print("Texto bruto:", resp.text)
    print("================\n")


if __name__ == "__main__":
    numero_teste = "553399620430"
    print("Número fixo para teste:", numero_teste)
    dialog_id = input("Digite o dialog_id para testar: ").strip()

    if not dialog_id:
        print("Dialog_id não informado. Saindo.")
    else:
        executar_dialogo(numero_teste, dialog_id)
