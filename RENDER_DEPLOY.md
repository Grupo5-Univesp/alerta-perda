# Publicação do Alerta Perda no Render

Este guia publica a aplicação Flask original. Não use o Streamlit para esta
etapa.

## Antes de começar

- O repositório que deve ser conectado é Leme-BI/alerta-perda.
- O arquivo render.yaml já cria o serviço Flask e o banco PostgreSQL.
- A senha inicial do administrador será pedida pelo Render. Escolha uma senha
  forte e guarde-a. A matrícula inicial é ADMIN-001.
- No primeiro deploy, o sistema cria automaticamente um catálogo inicial com
  tomate, iogurte, leite, queijo e ovos, cada qual com lote e validade.

## Publicação

1. Acesse dashboard.render.com e entre com sua conta GitHub.
2. Clique em New + e depois em Blueprint.
3. Conecte o repositório Leme-BI/alerta-perda e clique em Connect.
4. O Render encontrará o arquivo render.yaml. Confirme a criação do serviço
   alerta-perda e do banco alerta-perda-db.
5. Quando aparecer a variável DEFAULT_ADMIN_PASSWORD, informe a senha inicial
   do administrador. Não use admin123.
6. Clique em Apply e aguarde a conclusão do deploy.
7. Abra a URL fornecida pelo Render, no formato
   https://alerta-perda.onrender.com.
8. Entre usando ADMIN-001 e a senha definida no passo 5.

## O que o Render configura

- gunicorn app:app executa o Flask em modo de produção.
- DATABASE_URL recebe a conexão privada do PostgreSQL automaticamente.
- APP_SECRET_KEY é gerada pelo Render e não fica no GitHub.
- A integração climática começa configurada para Pitangueiras, SP.

## Atualizações

Cada envio ao branch main inicia uma nova publicação no Render. Para
acompanhar, abra o serviço no painel do Render e consulte a guia Events.

## Limite do plano gratuito

O plano gratuito é adequado para apresentação e testes: o serviço pode entrar
em repouso após inatividade. O banco PostgreSQL gratuito expira após 30 dias.
Para manter os dados permanentemente, altere o banco para um plano pago no
painel do Render antes do vencimento.
