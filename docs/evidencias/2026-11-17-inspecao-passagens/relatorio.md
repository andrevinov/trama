# Inspeção de passagens — 17/11/2026

[Evidências](../README.md) · [Casos e critérios](../../sistema/qualidade/inspecao-live.md)

## Resultado e escopo

Quatro casos novos aprovados, uma tentativa por caso, **11 chamadas ao SDK**,
dentro do teto autorizado de 15. Nenhuma outra suíte live foi executada.
Execução `20261117T232158-47cf8f14`, modelo efetivo `gpt-5.6-terra`, pela composição normal,
`open_situation` e `game.runner.submit`. A preparação usa operações públicas;
não mede a interpretação das ações anteriores nem a janela Pygame.

| Caso | Chamadas | Observação |
| --- | ---: | --- |
| Cela 4 silenciosa | 3 | Frase original interpretada como inspeção; grade continua fechada/destrancada. Furtividade 17 preservada, nenhum dado novo ou item. |
| Porta genérica trancada | 3 | Confere o mecanismo; confirma trancada sem abertura/destrancamento. Furtividade 17 preservada. |
| Apenas olhar de longe | 3 | Informa fechada e mantém trancamento desconhecido; posição, recursos e conhecimento iguais. |
| Alvo ainda indefinido | 2 | Pergunta qual grade; não consulta o Mundo nem executa ações, som ou testes. |

Sem falhas, correções adicionais ou repetições pagas nesta bateria. Dados, eventos,
planos, estado antes/depois e narrador foram conferidos. As quatro respostas foram
lidas: sem abertura, deslocamento, conhecimento secreto ou teste inventados.
A pergunta de esclarecimento aparece repetida em off pelo complemento
determinístico do impedimento: ressalva editorial, sem avanço do jogo.

## Regra implementada

Inspeção é uma operação geral, separada de abrir, destrancar e investigar um
cômodo. Aparência fechada não revela trancamento. Conferir mecanismo simples e
acessível ao alcance é uma decisão determinística do Trama, sem CD inventada.
Mecanismo inacessível continua desconhecido; sua cobertura é local neste incremento.
Som usa percepção real e furtividade já obtida, sem Hide repetido.

O conhecimento da fechadura pertence ao jogador, com fonte; espectadores não
recebem automaticamente o resultado tátil. O estado completo de mestre permanece
separado do mapa mascarado e da lembrança do jogador.

## Revisão e verificações locais

Base Git: `f9740cb78c8c4fd014f627138c6b60363b2637d9`, árvore com alterações ainda não commitadas.
`revisao-da-medicao.json` preserva hashes anteriores e os fontes alterados medidos;
`contratos-enviados.json` vem dos pedidos reais, sem reconstruir prompts.
`revisao-final.json` separa dois refinamentos posteriores: permitir observação
visual durante abordagem e conservar movimento imediato ao apenas olhar. Esses
casos foram verificados localmente, sem nova avaliação paga; os quatro arranjos
medidos não dependem dessas condições.

Regressões pertinentes: **201 aprovadas**. Após os refinamentos, **58 aprovadas**
na seleção focada de inspeção, preparação/oráculos live, parley e agência.
As seleções se sobrepõem; não são contagens somáveis de casos distintos.
Não foi executada toda a suíte local ou live. Contratos reconstruídos conferem,
`poetry check`, `git diff --check` e integridade das evidências históricas passaram.

## Evidências e limites

Tokens agregados: entrada 101916, saída 1599,
total 103515. Configuração e detalhes por chamada estão em
`resumo.json`; nenhum valor monetário foi estimado.

Os critérios mecânicos têm controles negativos offline. A revisão humana do
texto não constitui prova universal da narração. Um sucesso por caso não mede
repetibilidade nem cobre mecanismos mágicos, armadilhas, escuridão ou inspeção
em combate com IA; esses limites não recebem aprovação live nesta medição.

Logs originais em `logs/live/passage_inspection/20261117T232158-47cf8f14/`, sem alterações.
O manifesto guarda hashes dos artefatos locais e versionáveis, incluindo a
regressão original selecionada. Novas medições devem receber registros próprios.
