# Eventos Avulsos

Aplicação desktop em português para consolidar solicitações de Eventos Avulsos e indicar conflitos com atividades docentes de um Excel exportado da view. Ela lê apenas arquivos `xlsx` e `xlsm` diretamente nas pastas configuradas e nunca move, renomeia, exclui ou altera os arquivos de origem.

## Arquitetura

`GUI Tkinter` → `orchestrator` → descoberta, perfil/leitura, normalização, DW, conflitos e exportação. O núcleo não depende da interface, portanto também pode ser executado por linha de comando. A interface executa o trabalho em segundo plano e recebe progresso e logs por fila.

## Instalação no Windows

1. Instale Python 3.11+ e marque **Add Python to PATH**.
2. No PowerShell, dentro desta pasta, execute `py -3.11 -m venv .venv`, `.\.venv\Scripts\Activate.ps1` e `pip install -r requirements.txt`.
3. Copie `config.example.json` para `config.json`. Coloque o Excel exportado da view na raiz da automação com o nome `base_dw.xlsx`, ou selecione-o pela interface.
4. Execute `python main.py`.

Para criar o executável: `pyinstaller --noconfirm --windowed --name EventosAvulsos main.py`. Inclua `config.example.json` junto ao executável e crie `config.json` no mesmo diretório.

## Uso

1. Selecione o diretório que contém `1. LETIVA`, `2. NAO LETIVA` e, quando aplicável, as duas pastas históricas elegíveis.
2. Use **Validar arquivos**. O relatório informa pastas ausentes, arquivos ignorados e arquivos sem registros. Subpastas, inclusive `2025`, `2026` e `ajustes`, não são percorridas.
3. Escolha o perfil e use **Prévia do mapeamento** antes de executar. O perfil novo busca primeiro cabeçalhos conhecidos e só aceita as posições B, F, W e X quando o perfil explicitamente selecionado as configura. O perfil VBA é exclusivamente manual.
   Quando o arquivo possuir B e F, mas ainda não tiver W/X, a consolidação continuará e o registro será marcado como `Não verificado — horário de início ou término ausente ou inválido`.
4. Escolha o arquivo exportado da view e informe o período de cobertura confirmado. Sem cobertura confirmada, os eventos não são declarados sem conflito.
5. Clique **Executar**. Um novo arquivo é criado em `resultados`; a saída dentro de qualquer origem habilitada é bloqueada.

## Arquivo exportado da view

Exporte a view com as colunas `MATRICULA_ADP`, `DATA`, `HORARIO_INICIO HR Relogio`, `HORARIO_FIM HR Relogio`, `TIPO_ATIVIDADE` e `DISCIPLINA_ATIVIDADE_NOME`. Salve o arquivo na raiz como `base_dw.xlsx` ou escolha outro pelo botão **Selecionar arquivo**. O botão **Validar arquivo da view** confere a estrutura antes da execução.

## Perfis de template

Cada perfil em `config.json` possui aba(s) permitida(s), linha do cabeçalho, primeira linha de dados, aliases e colunas. Ajuste os aliases depois de confirmar os cabeçalhos reais, sobretudo no template não letivo. Quando nenhuma ou mais de uma aba corresponder ao perfil, o arquivo é registrado como pendência em vez de ser adivinhado.

O formato de múltiplas aulas no mesmo registro ainda é uma pendência de negócio. A versão atual não interpreta textos livres ou períodos como múltiplas ocorrências.

## Demonstração e testes

Com as dependências instaladas, execute `python exemplos/gerar_dados_ficticios.py` e escolha `exemplos/dados_ficticios` como entrada, `exemplos/dados_ficticios/dw_exportado.xlsx` como fonte DW, cobertura `01/10/2026` a `31/10/2026`. Execute os testes com `pytest`.

## Pendências objetivas

- Confirmação das colunas presentes no Excel exportado da view.
- Nomes reais das abas, cabeçalhos e linha de cabeçalho.
- Compatibilidade e perfil definitivo para solicitações não letivas.
- Regra e formato estruturado para várias aulas em um registro.
