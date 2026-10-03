# Auditoria do tracker, 03/10/2026

A divergência dos prints vinha de contas diferentes: Hour lia registros locais; Day e modelos usavam coletores com outras regras e totais remotos. A publicação anterior também foi validada só pelos arquivos copiados, sem provar qual componente o shell tinha carregado. Essa validação foi insuficiente.

A versão 1.8 concentra a conta em `UsageMath.js`. Day é o total do mesmo snapshot usado em Hour; modelos usam esse snapshot. Week e Month significam os últimos 7 e 30 dias do calendário, incluindo hoje. Total significa todo o histórico disponível, sem prometer recuperar registros apagados. `Main.qml` cuida de descoberta, metadados, cotas e sincronização; a antiga soma de All foi removida.

## Achados e correções

| Área | Falha | Correção |
| --- | --- | --- |
| Hour, Day, modelos | Períodos e fontes diferentes; remoto desaparecia de Hour | Conta única, período no título e linhas explícitas sem horário |
| Week, Month, Total | Regras separadas, dados futuros e histórico parcial apresentados como completo | Resumo do índice local com janela explícita; faltas de divisão diária aparecem separadas |
| Codex | Coletores somavam atualizações repetidas de um acumulado | Parser diário reutiliza o parser do índice, com deltas; cache invalidado |
| Claude | Primeira revisão de streaming mantida; consumo final perdido | Última revisão por ID; consumo de hoje zerado quando ausente, inclusive pelo enriquecedor completo |
| Arquivos removidos | Consumo permanecia no índice | Eventos e cursores removidos com a fonte; falha temporária de leitura preserva registros e informa leitura parcial |
| Hermes | Acumulado de sessão inteiro jogado na última hora/dia | Intervalo observado considerado; cruzamento de limite excluído do período com aviso, mantido em Total sem inventar data |
| Pi e OMP | Uso ausente do índice de horas | Registros adicionados ao harness correspondente |
| OpenCode | Mesmo uso refletido nos coletores Codex/Grok e no OpenCode | No painel, cada fonte local usa seus próprios registros do índice |
| 9Router | Gráfico e stats lidos em momentos diferentes; posições assumidas como datas | Stats do período como total, rótulos reais como datas, detalhe divergente sinalizado |
| Cache 9Router | Cache de outra data ou do futuro aceito; escrita concorrente | Validade por idade e dia; escrita atômica |
| Sincronização | Máximo de cada modelo misturava réplicas de uma conta; histórico descartado | Réplica inteira mais recente, histórico e totais de período preservados; dispositivos continuam aditivos |
| Descoberta | Fonte com tokens, sem prompts/sessões, desaparecia | Tokens e modelos também admitem a fonte; FileView pré-carregado, arrays inválidos rejeitados |
| Modelos ocultos | Limite visual descartava parte do total | Linha Outros conserva a soma; detalhe sem modelo permanece explícito |
| Radar | Percentual ausente virava 0%, como se a cota estivesse livre | Ausentes e não finitos descartados; ordenação exercitada nas funções reais |
| Projetos e Tempo real | Escopo local pouco claro, sessões sem divisão temporal incluídas, detalhes persistiam após trocar filtros | Escopo local indicado, exclusão de acumulados informada, detalhes limpos ao trocar filtros |
| Atualização | Exclusões não chegavam ao stock; `all` não executava os coletores; chamadas podiam ultrapassar o watchdog | Exclusões encaminhadas, `all` normalizado, bloqueio de concorrência e orçamento total de 240 s |
| Instalação | Mesmo URL podia conservar componentes compilados antigos | Gerações imutáveis, manifesto publicado por último e diagnóstico da versão carregada |
| Desempenho | WAL procurado em cada JSONL; consulta SQLite individual por arquivo | WAL consultado apenas em bancos, metadados do índice carregados em lote |

## Evidência

Quatro regressões foram reproduzidas antes das correções: Codex 220 contra 110 tokens, Claude streaming 100 contra 110, Today antigo de 500 e registro removido ainda presente. Os novos testes exercitam os parsers, sincronização e funções QML reais, além da suíte anterior. Alguns testes antigos são contratos reimplementados em Python; eles não são tratados como prova de que a UI funciona.

Validação final: 91 testes Python, 16 testes Node, 4.000 snapshots gerados de contagem, parser QML e sintaxe Bash. O teste de integração carrega o QML real, FileView, processos e delegates numa bancada. Só o adaptador de janela Wayland é substituído, pois a bancada é X11. Nove telas foram conferidas com dados controlados e nove com dados reais, sem navegar ou manipular o desktop humano.

Na captura real inicial desta auditoria, All foi 2.896.000.252 em Day e Hour. Opus foi 1.853.216.232 nas duas telas. Claude local foi 387.996.800 e 9Router foi 1.644.395.470. Em todas as nove telas: total = soma das linhas = soma dos modelos, incluindo Outros. Esses números são uma captura com horário; continuam mudando com uso novo.

A mediana inicial do índice aquecido foi 187,9 ms. Após retirar as leituras desnecessárias, a medição final deu 159,7 ms (cerca de 15% menos). Isso mede o índice local, não latência das APIs. O modo de resumo evita carregar prévias de mensagens para gráficos; Tempo real continua com atualização a cada 5 s, e os gráficos a cada 30 s enquanto abertos.

O inventário de funções está em [audit-function-inventory.json](audit-function-inventory.json). Ele delimita os módulos inspecionados; não representa cobertura de 100% dos ramos ou prova de todas as respostas possíveis dos serviços.

## Limites da informação

- O dia local e Today dos gateways podem usar calendários diferentes. Sem timestamps não há conversão confiável para horas locais. A UI identifica essa diferença.
- Hermes fornece acumulados de sessão. Não dá pra reconstruir quanto de uma sessão de vários dias aconteceu em cada dia sem telemetria adicional. Períodos limitados mostram o que pôde ser atribuído e avisam a exclusão.
- All soma fontes disponíveis. Proxies locais conhecidos são excluídos; um total remoto sem IDs de requisição comuns não permite provar unicidade entre gateway e harness. O teste de conservação valida a conta, não cria esses IDs ausentes.
- O fallback de Railway pelo Jcode cobre só essas sessões, não todos os clientes Railway. A origem continua indicada pelo coletor.
- APIs de cota, disponibilidade e login dependem do serviço. Foram inspecionadas as normalizações, falhas, caches e fixtures disponíveis; não foram feitas requisições de geração para testar consumo nem alterações nas contas.

## Publicação e recuperação

`python3 bin/deploy.py` copia a geração completa para `.runtime/<hash>/` e troca o manifesto atomicamente. `quickshell ipc -p /usr/share/omarchy/shell call lol.agents diagnostics` confirma a versão realmente carregada. `ready: false` com painel fechado indica que a leitura do período ainda não ocorreu; a UI mostra leitura pendente ao abrir.

A geração anterior e o manifesto anterior permitem voltar à versão antiga sem reiniciar o desktop. Depois de uma atualização convencional do plugin, use o instalador da cópia local pra garantir URLs novos no shell que já está aberto.
