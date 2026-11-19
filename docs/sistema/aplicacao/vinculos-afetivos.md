# Amizade e vínculos amorosos

Tier 3 · [Aplicação](README.md) · [Relações](relacoes-iniciais.md) · [Situações jogáveis](../simulador/vinculos-afetivos.md)

`bonds.py` define vínculos qualitativos direcionais de um NPC para outro
personagem; `application/bonds.py` valida as interpretações do diretor sobre
memórias reais do dono. `RelationshipState` mantém estado, motivo, fontes e
história. São critérios de implementação do Trama, sem regra oficial de D&D ou
pretensão de descrever uma lei psicológica.

Confiança e afeto continuam independentes. Os vínculos não adicionam pontos a
`S_opcao`, não mudam CDs e não obrigam aceitação. Alinhamento e persona permanecem
estáveis. O diretor pode mudar prioridades, oferecer cuidado ou recusar com
franqueza conforme o vínculo, respeitando seus interesses e limites próprios.
O sistema não mantém sentimentos inferidos do jogador ou reciprocidade automática.

## Formação e evidências

Cada tipo tem estado `absent`, `active` ou `ended`. O diretor propõe até oito
`BondUpdate` em `WorldReaction.bonds`, com `owner_id`, `target_id`, `kind`,
`state`, `reason` e de uma a oito `evidence_ids`. A atualização só ocorre em
`player_action` narrado ou `npc_review`, antes das opiniões; agência escolhe a
ação depois dessa validação. Não há interpretação durante o turno de combate.

| Tipo | Critério de formação em jogo |
| --- | --- |
| `friendship` | Dois episódios distintos de cuidado observado: um praticado pelo dono e outro pelo destinatário. |
| `attraction` | Interpretação própria apoiada em observação de um encontro com o destinatário. Não exige amizade nem nível mínimo. |
| `infatuation` | Atração própria ativa e novo encontro significativo observado depois dela, em episódio distinto. |
| `love` | Amizade e paixão próprias ativas, cuidado nas duas direções e novo cuidado observado do destinatário depois da paixão. |

Cuidado exige observação autoral com tópico `care`/`costly_help` ou episódio
`care_shown`/`costly_help` já validado pela [política numérica](evolucao-das-relacoes.md).
Encontro significativo usa cuidado ou tópico autoral `personal_encounter`.
Relato, saudação e pontuação alta não satisfazem essas condições. Cuidado
recíproco descreve ações percebidas, sem provar sentimentos recíprocos.

As fontes devem ser memórias ativas do próprio NPC, ligadas ao destinatário.
Resumos derivados de relações, vínculos, compromissos e pendências não substituem
evidência. `latest_observation`/`latest_report` resolvem a última fonte pertinente
após a execução real, não um fato que o diretor apenas sugeriu. A sequência de
aquisição impede avançar por vários estágios usando a mesma história antiga.

A classificação semântica continua sendo responsabilidade do diretor e do autor:
fechar qualquer porta não prova cuidado por si só. O código verifica categoria,
fonte, dono e sequência; não interpreta sozinho o significado humano do gesto.

## Manutenção, ruptura e continuidade

Um vínculo ativo permanece sem atualizações periódicas. Para registrar nova
interpretação mantendo `active`, é necessário acontecimento próprio posterior.
Encerrar exige vínculo ativo, evidência posterior e motivo. Uma reaproximação
também exige evidência nova e os critérios de formação. Repetir o mesmo estado
com as mesmas fontes não gera outra mudança, mesmo usando aliases.

Ruptura preserva antes/depois e proveniência; não apaga a história. Redução de
confiança não termina amor automaticamente. Encerrar paixão não encerra os
outros tipos. Os requisitos de formação não são condições que precisam ser
continuamente recalculadas para manter um sentimento.

Não há progressão ou decaimento por tempo, número de falas ou frames. A evolução
depende de acontecimentos e interpretação explícita. Reiniciar restaura a base
autoral e limpa as mudanças; salvar campanha fora do processo permanece fora do
recorte. Vínculos iniciais documentam história anterior ao jogo: exigem fontes
próprias, mas não reexecutam uma cronologia de formação anterior à sessão.
A sequência inicial de aquisição serve de base: lembranças já carregadas não
se tornam acontecimentos posteriores a um vínculo inicial.

## Disponibilidade e limites declarados

Romance requer `adult: true` explícito em ambos os participantes no cenário.
Ausência do campo significa elegibilidade não declarada; não se infere idade por
nome, papel ou ficha. Amizade não depende desse campo. O garoto do cenário casual
continua sem elegibilidade romântica.

Em uma fala real, `ConversationUpdate.romance_boundary` pode registrar `open` ou
`declined`, com um único destinatário e `boundary_text` literal presente na fala.
O campo descreve apenas a escolha declarada pelo próprio falante. `open` não
prova desejo, reciprocidade ou aceitação de uma proposta. Uma recusa pode ser
declarada por qualquer participante; abertura romântica exige ambos adultos.

O falante conhece sua declaração; apenas quem a compreendeu aprende um relato
dela. A memória diz que a pessoa falou, sem confirmar sua vida interior. O
prefixo de Claim `romance_boundary:` é reservado ao registro validado, evitando
forjá-lo por uma alegação comum. Essas memórias também não podem ser divulgadas
por `memory_ids`: repetir uma declaração antiga não substitui a exigência de
uma nova fala própria literal. Uma reabertura não ouvida não muda a crença do
NPC. Repetir a mesma declaração não cria conhecimento novo para quem já a conhece.

`romantic_expression=true` identifica uma expressão amorosa e exige elegibilidade,
ausência de recusa própria/do destinatário conhecida e, para NPC, sentimento
amoroso próprio ativo. Uma abertura própria explícita pode substituir sua recusa
anterior. Recusa conhecida bloqueia a expressão, sem apagar o sentimento privado
ou impedir conversa comum. O jogador continua dono de suas escolhas e expressões.

Esses campos dependem da interpretação correta da fala. O código valida o trecho
literal e os efeitos tipados; não reconhece lexicalmente toda aproximação amorosa
em texto livre. As instruções exigem classificação e respeito aos limites, mas a
qualidade semântica de um modelo real ainda precisa de avaliação manual.

## Contextos, privacidade e diagnóstico

O Mundo recebe `world.social.relationships`; revisão e agência recebem apenas
`relationships` do NPC solicitado. Cada par traz os quatro `bonds`, últimas
quatro mudanças e `romance` com `eligible`, `own_choice`, `known_target_choice` e
`can_express`. Um NPC sem relação inicial recebe projeção neutra para o jogador,
sem criar vínculo ou estado inverso. A base privada invalida opiniões antigas
quando muda; não calcula nova nota ou decisão automaticamente.

Interpretação e narração não recebem esses vínculos, fontes ou motivos privados.
Declarações realmente ouvidas e respostas executadas podem ser narradas. Resumos
de vínculo são inferências próprias, `shareable=false`, excluídas de M e de
novas evidências; não alimentam um ciclo de reconsideração. O histórico completo
fica na sessão em `relationships.bond_history(owner, target)` e no log privado
`relationship.bond_updated`.

As regressões em `tests/integration/test_relationship_bonds.py` usam o runner e
as situações oficiais com decisões fixas. Controles parciais verificam cronologia,
fontes, repetição e lotes inválidos; operações de porta classificadas como cuidado
são arranjos explícitos desses controles, não prova de julgamento semântico.
Os [contratos de IA](../ia/contextos-e-contratos.md) auditam projeções reais sem
rede. Não houve avaliação nova de modelo real para este incremento.
