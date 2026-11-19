# Memórias contextualizadas dos personagens

Tier 3 · [Aplicação](README.md) · [Contratos de IA](../ia/contextos-e-contratos.md)

## Objetivo e regra do Trama

Conhecimento é uma crença de um personagem, com origem e ocasião. Ele não é
atualizado pela verdade oculta do mapa. Esta é uma decisão de projeto solicitada
pelo usuário, não uma regra nova de D&D nem um teste de atributo.

`trama.knowledge` contém os registros e índices, sem SDK, mapa ou cenário.
`application.knowledge.KnowledgeSystem` usa os sentidos reais para adquirir e
transmitir informações. A sessão e os executores existentes continuam sendo
os responsáveis pelas ações; não há outro coordenador nem chamadas extras à IA.

## Registro e preparação

Cada NPC em `creatures` ou `observers` pode declarar `knowledge`:

```json
{
  "id": "key-custodian",
  "claim": {"subject_id": "cell_key", "predicate": "custodian", "value": "guard_1"},
  "text": "É o guarda quem fica com a chave das celas. Não sei onde ele a mantém.",
  "source": {"kind": "observation", "event_id": "prisoner-learned-key-custody"},
  "when": "Durante sua prisão.",
  "context": "O prisioneiro conhece o responsável pela chave, mas não onde ela fica.",
  "entities": ["guard_1", "gate_2"],
  "topics": ["escape", "chave"],
  "shareable": true
}
```

O dono vem do NPC; o id final é `<npc>:<id>`. A afirmação tem entidade, relação e
valor, permitindo consultar e contrariar o mesmo assunto sem comparar frases.
`text`, `when` e `context` preservam o significado e a ocasião. `entities` e
`topics` são âncoras de consulta. `shareable=false` impede divulgação por referência;
a IA ainda considera interesses e situação para decidir compartilhar as demais.

Origens: `observation`, `report`, `inference`, `habit`. Relatos exigem `actor_id`.
Inferências e hábitos podem ser declarados inicialmente; não existe motor de
inferência automática. Valores de localização podem ser ids de lugares,
`position:coluna,linha` em base 1 ou `carried:id`. A localização lembrada pode
continuar errada. Um relato que só revela a existência de um item não concede
sua localização. Locais abstratos não ganham navegação automática por este recorte.

## Aquisição e contradições

- Portas e objetos estáticos expostos produzem observações para quem realmente
  os vê; paredes, escuridão, distância, sono e visão própria continuam valendo.
- Na dungeon, itens expostos e eventos presenciados de descoberta, coleta e
  descarte usam o mesmo serviço. A visibilidade física (`exposed_items`) é
  separada do que o jogador ouviu ou descobriu. Prestidigitação bem-sucedida ao
  pegar a chave não informa o furto ao guarda que foi enganado.
- Observação nova substitui a crença ativa do mesmo personagem/assunto/relação,
  sem apagar a anterior. Observar a mesma coisa novamente não duplica memórias.
- Relatos conflitantes coexistem com observações. Eles não mudam o mapa,
  inventário, portas ou recursos. Não há atualização automática nem expiração
  por uma mudança que o NPC não presenciou.

`acquired_at` é uma sequência lógica de aquisição, não segundos fictícios.
`when` descreve a ocasião informada, preservada quando uma lembrança é repassada.
Novos relatos registram o momento de aquisição mesmo quando repetem um valor.
`source.event_id`, `source.actor_id` e `source.memory_id` permitem seguir a cadeia
até a lembrança citada. `knowledge.acquired` registra aquisições nos logs.
Uma inspeção direta que reconfirma um local supera um relato conflitante, mesmo
se esse local também constava de uma observação antiga.

## Fala e autorização

O Mundo propõe `say` com `memory_ids` do próprio falante. O código rejeita ids
desconhecidos, de outro personagem e memórias privadas antes de transmitir.
Saudações, ameaças e respostas sem conteúdo factual podem usar lista vazia.

Ouvintes conscientes, alcançados pelo som, aprendem as afirmações citadas como
`report`, com o falante como fonte imediata e a memória original referenciada.
Fala normal com contato visual mútuo usa a [margem de conversa de 50%](../mundo/visao-e-percepcao.md#audição-e-decisões-explícitas-do-trama),
nos dois sentidos; ruídos incidentais e sussurros conservam o alcance anterior.
Quem desperta com uma fala não recebe retroativamente seu conteúdo. O jogador
também pode aprender pelo som, sem ganhar o item. Memórias não são transmitidas
por perguntas off, narração nem pela simples presença de outro personagem.
O novo contexto do ouvinte registra a fala recebida. O contexto interno do
falante não é copiado; `shared_memories` publica somente id, dono, afirmação,
texto, origem e ocasião. Perguntas off podem consultar memórias próprias do
jogador, sem aquisição, ação ou avanço de NPCs.

Em `speak`/`challenge`, o interpretador pode propor até três `claims` que o
jogador está afirmando. São relatos não confirmados, inclusive se forem falsos.
Perguntas, hipóteses e negações usam lista vazia. NPCs não fabricam novas
afirmações estruturadas por fala: compartilham referências próprias.

Os ids validam origem e autorização da informação estruturada. Não demonstram
que cada frase livre da IA é semanticamente fiel: essa parte exige instruções,
testes live e revisão do texto preservado, sem presumir garantia determinística.

## Seleção e custo

O armazenamento mantém índices por dono, entidade, assunto e palavras sem
acentos. A seleção usa mensagem atual, lugar do jogador e lugar do NPC. O contexto
do Mundo considera até oito NPCs relevantes por visão, audição ou iniciativa,
priorizando o ativo e a proximidade. Não percorre todas as memórias para procurar
uma palavra; consultas usam os índices.

Limites por projeção: seis memórias e 3.500 caracteres de conteúdo JSON por
personagem; conjunto de NPCs limitado a 9.000 caracteres de conteúdo. São limites
de caracteres, não tokens nem preços. Histórico e registros superados ficam no
armazenamento, fora do prompt. Uma informação pode ficar fora da seleção;
ausência na seleção não é prova de ignorância absoluta do personagem.

`knowledge` na raiz de interpretação e narração contém somente memórias do
jogador. `world.knowledge.actors` é exclusivo do contexto de decisão do Mundo.
A narração recebe os fatos compartilhados em `shared_memories`, preservando
ocasião e fonte. O estado completo de mestre não concede conhecimento ao NPC.

`KnowledgeStore.export()`/`restore()` preservam memórias, fontes e substituições
em dados JSON. O reinício da sessão restaura as memórias iniciais. Não há banco
vetorial, serviço de memória, save completo de campanha, inferência semântica
automática, detecção genérica de ausências ou sistema de reputação neste incremento.
O armazenamento é local e indexado; a execução continua limitada aos mapas e
às operações atualmente suportados pelo Trama.

## Prisioneiro e testes

O prisioneiro agora recebe sua lembrança da chave nos dados do NPC. Ao despertar,
o roteiro pode pedir ajuda e compartilhar uma memória de fuga autorizada; sem
ela, não revela a chave. A memória padrão indica somente quem fica com a chave,
sem posição de armazenamento. O guarda tem lembranças distintas da ordem de
prisão de seu chefe, da possível filiação nobre de um prisioneiro e do medo
condicional de represálias, sem identidade ou parentesco confirmados.
Conhecer um local antigo não revela a posição oculta atual
ao jogador nem fornece uma rota até ela. Fala e personalidade ainda têm partes
de cenário; o conhecimento e sua transmissão são gerais.

As regressões locais novas ficam em `test_knowledge_memories.py`,
`test_npc_knowledge.py`, `test_knowledge_transport.py` e
`test_knowledge_live_scenarios.py`. A avaliação real tem
[casos e orçamento próprios](../qualidade/conhecimento-live.md).

Na audição através de portas, perceber uma voz e compreender suas palavras são
avaliações distintas. Som percebido não basta para aprender Claims. Referências
privadas redundantes de Influence em gravações antigas são validadas sem
compartilhamento; a saída atual só permite `memory_ids` públicos em `say`.
Veja [avaliação contextual](avaliacao-de-dificuldade.md).

O passo 6 registra autoria de operações de porta e ataques diretos com dano
somente para quem vê autor e resultado. Também consolida compromissos e pendências
no fechamento percebido e conserva inferências privadas sobre episódios. A
substituição de um resumo ativo preserva sua história; ele não vira observação
nem é compartilhado por `memory_ids`. A seleção dá pertinência a esses tópicos,
mantendo os limites existentes. Política, deduplicação entre M/R e alcance das
observações estão em [evolução das relações](evolucao-das-relacoes.md).

Aquisições pertinentes também podem notificar a
[reconsideração por acontecimentos](acontecimentos-e-prioridades.md). Relato
permanece relato. Ver apenas um ferido produz observação da condição sem
identificar o agressor; só ver autor e resultado sustenta atribuição de autoria.
Notificação privada não transmite a memória aos outros participantes.

Para a decisão individual, a seleção também considera a área atual do NPC e
as comunicações recentes que ele compreendeu, além do objetivo. Isso permite
recuperar uma ajuda anterior ou um caminho conhecido numa conversa casual,
sem importar o histórico onisciente. Continuam os mesmos limites por dono;
uma orientação falada chega ao ouvinte como relato e não o desloca até o destino.

## Vínculos e disponibilidade declarada

Os [vínculos qualitativos](vinculos-afetivos.md) geram resumos próprios
`relationship_bond`, não compartilháveis e excluídos de M ou de novas provas.
Uma declaração própria de abertura/recusa registra `romance_boundary:<alvo>`
somente a partir de fala validada: observação de dizer para o falante e relato
para quem compreendeu. Isso registra disponibilidade declarada, sem provar
sentimento ou reciprocidade. Repetição conhecida não gera nova aquisição.
