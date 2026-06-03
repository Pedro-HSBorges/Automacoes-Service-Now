import requests
import os
import json
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).parent

logging.basicConfig(
    filename=BASE_DIR / "marcadores.log",
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# Carrega configuração de marcadores e intervalo do arquivo JSON
with open(BASE_DIR / "config.json") as f:
    config = json.load(f)

user: str = os.getenv("USUARIO")
password: str = os.getenv("SENHA")
instance: str = os.getenv("INSTANCE")
marcadores = {m["group_id"]: m for m in config["marcadores"]}

INTERVALO_SEGUNDOS = config["intervalo_segundos"]
MAX_FALHAS_CONSECUTIVAS = config.get("max_falhas_consecutivas", 5)
INTERVALO_HEALTHCHECK = config.get("intervalo_healthcheck_segundos", 180)


def buscar_casos() -> requests.Response:
    """Busca casos abertos (não fechados nem cancelados), ordenados por data de criação."""
    path = "/api/now/table/sn_customerservice_case"
    params = {
        "sysparm_query": "stateNOT IN6,7^ORDERBYDESCsys_created_on",
        "sysparm_fields": "number,sys_id,case"
    }
    response = requests.get(instance + path, params=params, auth=(user, password))
    response.raise_for_status()
    return response


def buscar_chamado_atrelado(sys_id: str) -> requests.Response:
    """Busca incidentes atrelados ao caso pelo sys_id."""
    path = "/api/now/table/incident"
    params = {
        "sysparm_query": f"parent_incident={sys_id}",
        "sysparm_fields": "number,sys_id,assignment_group"
    }
    response = requests.get(instance + path, params=params, auth=(user, password))
    response.raise_for_status()
    return response


def validar_grupos(assignment_group: str) -> str:
    """Valida o grupo de atribuição do chamado e retorna o nome do grupo caso esteja cadastrado nos marcadores."""
    if not assignment_group:
        return "Sem grupo de atribuição"
    return marcadores.get(assignment_group, {}).get("name", "Sem grupo de atribuição")


def buscar_marcadores_atrelados(sys_id: str) -> list:
    """Retorna todos os marcadores atrelados ao caso."""
    path = "/api/now/table/label_entry"
    params = {
        "sysparm_fields": "sys_id,label",
        "sysparm_query": f"table_key={sys_id}"
    }
    response = requests.get(instance + path, params=params, auth=(user, password))
    response.raise_for_status()
    return response.json().get("result", [])


def marcador_esta_correto(atrelados: list, sys_id_esperado: str) -> bool:
    """Retorna True somente se há exatamente um marcador atrelado e é o correto.

    Se houver múltiplos marcadores (mesmo que um deles seja o correto),
    retorna False para forçar limpeza e recriação.
    """
    if len(atrelados) != 1:
        return False
    return atrelados[0].get("label", {}).get("value") == sys_id_esperado


def deletar_marcadores(atrelados: list) -> None:
    """Remove todos os marcadores da lista fornecida."""
    base_path = "/api/now/table/label_entry"
    for entry in atrelados:
        response = requests.delete(
            instance + base_path + f"/{entry['sys_id']}",
            auth=(user, password)
        )
        response.raise_for_status()


def atrelar_marcador(sys_id: str, label: str, case: str) -> None:
    """Cria uma entrada de marcador para o caso."""
    path = "/api/now/table/label_entry"
    data = {
        "table_key": sys_id,
        "table": "sn_customerservice_case",
        "label": label,
        "title": "Caso - " + case
    }
    response = requests.post(instance + path, json=data, auth=(user, password))
    response.raise_for_status()


def aplicar_marcador(sys_id: str, numero: str, sys_id_marcador: str) -> None:
    """Garante que o caso tenha exatamente o marcador correto, sem extras."""
    atrelados = buscar_marcadores_atrelados(sys_id)

    if marcador_esta_correto(atrelados, sys_id_marcador):
        log.info("Caso %s — marcador já está correto, nada a fazer.", numero)
        return

    if atrelados:
        log.info("Caso %s — removendo %d marcador(es) incorreto(s)/extra(s).", numero, len(atrelados))
        deletar_marcadores(atrelados)

    atrelar_marcador(sys_id, sys_id_marcador, numero)
    log.info("Caso %s — marcador aplicado com sucesso.", numero)


def healthcheck(inicio: datetime, ciclos_ok: int, falhas_consecutivas: int, ultimo_erro: str | None) -> None:
    """Registra um resumo periódico do estado da automação no log."""
    uptime = datetime.now() - inicio
    horas, resto = divmod(int(uptime.total_seconds()), 3600)
    minutos, segundos = divmod(resto, 60)
    status = "OK" if falhas_consecutivas == 0 else "DEGRADADO"
    log.info(
        "[HEALTHCHECK] Status: %s | Uptime: %dh%02dm%02ds | Ciclos bem-sucedidos: %d | "
        "Falhas consecutivas: %d/%d | Último erro: %s",
        status, horas, minutos, segundos,
        ciclos_ok, falhas_consecutivas, MAX_FALHAS_CONSECUTIVAS,
        ultimo_erro or "nenhum"
    )


def processar_caso(caso: dict) -> None:
    """Processa um único caso: valida chamados atrelados e aplica o marcador correto."""
    numero = caso.get("number")
    sys_id = caso.get("sys_id")
    log.info("Processando caso: %s", numero)

    try:
        chamados_atrelados = buscar_chamado_atrelado(sys_id).json().get("result", [])
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "N/A"
        log.error("Caso %s — erro HTTP %s ao buscar chamados atrelados: %s", numero, status, e)
        return
    except requests.RequestException as e:
        log.error("Caso %s — erro de conexão ao buscar chamados atrelados: %s", numero, e)
        return

    if chamados_atrelados:
        for chamado in chamados_atrelados:
            log.info("Caso %s — chamado atrelado encontrado: %s", numero, chamado.get("number"))

            assignment_group_raw = chamado.get("assignment_group")
            assignment_group_id = (
                assignment_group_raw.get("value")
                if isinstance(assignment_group_raw, dict)
                else None
            )

            try:
                grupo = validar_grupos(assignment_group_id)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else "N/A"
                log.error("Caso %s — erro HTTP %s ao validar grupo: %s", numero, status, e)
                continue
            except requests.RequestException as e:
                log.error("Caso %s — erro de conexão ao validar grupo: %s", numero, e)
                continue

            log.info("Caso %s — grupo de atribuição: %s", numero, grupo)

            if grupo == "Sem grupo de atribuição":
                continue

            if assignment_group_id not in marcadores:
                log.warning(
                    "Caso %s — grupo '%s' não encontrado nos marcadores configurados. "
                    "Adicione-o no .env.",
                    numero, grupo
                )
                continue

            try:
                sys_id_marcador = marcadores[assignment_group_id].get("sys_id")
                aplicar_marcador(sys_id, numero, sys_id_marcador)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else "N/A"
                log.error("Caso %s — erro HTTP %s ao aplicar marcador: %s", numero, status, e)
            except requests.RequestException as e:
                log.error("Caso %s — erro de conexão ao aplicar marcador: %s", numero, e)

    else:
        log.info("Caso %s — sem chamado atrelado, aplicando marcador de aguardando.", numero)
        try:
            sys_id_marcador = marcadores["N/A"].get("sys_id")
            aplicar_marcador(sys_id, numero, sys_id_marcador)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            log.error("Caso %s — erro HTTP %s ao aplicar marcador de aguardando: %s", numero, status, e)
        except requests.RequestException as e:
            log.error("Caso %s — erro de conexão ao aplicar marcador de aguardando: %s", numero, e)

    log.info("-" * 40)


def main():
    log.info("Iniciando automação de marcadores.")
    falhas_consecutivas = 0
    ciclos_ok = 0
    ultimo_erro = None
    inicio = datetime.now()
    last_healthcheck = time.monotonic()

    while True:
        now = time.monotonic()
        if now - last_healthcheck >= INTERVALO_HEALTHCHECK:
            healthcheck(inicio, ciclos_ok, falhas_consecutivas, ultimo_erro)
            last_healthcheck = now

        try:
            casos = buscar_casos().json().get("result", [])
            log.info("Total de casos encontrados: %d", len(casos))
            for caso in casos:
                processar_caso(caso)
            falhas_consecutivas = 0
            ciclos_ok += 1
            ultimo_erro = None

        except KeyboardInterrupt:
            log.info("Processo interrompido pelo usuário.")
            break

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            falhas_consecutivas += 1
            ultimo_erro = f"HTTP {status}"
            log.error(
                "Erro HTTP %s ao buscar casos: %s [falha consecutiva %d/%d]",
                status, e, falhas_consecutivas, MAX_FALHAS_CONSECUTIVAS
            )

        except requests.RequestException as e:
            falhas_consecutivas += 1
            ultimo_erro = str(e)[:120]
            log.error(
                "Erro de conexão ao buscar casos: %s [falha consecutiva %d/%d]",
                e, falhas_consecutivas, MAX_FALHAS_CONSECUTIVAS
            )

        if falhas_consecutivas >= MAX_FALHAS_CONSECUTIVAS:
            log.critical(
                "Limite de %d falhas consecutivas atingido. Encerrando processo para reinício supervisionado.",
                MAX_FALHAS_CONSECUTIVAS
            )
            raise SystemExit(1)

        intervalo = INTERVALO_SEGUNDOS * (2 ** falhas_consecutivas) if falhas_consecutivas else INTERVALO_SEGUNDOS
        log.info("Ciclo concluído. Próxima execução em %ds.", intervalo)
        time.sleep(intervalo)


if __name__ == "__main__":
    main()