import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

user: str = os.getenv("USUARIO")
password: str = os.getenv("SENHA")
instance: str = os.getenv("INSTANCE")
_lista = json.loads(os.getenv("MARCADORES")) #Pega a lista de marcadores no .env
marcadores = {m["group_id"]: m for m in _lista} #Transforma a lista em dicionário para consulta

def buscar_incidentes(path: str, params: dict) -> requests.Response:
    """essa aqui faz a consulta pra buscar os incidentes, ela recebe o caminho da API e os parâmetros de consulta, e retorna a resposta da requisição"""
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
    """mano, esse aqui valida o nome do grupo de atribuição, se tiver, se não tiver, ele retorna "Sem grupo de atribuição" """
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

    path = "/api/now/table/label_entry"
    params = {
        "sysparm_fields": "sys_id",
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

def atrelar_marcador(sys_id: str, label: str, number: str) -> None:
    path = "/api/now/table/label_entry"
    data = {
        "table_key": sys_id,
        "table": "incident",
        "label": label,
        "title": "Incident + " + number
    }
    response = requests.post(
        instance + path,
        json=data,
        auth=(user, password)
    )
    response.raise_for_status()

def deletar_marcador(sys_id: str) -> None:
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
    params: dict = {
        "sysparm_query": "ORDERBYDESCsys_created_on",
        "sysparm_fields": "number,sys_id,assignment_group"
    }

    while True:
        try:
            response: requests.Response = buscar_incidentes("/api/now/table/incident", params)
            incidentes: list = response.json().get("result", [])

            for incidente in incidentes:
                print("Número:", incidente.get("number"))

                chamado_atrelado_response: requests.Response = buscar_chamado_atrelado(incidente.get("sys_id"))
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
                            validacao = validar_marcador(chamado.get("sys_id"), assignment_group_name)
                            if validacao:
                                print("Marcador já atrelado.")
                            else:
                                print("Marcador não atrelado, atrelando agora...")
                                deletar_marcador(chamado.get("sys_id"))
                                atrelar_marcador(chamado.get("sys_id"), marcadores[assignment_group_name].get("sys_id"), incidente.get("number"))
                                print("Marcador atrelado com sucesso.")
                        print("-" * 40)
                else:
                    print("Nenhum chamado atrelado encontrado.")
                    print("Atrelar marcador de aguardando atendimento.")
                    print("-" * 40)
        except requests.RequestException as e:
            print("Erro ao buscar incidentes:", e)
        except KeyboardInterrupt:
            print("Processo interrompido pelo usuário.")
            break

if __name__ == "__main__":
    raise SystemExit(main())