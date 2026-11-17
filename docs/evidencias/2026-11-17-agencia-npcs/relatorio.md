# Agência em exploração e fatos da narração — 17/11/2026

[Índice](../README.md) · [Implementação](../../sistema/aplicacao/intencoes-dos-npcs.md) ·
[Bateria](../../sistema/qualidade/agencia-live.md) · [Manifesto](manifesto.json)

## Resultado

Três casos novos foram aprovados na primeira rodada, com 27 chamadas ao SDK.
Uma revisão de linguagem reavaliou somente o caso de consulta off com as seis
chamadas restantes: **33 no total**, teto autorizado pelo usuário. As quatro
execuções completas foram aprovadas; nenhuma suíte live anterior foi executada.

| Rodada | Casos | Chamadas | Observação |
| --- | --- | --- | --- |
| `20261117T221855-66f13b3e` | Negociação da dungeon, vigia genérico e consulta off | 12 + 9 + 6 | Critérios funcionais aprovados; uma resposta off citou `heard_by`. |
| `20261117T222332-1bfc00e4` | Somente consulta off | 6 | Fatos corretos em linguagem de mesa, sem nomes internos. |

Perfil padrão da aplicação, modelo efetivo `gpt-5.6-terra`, sem configuração
experimental, sem retries de transporte e sem substituir respostas reais.
Configuração, decisões e consumo estão no [resumo](resumo.json). Não se estima
valor monetário sem a tabela do provedor.

## Falha original e correção

A sessão `d23dc26c34414556a64faa0bc054f833` registrou uma fala `quiet` do jogador,
ouvida apenas pelo prisioneiro, e uma resposta também privada. Na pergunta off
seguinte, o narrador afirmou que o guarda estava “ouvindo a conversa”. Os eventos
selecionados, timestamps, interação e hashes originais estão na
[fonte preservada](fonte-da-regressao.json); os logs originais não foram reescritos.

A limitação de agência vinha da negociação pendente sem acompanhamento: falas
com terceiros podiam manter o guarda indefinidamente em `listening`. O novo
acompanhamento acontece após os efeitos reais, no mesmo fluxo oficial. Recebe
somente sentidos, memórias e persona próprios e as comunicações percebidas; texto
inaudível é nulo. Uma espera breve precisa de motivo e não pode ser renovada sem
uma troca audível respondida ao NPC. Isso não força agressão nem cria turnos em
exploração.

O narrador agora recebe o registro recente de comunicações e instruções para
respeitar volume, ouvintes e efeitos efetivamente executados, inclusive em off.
Após a primeira medição, reforçamos que respostas usam linguagem de mesa sem
campos internos. O caso off foi reavaliado dentro do orçamento restante.

## O que os casos mostraram

Na dungeon, a oferta de ouro estabeleceu escuta com custódia. Após um cochicho ao
prisioneiro, o guarda disse que não ouviu e cobrou uma resposta mais alta. Após
outra fala privada, aguardou brevemente uma resposta concreta. A consulta off
negou compreensão dos cochichos e não inventou deslocamento ou ataque.

No cenário genérico, o NPC `warden`, chamado Vigia Mauro, aguardou uma vez e depois
exigiu uma resposta audível. Isso usa o mesmo acompanhamento sem referência a
`guard_1` ou ao roteiro da dungeon. A palavra secreta não foi entregue ao contexto
do vigia, aprendida por ele ou repetida em sua fala.

No caso off, duas perguntas sucessivas despacharam somente narração e conservaram
o estado inteiro, incluindo intenção e comunicações. A revisão final explicou
que o guarda não ouviu as palavras e não realizou novas ações desde a pergunta
anterior. Nenhum caso concedeu deslocamento, dano, chave, pagamento ou libertação
sem operação. Revisamos os textos salvos além das verificações automáticas.

## Testes locais e limites

A execução local ampla teve **1.189 aprovações e uma falha** num double antigo que
retornava plano vazio também para a nova fase. O arranjo agora fornece uma intenção
e espera explícitas, preservando o critério original: informação irrelevante não
reavalia disposição social. Depois do ajuste e das revisões de ciclo de vida,
**212 regressões locais focadas passaram**. A execução integral não foi repetida.
Os registros completos locais estão inventariados no manifesto.

Os testes cobrem espera limitada, retomada após diálogo audível sem Influence,
proteção da primeira resposta, ausência de ação duplicada, erro, reinício,
consulta off sem avanço, ocultação de palavras e memória alheia, encerramento
de conversa e iniciativa antes de movimento/ataque. Entrar em combate também
limpa objetivos de exploração. Esses refinamentos finais de ciclo de vida foram
verificados localmente; não acrescentamos chamadas pagas após atingir o teto.

Os contratos foram revisados com motivo, atualizados intencionalmente e conferidos
sem rede. `poetry check` e integridade das evidências passaram. O mesmo commit
inclui o painel de iniciativa anteriormente implementado, validado nas regressões
de interface; ele não cria chamadas de IA.

Esta versão acompanha interlocutores já envolvidos e percebendo a atividade. Não
implementa planejamento geral de todos os NPCs nem relógio em tempo real. Ações
físicas fora desse recorte continuam precisando de operações próprias. O filtro
lexical detecta a falha de audição conhecida, mas não prova toda a prosa livre;
a revisão humana e os resultados de uma rodada não garantem respostas futuras.

## Preservação

Os logs completos estão em `logs/live/agency/<rodada>/<caso>/trace.jsonl` e
`result.json`, com pedidos, respostas, estado, rolagens, erros e orçamento.
[Revisão inicial](revisao-inicial.json), [revisão final](revisao-final.json) e
[contratos efetivamente enviados](contratos-enviados.json) distinguem as versões.
Artefatos anteriores da dificuldade, disposição e memórias foram preservados.

```sh
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-17-agencia-npcs/manifesto.json --require-local
```
