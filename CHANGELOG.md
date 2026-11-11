# Histórico de versões

Este arquivo concentra as alterações funcionais do projeto. Use versionamento semântico simplificado no padrão `v1.x.x`:

- incremente o segundo número para novas funcionalidades compatíveis;
- incremente o terceiro número para correções e ajustes sem mudança de escopo;
- registre a versão mais recente no topo, com uma frase clara sobre o impacto da alteração.

## v1.6.0 - 2026-11-11

### Alterado

- Removido todo o fluxo de solicitações não letivas.
- A configuração aceita somente as pastas `1. LETIVA` e, quando habilitada, `3. LETIVA - Anterior_Maio.25`.
- O relatório passou a gerar somente a aba `Letivas`; a aba de não letivas e seus totais foram removidos.
- Simplificados o modelo de dados, a leitura dos arquivos, o resumo, os exemplos, os testes e a documentação para considerar apenas solicitações letivas.

## v1.5.0 - 2026-11-11

### Alterado

- Restaurada a verificação de conflito de horários contra o arquivo local `base_dw.xlsx`.
- Mantida a remoção de conexões diretas com SQL Server, credenciais, consultas e dependências de banco de dados.
- Adicionada validação estrutural da base da view pela interface e pela linha de comando.
- A cobertura da base passou a ser opcional; quando omitida, solicitações válidas são comparadas normalmente.

### Corrigido

- O progresso da leitura da base mostra a quantidade processada quando o arquivo não informa o total de linhas.

## v1.4.0 - 2026-10-28

### Alterado

- Removidas do consolidado as colunas técnicas de rastreabilidade solicitadas para uso interno.
- Criada a aba opcional `Detalhamento de conflitos` para apresentar cada sobreposição encontrada.

### Corrigido

- Eliminados filtros duplicados das abas de dados para evitar o aviso de reparo ao abrir o relatório no Excel.

## v1.3.0 - 2026-10-28

### Adicionado

- Exibição de etapas, registro em tempo real, tempo decorrido e cancelamento na interface gráfica.
- Prévia do mapeamento dos templates antes da execução.

### Alterado

- Permitida a consolidação de templates antigos sem horários, com marcação de `Não verificado` quando a comparação não puder ser executada.

## v1.2.0 - 2026-10-28

### Alterado

- Substituída a dependência de consulta direta ao DW pela leitura de uma exportação local da view em Excel.
- Implementada leitura progressiva da base, filtrando apenas matrículas e datas necessárias para a comparação.

## v1.1.0 - 2026-10-28

### Adicionado

- Perfis configuráveis para reconhecimento de abas e colunas de templates novos e legados.
- Validação de arquivos de origem, descoberta não recursiva e registro de pendências por arquivo.
- Relatório consolidado com resumo, solicitações, pendências e arquivos processados.

## v1.0.0 - 2026-10-28

### Adicionado

- Aplicação desktop para consolidar solicitações de Evento Avulso.
- Leitura de arquivos Excel e geração de relatório em `resultados`.
- Verificação de sobreposição de horários por matrícula e data.
