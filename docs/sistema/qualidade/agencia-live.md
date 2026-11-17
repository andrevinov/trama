# Agência em exploração e fidelidade da narração — live

Tier 3 · [Qualidade](README.md) · [Política](politica-live-tests.md)

`tests/live/test_npc_agency_live.py` percorre `open_situation`, composição oficial
e `game.runner`, com uma rodada por caso e sem retries até passar. As entradas
estão em `tests/fixtures/agency/cases.json`; situações são carregáveis no simulador.
A preparação usa operações públicas reais e não substitui respostas do modelo.

| Caso novo | Escopo e critérios | Previstas / teto de chamadas |
| --- | --- | --- |
| agencia-negociacao | Aceitar escuta com propina na dungeon; duas conversas privadas com o prisioneiro devem provocar acompanhamento do guarda; off verifica acontecimentos sem avançar estado. | 12 / 14 |
| agencia-vigia-generico | Vigia de outro mapa e outro ID; cochichos inaudíveis não aparecem no contexto dele; ele toma iniciativa até a segunda oportunidade sem espera renovada. | 9 / 11 |
| agencia-off-consulta | Conversa privada seguida de duas perguntas off: nenhuma decisão nova ou mudança mecânica nas consultas; narrador não inventa audição, movimento ou ataque. | 6 / 6 (8 na primeira rodada) |

Orçamento inicial: **27 chamadas previstas, teto agregado 33**, três casos novos,
uma tentativa cada. A diferença permite correções limitadas do interpretador;
nenhuma repetição automática após falha. Após a aprovação dos três casos em 27
chamadas, o caso off foi reavaliado com as seis restantes para conferir a linguagem
de mesa sem nomes internos. Total medido: 33 chamadas. O perfil efetivo é o padrão da aplicação.
Criação dos casos não autoriza execução paga; solicitar autorização para a bateria
concreta antes de executar, preservando também falhas/inconclusivos.

A decisão adicional ocorre apenas quando um interlocutor continua envolvido após
uma ação significativa e ainda não respondeu. A etapa recebe observações resolvidas,
sem palavras inaudíveis. Os dados opcionais de d20 estão fixados nas situações:
evitam que iniciativa coloque o NPC antes do jogador nesta bateria. A cobertura
local verifica também a entrada em conflito sem aproximação ou ataque gratuito.

Critérios independentes: mensagens privadas executadas em `quiet`; NPC ausente
de `heard_by`; palavra marcadora ausente do contexto de acompanhamento e das falas
do NPC; presença de decisão e iniciativa própria; nenhuma transferência, dano,
movimento, abertura de porta ou libertação sem operação. Perguntas off despacham
somente narração e preservam a fotografia mecânica inteira. Uma espera pode ocorrer
uma vez, mas a sequência não pode terminar em duas esperas renovadas.

O verificador lexical detecta variantes da falha original de “ouvindo a conversa”.
Ele não compreende toda a prosa: a revisão humana dos textos salvos deve conferir
audição, causalidade, mudança de volume, pensamentos privados e todas as ações
atribuídas aos envolvidos. Validação estrutural e uma medição não garantem futuras
respostas. Testes offline incluem controles que reprovam estado físico alterado e
a afirmação antiga de audição, sem chamadas externas.

As evidências ficam em `logs/live/agency/<rodada>/<caso>/{trace.jsonl,result.json}`:
configuração, pedidos/respostas reais, contexto por fase, antes/depois, rolagens,
relatórios, texto, erros, tokens e orçamento. A fonte datada da falha está em
`tests/fixtures/agency/regression_source.json`, com hashes originais das linhas.

Execução somente após autorização do orçamento:

```sh
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_agency_live.py -m live -q
```
