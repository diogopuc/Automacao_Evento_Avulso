# Eventos Avulsos

Aplicação desktop em português para consolidar solicitações de Eventos Avulsos. Ela lê apenas arquivos `xlsx` e `xlsm` diretamente nas pastas configuradas, não percorre subpastas e nunca move, renomeia, exclui ou altera os arquivos de origem.

## Instalação no Windows

1. Instale Python 3.11+ e marque **Add Python to PATH**.
2. No PowerShell, dentro desta pasta, execute `py -3.11 -m venv .venv`, `.\.venv\Scripts\Activate.ps1` e `pip install -r requirements.txt`.
3. Copie `config.example.json` para `config.json` e ajuste as pastas de origem, se necessário.
4. Execute `python main.py`.

Para criar o executável: `pyinstaller --noconfirm --windowed --name EventosAvulsos main.py`.

## Uso

1. Selecione o diretório que contém `1. LETIVA`, `2. NAO LETIVA` e, quando aplicável, as pastas históricas habilitadas no `config.json`.
2. Use **Validar arquivos** para conferir as pastas encontradas.
3. Escolha o perfil e use **Prévia do mapeamento** para confirmar a aba reconhecida.
4. Clique **Executar**. Um novo arquivo é criado em `resultados`; uma saída dentro de qualquer pasta de origem habilitada é bloqueada.

O relatório contém as abas **Resumo**, **Letivas**, **Não Letivas**, **Pendências** e **Arquivos processados**.

## Perfis de template

Cada perfil em `config.json` define as abas, a linha de cabeçalho e os campos usados para reconhecer o template. Quando nenhuma ou mais de uma aba corresponder ao perfil, o arquivo é registrado como pendência em vez de ser adivinhado.

## Demonstração e testes

Com as dependências instaladas, execute `python exemplos/gerar_dados_ficticios.py` e escolha `exemplos/dados_ficticios` como entrada. Execute os testes com `pytest`.
