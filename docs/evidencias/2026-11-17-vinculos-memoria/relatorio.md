# Vínculos de memória e disposição — 17/11/2026

[Plano e critérios](../../sistema/qualidade/vinculos-memoria-live.md) ·
[Regra](../../sistema/aplicacao/disposicao-social.md) · [Manifesto](manifesto.json)

## Problema e correção

A interação `e96eba4ba822425e94b547d0fe81b0a0`, da sessão
`dff07d768e90449c81bdd79d2f2fad16`, falhou às 13:43:28 UTC porque o Mundo
vinculou a alegação de filiação nobre a segurança e emprego. A validação antiga
proibia a mesma Claim duas vezes, apesar de serem interesses diferentes.
A resposta foi preservada em `tests/fixtures/social_memory_links/world_response.json`;
`source.json` registra chamada, instante e hashes da linha/texto originais. O
arquivo `logs/trama.jsonl` pode continuar crescendo; não inventariamos seu hash
inteiro como se fosse um artefato estável.

Agora cada par Claim/interesse pode aparecer uma vez. O motor preserva todos os
vínculos em `impacts`, agrupa por Claim e aplica uma contribuição por fato.
Soma os efeitos e limita a -1/0/+1 antes do peso da fonte: dois efeitos positivos
de um relato valem +1; efeitos opostos se compensam. Mantêm-se validação de
posse/relevância e limite global de memórias ±3. O perfil do guarda inclui
parentesco nas âncoras de emprego, pelo medo de represálias que já possui.

A resposta exata rejeitada agora percorre parser e runner nos testes locais:
promessa + nobreza contribuem 2, não 3; a parcela de persona é -1, o total é 1,
há hesitação e d20=20 resolve o teste. Nenhum diálogo live usa essa resposta
congelada. Repetir o mesmo fato/interesse continua inválido, com causa específica
visível na mensagem pública de erro do transporte.

## Configuração e escopo

Três situações `memoria-vinculos-*` na dungeon padrão, jogador [8,20], guarda
[10,6], porta aberta, modo narrado e abordagem pendente. A preparação usa a
operação pública de chamar o guarda, com sua resposta sensorial/rotina reais.
É um recorte desde abordagem preparada, sem interpretação live da preparação,
partida inteira ou janela Pygame.

Os lives usam `open_situation`, configuração padrão e `game.runner.submit`:
interpretador, Mundo, validação, regras e narração reais. Modelo efetivo
`gpt-5.6-terra`, SDK 3.49.0, contexto minimal, reasoning low, timeout 30 s,
retries 0, até uma correção de interpretação, saída de 1000 tokens para
interpretação/narração e 2000 para Mundo. Não houve abertura paga nem execução
de outras suítes live.

## Execuções, incluindo a falha

| Diretório em `logs/live/memory-links/` | Caso | Resultado | Chamadas |
| --- | --- | --- | ---: |
| `20261117T141938-7e865c3f` | Original | Falhou nos critérios semânticos; não houve rejeição de transporte. | 3 |
| `20261117T141938-7e865c3f` | Consequências | Aprovado. | 3 |
| `20261117T141938-7e865c3f` | Repetição | Aprovado nas duas mensagens. | 6 |
| `20261117T164734-f1d19b87` | Original, revisão | Aprovado. | 3 |

Total: **15 chamadas**, dentro do teto agregado de 16. A autorização do usuário
era corrigir o problema e criar/rodar três lives focados. O caso original recebeu
uma única revisão após a falha, usando a reserva; os demais não foram repetidos.

Na primeira execução, o Mundo classificou a ajuda para escapar como `access`
em vez de `release` e usou a suspeita antiga sem pontuar a nova alegação do
jogador como relato. Os critérios reprovaram isso. O contrato passou a distinguir
soltura/fuga de acesso a uma área, e a exigir que a alegação nova relevante use
a Claim atual, sem substituí-la pela suspeita sobre preso não identificado.
Os critérios e a frase original não foram relaxados. A revisão passou.

Os dois outros casos passaram antes dessa última revisão de instruções; não
foram novamente medidos após ela. Portanto, três casos têm execuções aprovadas,
mas não houve uma nova bateria completa dos três na revisão final do prompt.

## Efeitos observados e revisão narrativa

No caso de consequências, o Mundo propôs dois vínculos para a nova alegação e
dois para a suspeita anterior. O motor produziu dois fatos com score +1 cada:
parcela de memória 2, persona 4, total 6, disposto sem dado. A fala normal foi
ouvida a 22,5 m pelo alcance de conversa, sem avanço de nenhum personagem.

No caso de repetição, a alegação de nobreza afetou segurança e emprego e valeu
um único ponto; a promessa acrescentou outro. Persona limitada a 6, memória 2,
total 8: disposto. A segunda mensagem reutilizou a decisão sem dado nem
reavaliação. A variação de redação da Claim de recompensa pelo interpretador
não provocou outra resolução: o Mundo vinculou a memória anterior equivalente.

Na revisão do original, `goal=release`; promessa e filiação nobre foram relatos
distintos, com dois vínculos para a filiação e score 1 para cada fato. Total 8,
disposto sem dado. O guarda respondeu: “Se isso for verdade, não vou pagar para
descobrir o contrário. Vamos conversar sobre essa riqueza.” A narração registrou
que ele não se aproximou nem liberou passagem. Esta implementação registra a
concessão/condições; não adiciona executor genérico de soltura ou suborno pago.

Em todas as interações examinadas permaneceram posição, PV, recursos, portas,
inventário, custódia física e ausência de combate. Revisão da prosa não encontrou
pagamento, chave entregue ou fuga narrada como concluída. Não é garantia geral
de fidelidade da IA nem de estabilidade das disposições em outras execuções.

## Verificação local e preservação

Passaram **95 testes locais relacionados**, sendo 21 novos em
`test_memory_evidence_links.py`, além dos testes de disposição, transporte social
e audição de conversa. O parser recebeu a resposta real, sem remover as duas
justificativas. Há testes de efeitos positivos/negativos/opostos, ordem, fontes,
limite global, vínculos irrelevantes, mensagem de erro e reinício. O critério live
é exercitado pelo runner com adaptadores locais e reprova pontuação adulterada.
A suíte local completa não foi executada.

Os contratos de IA foram revisados e conferidos offline; a amostra acrescenta
os vínculos agrupados ao contexto de decisões do Mundo, sem expô-los ao narrador.
`revisao-inicial.json` e `revisao-final.json` conservam fontes e contratos medidos.
O manifesto relaciona configuração, tentativas, tokens e hashes de artefatos
versionados e logs locais. Falhas e inventários anteriores permanecem intactos.

```bash
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-17-vinculos-memoria/manifesto.json --require-local
```
