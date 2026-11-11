# Eventos Avulsos

Aplicação desktop para consolidar solicitações de Eventos Avulsos e verificar conflitos de horário com a base local `base_dw.xlsx`, exportada da view. Não existe conexão com SQL Server, credenciais ou consultas de banco de dados.

Consulte [CHANGELOG.md](CHANGELOG.md) para o histórico de versões e alterações funcionais.

## Instalação no Windows

1. Instale Python 3.11+ e marque **Add Python to PATH**.
2. No PowerShell, dentro desta pasta, execute `py -3.11 -m venv .venv`, `.\.venv\Scripts\Activate.ps1` e `pip install -r requirements.txt`.
3. Copie `config.example.json` para `config.json` e ajuste as pastas de origem, se necessário.
4. Salve a exportação da view como `base_dw.xlsx` na raiz da automação, ou selecione outro arquivo pela interface.
5. Execute `python main.py`.

## Uso

1. Selecione o diretório que contém `1. LETIVA` e, se aplicável, a pasta histórica letiva configurada.
2. Escolha o perfil e use **Prévia do mapeamento** para confirmar a aba reconhecida.
3. Selecione a base exportada e clique em **Validar base**. Ela precisa ter as colunas `MATRICULA_ADP`, `DATA`, `HORARIO_INICIO HR Relogio`, `HORARIO_FIM HR Relogio`, `TIPO_ATIVIDADE` e `DISCIPLINA_ATIVIDADE_NOME`.
4. Informe a cobertura da base apenas se quiser restringir as datas aceitas. Deixe em branco para comparar todas as solicitações válidas.
5. Clique em **Executar**.

A aba **Letivas** traz o resultado por registro: `Conflito`, `Sem conflito` ou `Não verificado`. Os detalhes de cada conflito ficam na aba **Detalhamento de conflitos** quando houver ocorrências.

## Demonstração e testes

Execute `python exemplos/gerar_dados_ficticios.py` e escolha `exemplos/dados_ficticios` como entrada. Execute os testes com `pytest`.
