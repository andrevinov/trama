# Conhecimento dos NPCs — 17/11/2026

[Evidências](../README.md) · [Escopo da bateria](../../sistema/qualidade/conhecimento-live.md)
· [Contrato implementado](../../sistema/aplicacao/conhecimento-dos-npcs.md)

## Resultado observado

Os quatro casos novos passaram na revisão medida, com 18 respostas de IA:

| Caso | Resultado e observação | Chamadas com resposta |
| --- | --- | ---: |
| `memoria-inicial` | Arquivista citou sua inspeção anterior; jogador e aprendiz adquiriram um relato com fonte e referência à memória original. | 3 |
| `memoria-desconhecida` | Sem lembrança inicial, reconheceu não saber e não forneceu a posição oculta do objeto. | 3 |
| `memoria-desatualizada` | Informou a coluna 13 da lembrança, qualificando a ocasião; a chave real na coluna 18 permaneceu desconhecida ao NPC. | 3 |
| `memoria-relato` | Recebeu relato do jogador sobre a coluna 18, preservou sua observação da coluna 13 e atribuiu a informação recente ao jogador na resposta seguinte. O objeto não se moveu. | 9 |

Revisão humana da prosa: respostas coerentes com as fontes e a incerteza. No
último caso, o arquivista disse não poder confirmar o relato, distinguindo-o do
local onde viu a chave pessoalmente. Não houve iniciativa, movimento, dano,
mudança de portas ou gasto de recursos. Os critérios não exigiram redação única.

## Preparação, composição e limites

O usuário autorizou implementar e executar somente os testes novos. A bateria
usa situações do catálogo, carregador, `open_situation`, `game.runner`, contextos
e composição padrão reais. O cenário genérico tem arquivista e aprendiz na sala
oeste, separados da chave por uma porta fechada. Memórias e variações são dados
validados da aplicação; não há prompt alternativo nem plano de IA substituto.

A localização oculta diferente da lembrança foi declarada antes da construção.
O caso não demonstra deslocamento live de objeto estático, operação que não faz
parte deste recorte. Coleta física não acontece nesta bateria; as regressões
locais incluem a chave da dungeon sendo pega sem o prisioneiro testemunhar.

Configuração medida: `gpt-5.6-terra`, SDK 3.49.0, perfil padrão, contexto mínimo,
esforço `low`, ordem de esquema com operação primeiro, timeout 30 s e zero retries
de transporte. Correção do interpretador permitida pela composição, sem ser
necessária nesta amostra. Configurações efetivas e payloads ficam nos artefatos.

## Tentativas, orçamento e proveniência

Plano anterior às chamadas: uma tentativa por caso, 18 chamadas normais e teto
de 24 tentativas do SDK, incluindo correções. Não foram executadas suítes live
anteriores nem a suíte local completa.

| Execução local em `logs/live/knowledge/` | Resultado | Tentativas / respostas |
| --- | --- | ---: |
| `20261117T042916-a0224c11` | Quatro falhas de conexão dentro da sandbox, uma por caso; nenhum modelo respondeu. Os testes e traces dessas falhas permanecem preservados. | 4 / 0 |
| `20261117T104100-b6d33083` | Reexecução fora da sandbox após aprovação de acesso à rede: quatro casos aprovados. | 18 / 18 |

Na retomada, `TRAMA_KNOWLEDGE_CALLS_RESERVED=1` descontou uma tentativa de cada
caso. Tetos restantes: 3, 3, 3 e 11. Total efetivo: **22 tentativas, 18 respostas**,
abaixo das 24 planejadas. Não houve repetição de uma resposta desfavorável do
modelo até obter sucesso; as únicas falhas da primeira execução foram de conexão.

Uso agregado reportado: 117.611 tokens de entrada e 2.013 de saída, 119.624 no
total. Não foi calculado valor monetário. Os horários dos identificadores são
UTC; ambas as execuções ocorreram em 17/11 no fuso UTC−3.

O [manifesto](manifesto.json) conserva caminhos literais, tamanhos, SHA-256,
configuração, orçamento e hashes das instruções por fase. Há um snapshot local
dos onze arquivos centrais da revisão medida em
`20261117T104100-b6d33083/source_snapshot/` e seu inventário em `source-at-live.json`.
Não é uma cópia completa do ambiente ou do checkout.

## Refinamentos posteriores à medição

A revisão final acrescentou três proteções verificadas somente offline:

1. Reconfirmar diretamente uma localização supera um relato conflitante, mesmo
   quando já existia observação antiga do mesmo local; não deduplica essa nova
   confirmação como se nada tivesse acontecido.
2. Perguntas off recuperam memórias próprias usando o assunto perguntado, sem
   aquisição ou alteração do estado e sem memórias privadas de NPCs.
3. A transmissão não copia o contexto interno do falante. A projeção pública
   de `shared_memories` contém somente id, dono, afirmação, texto, origem e ocasião.

Esses ajustes não receberam outra execução paga. O manifesto distingue os hashes
do código medido e do código final; a aprovação da bateria não é atribuída
retroativamente aos contextos finais. A remoção dos campos internos foi revisada
e registrada no contrato de IA, seguida de conferência offline estável.

## Testes locais novos e limites da evidência

**52 testes locais novos passaram**, em 8,62 s, cobrindo origem, fontes
encadeadas, contradições, persistência JSON, reinício, audição, sono, divulgação,
seleção limitada, campos de transporte e os critérios/registro dos live tests.
Incluem o prisioneiro com/sem lembrança, falta de testemunho ao pegar a chave,
Prestidigitação bem-sucedida, posição lembrada na navegação e conhecimento de
existência sem localização. A suíte anterior não foi executada, por solicitação
do usuário. Os contratos, metadados Poetry e integridade das evidências foram
verificados separadamente, sem chamadas de IA.

As referências validam a origem estruturada. Não provam toda frase livre de uma
IA, qualquer mentira, aquisição de todo fato possível ou toda decisão de
divulgação. Não há teste de UI gráfica, benchmark de uma campanha grande ou save
completo de jogo. A seleção pode omitir memórias por orçamento e não equivale a
um inventário exaustivo do que um NPC sabe.

## Conferência sem rede

```bash
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-17-conhecimento-npcs/manifesto.json --require-local
```

Os logs brutos e snapshots ficam locais, ignorados pelo Git. Este é um registro
novo; inventários e hashes históricos anteriores permanecem intactos.
