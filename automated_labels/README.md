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

```bash
git clone https://github.com/Pedro-HSBorges/Automacoes-Service-Now.git
cd Automacoes-Service-Now/automated_labels
pip install -r requirements.txt
```

## Configuração

Crie um arquivo `.env`:

```env
INSTANCE=
USUARIO=
SENHA=
MARCADORES(EXEMPLO)=[{"Nome": "Network", "sys_id": "6b16434d83c14710e0d8fb96feaad37c", "group_id": "287ebd7da9fe198100f92cc8d1d2154e"},{"Nome": "Service Desk", "sys_id": "76068f0d83c14710e0d8fb96feaad3d4", "group_id": "d625dccec0a8016700a222a0f7900d06"}]
```

## Uso

```bash
python main.py
```