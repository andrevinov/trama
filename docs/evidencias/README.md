# Evidências e experimentos datados

- [19/11/2026 — Foco da conversa no conselho](2026-11-19-foco-conversa/relatorio.md): reprodução do cumprimento de Tristan, medição real e falhas preservadas, incluindo estado ativo redundante.

[Visão geral](../../README.md) · [Cobertura atual](../sistema/qualidade/cobertura-atual.md)

Cada registro descreve o que foi observado numa data, com configuração,
proveniência, resultados e limites. Dados ausentes não devem ser inventados;
uma nova implementação não transforma resultados antigos em aprovação atual.

- [15/11/2026 — Ordem de esquema](2026-11-15-ordem-esquema/relatorio.md): comparação histórica com contrato anterior.
- [16/11/2026 — Movimento contextual](2026-11-16-movimento-contextual/relatorio.md): experimento pelo fluxo compartilhado, com [manifesto](2026-11-16-movimento-contextual/manifesto.json).
- [16/11/2026 — Preservação das análises](2026-11-16-preservacao-das-analises/relatorio.md): inventário offline de três registros, com [hashes e relocações](2026-11-16-preservacao-das-analises/manifesto.json); nenhuma nova medição de IA.
- [16/11/2026 — Conclusão de turnos de NPCs](2026-11-16-conclusao-turnos-npc/relatorio.md): execução focada, falhas preservadas e reavaliação após corrigir a instrução de movimento.
- [17/11/2026 — Conhecimento dos NPCs](2026-11-17-conhecimento-npcs/relatorio.md): memórias, informação antiga e relatos; quatro casos live aprovados na revisão medida e refinamentos finais locais.
- [17/11/2026 — Disposição social](2026-11-17-disposicao-social/relatorio.md): alinhamento, persona e novas informações; correções de critérios, falha real no registro de ofertas e aprovação focada após correção, com memória live incompleta.
- [17/11/2026 — Vínculos por memória](2026-11-17-vinculos-memoria/relatorio.md): mesma alegação em vários interesses sem pontuação duplicada; três casos aprovados nas execuções registradas, com falha semântica inicial preservada.

- [17/11/2026 — Dificuldades contextuais e memórias](2026-11-17-dificuldade-contextual/relatorio.md): dez casos novos com execução aprovada, três falhas iniciais preservadas e 40 chamadas ao SDK.
- [17/11/2026 — Agência dos NPCs e fatos da narração](2026-11-17-agencia-npcs/relatorio.md): três casos novos aprovados, espera limitada, cochichos privados e off sem avanços; 33 chamadas incluindo revisão de linguagem.

- [17/11/2026 — Inspeção de passagens](2026-11-17-inspecao-passagens/relatorio.md): quatro casos novos aprovados, 11 chamadas; conferência sem abertura, memória de trancamento e esclarecimento sem ação.

Logs brutos permanecem nos diretórios locais indicados nos relatórios, ignorados
pelo Git. Estes relatórios não equivalem a autorização para repetir chamadas.

Para conferir os documentos e os logs locais disponíveis, use
`poetry run python tools/check_evidence.py`. Acrescente `--require-local` para
exigir todos os arquivos inventariados. Ausências num clone são informadas
explicitamente; conteúdo divergente sempre reprova. Veja o
[procedimento e seus limites](2026-11-16-preservacao-das-analises/relatorio.md#conferir-a-integridade).
