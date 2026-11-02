# Publicação no Streamlit Community Cloud

## Finalidade

`streamlit_app.py` é uma versão pública de demonstração do Alerta Perda. Ela mostra o painel de validade, clima, perdas, inspeções e indicadores com dados fictícios.

## Limite importante

O armazenamento local do Streamlit Community Cloud é temporário. Por esse motivo, esta versão não recebe cadastros nem altera estoque. O sistema operacional completo continua sendo a aplicação Flask executada localmente. Ao reiniciar o ambiente em nuvem, os dados de demonstração podem ser recriados.

## Passos de publicação

1. Acessar [Streamlit Community Cloud](https://share.streamlit.io/) e entrar com a conta do GitHub que possui acesso ao repositório.
2. Escolher **Create app** e selecionar `isaacspim/alerta-perda`.
3. Selecionar a branch `main`.
4. Informar `streamlit_app.py` como arquivo de entrada.
5. Escolher um endereço público, por exemplo `alerta-perda-pi`.
6. Clicar em **Deploy**.

## Atualizações

Após a publicação, todo `git push` na branch configurada atualiza o app em nuvem automaticamente.
