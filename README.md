# Alerta Perda 🥦🥩

Sistema de monitoramento preditivo de validades e prevenção de perdas no varejo alimentar (Hortifrúti e Carnes).

## Funcionalidades
- Painel de controle de shelf-life e alertas dinâmicos de validade.
- Registro de baixas e quebras com histórico auditável.
- Monitoramento e inspeção preventiva de temperatura dos balcões refrigerados.
- Gestão de equipe e fiscais de prevenção.
- API REST para integração com sistemas de PDV (`/api/produtos/alertas`).
- Integração meteorológica com Open-Meteo (`/api/clima`) para apoiar a rotina operacional.
- Login com perfis de administrador, gerente e operador.
- Saída por venda e remanejamento entre locais, preservando o histórico de movimentações.
- Indicadores consolidados de perdas por categoria e motivo.
- Recursos de acessibilidade: atalho para conteúdo principal, foco visível, mensagens anunciáveis e rótulos associados aos campos.

## Como Executar

1. Crie e ative o ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

2. Instale as dependências:
    ```powershell
    pip install -r requirements.txt

3. Inicie o servidor:
    ```powershell
    python run_local.py

Acesse em: http://127.0.0.1:5000

## Primeiro acesso local

Ao iniciar uma base local pela primeira vez, o sistema cria o usuário de demonstração abaixo. Altere a senha por variável de ambiente antes de qualquer publicação real.

```text
Matrícula: ADMIN-001
Senha local: admin123
```

Perfis: `administrador` gerencia usuários e todas as configurações; `gerente` registra entradas e consulta indicadores; `operador` registra inspeções, baixas e movimentações.

## Verificação

```powershell
.\.venv311\Scripts\python.exe -m unittest discover -s tests -v
```

## Configuração do clima

Por padrão, a integração consulta Pitangueiras-SP. Para configurar a localização do supermercado, defina as variáveis de ambiente abaixo antes de iniciar a aplicação:

```text
WEATHER_LOCATION=Nome da cidade, UF
WEATHER_LATITUDE=-21.0094
WEATHER_LONGITUDE=-48.2217
```
