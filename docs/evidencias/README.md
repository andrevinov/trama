# Evidências e experimentos datados

[Visão geral](../../README.md) · [Cobertura atual](../sistema/qualidade/cobertura-atual.md)

Cada registro descreve o que foi observado numa data, com configuração,
proveniência, resultados e limites. Dados ausentes não devem ser inventados;
uma nova implementação não transforma resultados antigos em aprovação atual.

- [15/11/2026 — Ordem de esquema](2026-11-15-ordem-esquema/relatorio.md): comparação histórica com contrato anterior.
- [16/11/2026 — Movimento contextual](2026-11-16-movimento-contextual/relatorio.md): experimento pelo fluxo compartilhado, com [manifesto](2026-11-16-movimento-contextual/manifesto.json).
- [16/11/2026 — Preservação das análises](2026-11-16-preservacao-das-analises/relatorio.md): inventário offline de três registros, com [hashes e relocações](2026-11-16-preservacao-das-analises/manifesto.json); nenhuma nova medição de IA.

Logs brutos permanecem nos diretórios locais indicados nos relatórios, ignorados
pelo Git. Estes relatórios não equivalem a autorização para repetir chamadas.

Para conferir os documentos e os logs locais disponíveis, use
`poetry run python tools/check_evidence.py`. Acrescente `--require-local` para
exigir todos os arquivos inventariados. Ausências num clone são informadas
explicitamente; conteúdo divergente sempre reprova. Veja o
[procedimento e seus limites](2026-11-16-preservacao-das-analises/relatorio.md#conferir-a-integridade).
