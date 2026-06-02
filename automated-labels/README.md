# Automated Labels

Automação para gerenciamento de marcadores (labels) no ServiceNow via API.

## Funcionalidades

- Adicionar labels em incidentes e casos
- Remover labels existentes
- Evitar labels duplicadas
- Centralização da lógica de aplicação de marcadores

## Tecnologias

- Python
- Requests
- ServiceNow REST API
- dotenv

## Instalação

Clone o repositório
```bash
git clone https://github.com/Pedro-HSBorges/Automacoes-Service-Now.git
cd Automacoes-Service-Now/automated-labels
```
Baixe os requisitos:
```bash
pip install -r requirements.txt
```

## Configuração

Crie um arquivo `.env`:

- Linux / macOS / Git Bash / PowerShell:
```bash
cp .env.example .env
```

- Windows Command Prompt (CMD):
```bash
copy .env.example .env
```

Alterar a config caso necessário de acordo com os parâmetros do ambiente:

```json
{
    "marcadores": [
        {
            "group_id":"287ebd7da9fe198100f92cc8d1d2154e",
            "sys_id":"6b16434d83c14710e0d8fb96feaad37c",
            "name":"Network"
        }
    ],
    "intervalo_segundos":60
}
```

## Uso

```bash
python marcadores.py
```