# Projeto: resolver_automaticamente.py

Um projeto simples para automação de resolução de casos no ServiceNow.

## Descrição

Este repositório contém o script `resolver_automaticamente.py`, que automatiza o fechamento ou resolução de chamados de forma programática.

## Instalação

Clone o repositório
```bash
git clone https://github.com/Pedro-HSBorges/Automacoes-Service-Now.git
cd Automacoes-Service-Now/auto-resolve-cases
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

## Uso

Execute o script principal:

```bash
python resolver_automaticamente.py
```

## Estrutura

- `resolver_automaticamente.py`: script principal que processa e resolve casos automaticamente.

## Observações

Ajuste as configurações de conexão e autenticação conforme necessário para o seu ambiente ServiceNow antes de executar.
