# Eventos Avulsos

Aplicação desktop para consolidar solicitações de Eventos Avulsos e verificar conflitos de horário com a base local `base_dw.xlsx`, exportada da view. Não existe conexão com SQL Server, credenciais ou consultas de banco de dados.

Consulte [CHANGELOG.md](CHANGELOG.md) para o histórico de versões e alterações funcionais.

## Instalação no Windows

### Executável para usuários

Copie `EventosAvulsos.exe` para uma pasta em que seu usuário possa gravar arquivos e abra-o com dois cliques. Python e as bibliotecas já estão incluídos; não é necessário instalá-los, baixá-los ou usar uma conta administradora. Coloque a pasta `1. LETIVA` junto ao executável e a base em `dados/base_dw.xlsx`, ou selecione os caminhos na tela. A configuração será criada em `config/config.json` e os relatórios em `resultados`. Não compartilhe o `config.json` pessoal, que pode conter caminhos específicos da sua máquina.

### Execução pelo código-fonte

1. Instale Python 3.11+ e marque **Add Python to PATH**.
2. No PowerShell, na pasta `desenvolvimento`, crie e ative um ambiente virtual e execute `pip install -r requirements.txt`.
3. Ajuste `config/config.json`, se necessário, usando `config/config.example.json` como referência.
4. Salve a exportação da view como `dados/base_dw.xlsx`, ou selecione outro arquivo pela interface.
5. Na pasta `desenvolvimento`, execute `python main.py`.

Para gerar novamente o executável em Windows, execute na pasta `desenvolvimento`: `python -m PyInstaller --noconfirm --onefile --windowed --name EventosAvulsos --add-data "../config/config.example.json;." main.py`. O arquivo será criado em `desenvolvimento/dist` e deverá ser copiado para a raiz do projeto.

## Uso

1. Selecione o diretório que contém `1. LETIVA` e, se aplicável, a pasta histórica letiva configurada.
2. Escolha o perfil e use **Prévia do mapeamento** para confirmar a aba reconhecida.
3. Selecione a base exportada e clique em **Validar base**. Ela precisa ter as colunas `MATRICULA_ADP`, `DATA`, `HORARIO_INICIO HR Relogio`, `HORARIO_FIM HR Relogio`, `TIPO_ATIVIDADE` e `DISCIPLINA_ATIVIDADE_NOME`.
4. Informe a cobertura da base apenas se quiser restringir as datas aceitas. Deixe em branco para comparar todas as solicitações válidas.
5. Clique em **Executar**.

O relatório atual é salvo em `resultados/irregularidades_EV.xlsx`. Antes de cada substituição, a versão anterior é copiada para `resultados/versionamento`.

A aba **Letivas** traz o resultado por registro: `Conflito`, `Sem conflito` ou `Não verificado`. Os detalhes de cada conflito ficam na aba **Detalhamento de conflitos** quando houver ocorrências.

## Descansos entre jornadas

Além dos conflitos com a base, o relatório calcula duas validações para cada solicitação válida, usando os horários da base e dos Eventos Avulsos do mesmo professor:

- **Intrajornada:** jornada de 5h a menos de 7h requer pausa mínima de 15 minutos; jornada de 7h até 8h requer pausa mínima de 1h; jornada acima de 8h é marcada como não conforme.
- **Interjornada:** são exigidas 11h entre o término da última atividade de um dia e o início da primeira atividade do dia seguinte.

Os resultados ficam nas colunas **Validação intrajornada** e **Validação interjornada** da aba **Letivas**.

## Demonstração e testes

Execute `python exemplos/gerar_dados_ficticios.py` e escolha `exemplos/dados_ficticios` como entrada. Execute os testes com `pytest`.
