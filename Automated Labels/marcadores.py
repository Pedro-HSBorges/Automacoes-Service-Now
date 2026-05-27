import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

user: str = os.getenv("USUARIO")
password: str = os.getenv("SENHA")
instance: str = os.getenv("INSTANCE")
_lista = json.loads(os.getenv("MARCADORES")) # Pega a lista de marcadores no .env
marcadores = {m["group_id"]: m for m in _lista} # Transforma a lista em dicionário para consulta

def buscar_casos() -> requests.Response:
    """essa aqui faz a consulta pra buscar os casos, ela recebe o caminho da API e os parâmetros de consulta, e retorna a resposta da requisição"""
    path = "/api/now/table/sn_customerservice_case"
    params = {
        "sysparm_query": "stateNOT IN6,7^ORDERBYDESCsys_created_on", # Filtra os casos que não estão fechados ou cancelados
        "sysparm_fields": "number,sys_id,case"
    }
    response = requests.get(
        instance + path,
        params=params,
        auth=(user, password)
    )
    response.raise_for_status()
    return response

def buscar_chamado_atrelado(sys_id: str) -> requests.Response:
    """esse aqui procura pra ver se tem chamado atrelado, se não tiver ele só fala que não tem"""
    path = "/api/now/table/incident"
    params = {
        "sysparm_query": f"parent_incident={sys_id}",
        "sysparm_fields": "number,sys_id,assignment_group"
    }
    response = requests.get(
        instance + path,
        params=params,
        auth=(user, password)
    )
    response.raise_for_status()
    return response

def validar_grupos(assignment_group):
    """esse aqui valida o nome do grupo de atribuição, se tiver, se não tiver, ele retorna "Sem grupo de atribuição" """
    if not assignment_group:
        return "Sem grupo de atribuição"
    
    path = "/api/now/table/sys_user_group"
    params = {
        "sysparm_fields": "name",
        "sysparm_query": f"sys_id={assignment_group}"
    }
    response = requests.get(
        instance + path,
        params=params,
        auth=(user, password)
    )
    response.raise_for_status()

    resultado = response.json().get("result", [])
    if not resultado:
        return "Sem grupo de atribuição"
    
    return resultado[0].get("name", "Sem grupo de atribuição")

def validar_marcador(sys_id: str, assignment_group: str) -> bool:
    """essa aqui valida se o marcador já tá atrelado, se tiver, ele retorna True, se não tiver, ele retorna False"""
    path = "/api/now/table/label_entry"
    params = {
        "sysparm_fields": "sys_id,label",
        "sysparm_query": f"table_key={sys_id}"
    }
    response = requests.get(
        instance + path,
        params=params,
        auth=(user, password)
    )
    response.raise_for_status()
    resultado = response.json().get("result")
    if resultado and resultado[0].get("label", {}).get("value") == marcadores[assignment_group].get("sys_id"):
        return True
    return False

def atrelar_marcador(sys_id: str, label: str, case: str) -> None:
    """essa aqui atrela o marcador, ela recebe o sys_id do caso, o sys_id do marcador e o número do caso pra colocar no título do marcador"""
    path = "/api/now/table/label_entry"
    data = {
        "table_key": sys_id,
        "table": "sn_customerservice_case",
        "label": label,
        "title": "Caso - " + case
    }
    response = requests.post(
        instance + path,
        json=data,
        auth=(user, password)
    )
    response.raise_for_status()

def deletar_marcador(sys_id: str) -> None:
    """essa aqui deleta o marcador, ela recebe o sys_id do caso, busca os marcadores atrelados e deleta um por um"""
    path = "/api/now/table/label_entry"
    params = {
        "sysparm_query": f"table_key={sys_id}"
    }
    response = requests.get(
        instance + path,
        params=params,
        auth=(user, password)
    )
    response.raise_for_status()
    resultado = response.json().get("result", [])
    for entry in resultado:
        delete_response = requests.delete(
            instance + path + f"/{entry['sys_id']}",
            auth=(user, password)
        )
        delete_response.raise_for_status()

def main():
    while True:
        try:
            response: requests.Response = buscar_casos()
            casos: list = response.json().get("result", [])

            for caso in casos:
                print("Número:", caso.get("number"))

                chamado_atrelado_response: requests.Response = buscar_chamado_atrelado(caso.get("sys_id"))
                chamados_atrelados: list = chamado_atrelado_response.json().get("result", [])

                if chamados_atrelados:
                    for chamado in chamados_atrelados:
                        print("Chamado atrelado encontrado, número:", chamado.get("number"))
                        assignment_group_name = chamado.get("assignment_group")

                        if isinstance(assignment_group_name, dict):
                            assignment_group_name = assignment_group_name.get("value")
                        else:
                            assignment_group_name = None
                        
                        grupo = validar_grupos(assignment_group_name)
                        print("Grupo de atribuição do chamado:", grupo)
                        if grupo != "Sem grupo de atribuição":
                            validacao = validar_marcador(caso.get("sys_id"), assignment_group_name)
                            if validacao:
                                print("Marcador já atrelado.")
                            else:
                                print("Marcador não atrelado, atrelando agora...")
                                deletar_marcador(caso.get("sys_id"))
                                atrelar_marcador(caso.get("sys_id"), marcadores[assignment_group_name].get("sys_id"), caso.get("number"))
                                print("Marcador atrelado com sucesso.")
                        print("-" * 40)
                else:
                    print("Nenhum chamado atrelado encontrado.")
                    print("Atrelar marcador de aguardando atendimento.")
                    deletar_marcador(caso.get("sys_id"))
                    atrelar_marcador(caso.get("sys_id"), marcadores["N/A"].get("sys_id"), caso.get("number"))
                    print("-" * 40)
        except requests.RequestException as e:
            print("Erro ao buscar casos:", e)
        except KeyboardInterrupt:
            print("Processo interrompido pelo usuário.")
            break

if __name__ == "__main__":
    raise SystemExit(main())