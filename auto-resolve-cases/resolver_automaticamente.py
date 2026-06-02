import os
import time
import requests
import logging
from dotenv import load_dotenv

load_dotenv()


# Configuração do logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# Variáveis de ambiente
USUARIO = os.getenv('USUARIO')
SENHA = os.getenv('SENHA')
INSTANCE = os.getenv('INSTANCE')


def buscar_chamados(query: str, table: str) -> dict:
    path = f"{INSTANCE}/api/now/table/{table}"
    params = {
        "sysparm_query": query,  # Consulta para filtrar os chamados
        "sysparm_limit": "1000",  # Limite de resultados
        "sysparm_fields": "sys_id,number"  # Campos que queremos retornar
    }
    try:
        response = requests.get(path, auth=(USUARIO, SENHA), params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar chamado: {e}")
        return {"result": []}

def resolver_automaticamente(chamados: dict, table: str) -> None:
    for chamado in chamados['result']:
        try:
            sys_id = chamado['sys_id']
            resolver_url = f"{INSTANCE}/api/now/table/{table}/{sys_id}"
            payload = {
                "state": "6",
                "close_code": "Closed/Resolved by Caller",
                "close_notes": "Chamado resolvido automaticamente pelo sistema."
            }
            resolver_response = requests.put(resolver_url, json=payload, auth=(USUARIO, SENHA))
            resolver_response.raise_for_status()
            logging.info(f"Chamado {chamado['number']} resolvido com sucesso.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao resolver chamado {chamado.get('number', chamado.get('sys_id', 'desconhecido'))}: {e}")

        
def main():
    while True:
        try:
            # Exemplo de consulta: buscar chamados abertos (state NOT IN 6,7,3) com a descrição "Chamado aberto automaticamente"
            chamados = buscar_chamados("short_description=Chamado aberto automaticamente^ORDERBYDESCcreated_on^stateNOT IN6,7,3", "sn_customerservice_case")  # Exemplo: buscar chamados abertos
            logging.info(f"Chamados encontrados: {len(chamados['result'])}")
            if chamados['result']:
                logging.info("Resolvendo chamados encontrados...")
                resolver_automaticamente(chamados, "sn_customerservice_case")
            else:
                logging.info("Nenhum chamado encontrado para resolver.")
            logging.info("Aguardando para buscar novamente...")
            time.sleep(60)  # Espera 1 minuto antes de buscar novamente
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao buscar chamados: {e}")
        except KeyboardInterrupt:
            logging.error("Processo interrompido pelo usuário.")
            break    
        
            
if __name__ == "__main__":
    main()