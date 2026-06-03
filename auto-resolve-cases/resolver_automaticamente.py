import os
import time
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).parent

logging.basicConfig(
    filename=BASE_DIR / "resolver.log",
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

USUARIO = os.getenv("USUARIO")
SENHA = os.getenv("SENHA")
INSTANCE = os.getenv("INSTANCE")

INTERVALO_SEGUNDOS = 60
MAX_FALHAS_CONSECUTIVAS = 5
INTERVALO_HEALTHCHECK = 180


def buscar_chamados(query: str, table: str) -> list:
    """Busca chamados na tabela informada com a query fornecida."""
    path = f"{INSTANCE}/api/now/table/{table}"
    params = {
        "sysparm_query": query,
        "sysparm_limit": "1000",
        "sysparm_fields": "sys_id,number"
    }
    response = requests.get(path, auth=(USUARIO, SENHA), params=params)
    response.raise_for_status()
    return response.json().get("result", [])


def resolver_chamado(chamado: dict, table: str) -> None:
    """Resolve um único chamado via PUT."""
    sys_id = chamado["sys_id"]
    numero = chamado.get("number", sys_id)
    resolver_url = f"{INSTANCE}/api/now/table/{table}/{sys_id}"
    payload = {
        "state": "6",
        "close_code": "Closed/Resolved by Caller",
        "close_notes": "Chamado resolvido automaticamente pelo sistema."
    }
    response = requests.put(resolver_url, json=payload, auth=(USUARIO, SENHA))
    response.raise_for_status()
    log.info("Chamado %s resolvido com sucesso.", numero)


def resolver_chamados(chamados: list, table: str) -> None:
    """Itera sobre a lista de chamados e resolve cada um, logando erros individualmente."""
    for chamado in chamados:
        numero = chamado.get("number", chamado.get("sys_id", "desconhecido"))
        try:
            resolver_chamado(chamado, table)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            log.error("Chamado %s — erro HTTP %s ao resolver: %s", numero, status, e)
        except requests.RequestException as e:
            log.error("Chamado %s — erro de conexão ao resolver: %s", numero, e)


def registrar_healthcheck(inicio: datetime, ciclos_ok: int, falhas_consecutivas: int, ultimo_erro: str | None) -> None:
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


def main():
    log.info("Iniciando automação de resolução de chamados.")
    falhas_consecutivas = 0
    ciclos_ok = 0
    ultimo_erro = None
    inicio = datetime.now()
    ultimo_healthcheck = time.monotonic()

    while True:
        agora = time.monotonic()
        if agora - ultimo_healthcheck >= INTERVALO_HEALTHCHECK:
            registrar_healthcheck(inicio, ciclos_ok, falhas_consecutivas, ultimo_erro)
            ultimo_healthcheck = agora

        try:
            query = (
                "short_description=Chamado aberto automaticamente"
                "^ORDERBYDESCcreated_on"
                "^stateNOT IN6,7,3"
            )
            chamados = buscar_chamados(query, "sn_customerservice_case")
            log.info("Chamados encontrados: %d", len(chamados))

            if chamados:
                log.info("Resolvendo chamados encontrados...")
                resolver_chamados(chamados, "sn_customerservice_case")
            else:
                log.info("Nenhum chamado encontrado para resolver.")

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
                "Erro HTTP %s ao buscar chamados: %s [falha consecutiva %d/%d]",
                status, e, falhas_consecutivas, MAX_FALHAS_CONSECUTIVAS
            )

        except requests.RequestException as e:
            falhas_consecutivas += 1
            ultimo_erro = str(e)[:120]
            log.error(
                "Erro de conexão ao buscar chamados: %s [falha consecutiva %d/%d]",
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