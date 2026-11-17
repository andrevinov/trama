# Avaliação contextual de dificuldade

Tier 3 · [Aplicação](README.md) · [Percepção](../mundo/visao-e-percepcao.md)

O Mestre decide se uma tentativa incerta exige teste e sua dificuldade. A IA
exerce essa avaliação na decisão do Mundo que já existe; Python valida os fatos,
calcula a CD, rola os dados e aplica consequências. Não há chamada extra ao
provedor nem liberdade para a IA substituir regras com CD fixada.

## Inventário do incremento

| Tarefa implementada | Origem da dificuldade |
| --- | --- |
| Ataque | CA da ficha, fixa. |
| Hide | CD15; sucesso guarda o total como CD de detecção. |
| Search por criatura oculta | Total real de Furtividade; circunstâncias auditivas podem aplicar vantagem/desvantagem, sem trocar essa CD. |
| Influence, inclusive disfarce do cenário | Disposição e condições sociais; teste quando apropriado contra max(15, Inteligência do alvo). |
| Study de Ilusão Menor | CD da magia do conjurador: 13 para o prisioneiro atual. |
| Encontrar roupa escondida na Cela 4 | Search/Percepção contextual; espada evidente continua descoberta sem teste. |
| Escutar atividade além de uma passagem | Percepção contextual, com fonte e percurso auditivo reais. |
| Pegar chave exposta sem observador notar | Prestidigitação contextual; sem observador, não há teste de furto. |
| Examinar espada escondida no uniforme | Percepção contextual; arma exposta é evidente. |
| Notar ruído ou compreender palavras através de portas fechadas | Avaliação contextual distinta por finalidade, volume e barreiras reais. |
| Abrir passagem permitida, usar chave, pegar item conhecido livre | Validação determinística; sem nova CD inventada. |

Busca por objeto oculto passou de Investigação a Percepção, conforme Search.
O recorte não implementa ainda arrombamento com ferramentas ou tarefas gerais
novas: a regra de ferramentas/fechadura não é substituída por avaliação livre.
Alinhamento e persona continuam a política social do Trama, não pontos oficiais
de alinhamento previstos no D&D.

## Contrato e resolução

`world.adjudication.requests` contém IDs, tarefa, perícia e fatos identificados.
O Mundo devolve exatamente uma `Adjudication` por pedido ainda não avaliado,
com resultado `automatic`, `impossible` ou `check`. Um teste cita dificuldade
`very_easy/easy/moderate/hard/very_hard/nearly_impossible`, correspondendo a
5/10/15/20/25/30, e pode declarar vantagem/desvantagem. Sem teste, dificuldade
é nula e os modificadores são falsos. Sempre cita fatos fornecidos e razão curta.
Não fornece resultado de dado, modificador numérico ou efeitos materiais.

O executor recusa IDs desconhecidos, avaliações ausentes, fatos inexistentes e
decisões inválidas antes de executar ações. O fluxo oficial exige o conjunto
completo, inclusive em turno de NPC. Contextos prospectivos não representam
ruídos já emitidos: a IA não antecipa reações dependentes da detecção.

CDs fixas não são pedidos contextuais. A avaliação acústica classifica a tarefa,
não o sucesso de um NPC particular; cada ouvinte usa seus sentidos e bônus reais.
Percepção passiva é 10+bônus, +5 com vantagem ou -5 com desvantagem; ambas se
anulam. Busca ativa rola o d20 apropriado. Notar a voz não ensina suas palavras.
Quando a detecção procura jogador oculto, o total guardado de Furtividade tem
precedência sobre a categoria acústica proposta.

## Portas e cache

A geometria ainda verifica percurso, distância e capacidade auditiva antes do
teste. O acréscimo equivalente de 6m por porta e os alcances de som são recortes
autoriais do Trama, não regras universais de D&D. Estar geometricamente ao alcance
é possibilidade de ouvir; uma barreira pode tornar o teste difícil ou impossível.
Uma `Passage.description` opcional fornece fatos como espessura/frestas sem a
IA precisar inventá-los. O cenário padrão não presume materiais não descritos.

Avaliações são reutilizadas somente enquanto o pedido e seus fatos permanecerem
iguais. A política acústica é por portas atravessadas, volume e finalidade,
compartilhada por ouvintes; sentidos individuais e distância ficam no código.
Abrir a porta elimina sua barreira e reiniciar limpa o cache. Novos fatos/abordagem
invalidam decisões de tarefa. Isso não é simulação física de propagação sonora.

Preparações sem IA e consumidores determinísticos diretos conservam as CDs
autoriais anteriores (roupa15, escuta10, furto13, inspeção15). Esse fallback é
explicitamente registrado e não representa o fluxo oficial com diretor do Mundo.
Testes offline específicos fornecem decisões explícitas para exercitar os ramos.

## Referências de memória

O esquema novo separa `say` das demais operações: somente `say` pode propor
`memory_ids` públicos. Influence referencia Claims em sua avaliação privada.
Gravações antigas com referências redundantes em Influence podem ser lidas: o
executor exige memória pertencente ao ator e Claim citada na avaliação, registra
`private_memory_ids` no diagnóstico e não compartilha nem envia isso ao narrador.
Referências alheias ou sem fundamento continuam rejeitadas.

## Referências e limites

- [D&D 2024, D20 Tests e Typical Difficulty Classes](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game#D20Tests): Mestre julga tarefas, CDs típicas e circunstâncias.
- [Advantage/Disadvantage](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game#AdvantageDisadvantage): vantagem/desvantagem circunstancial.
- [Glossário: Search, Hide, Study, Influence e Passive Perception](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary): perícias, CDs fixadas e passiva ±5.
- [Minor Illusion](https://www.dndbeyond.com/sources/dnd/br-2024/spell-descriptions#MinorIllusion): Study contra a CD de magia.

D&D não impõe penalidade numérica universal para toda porta fechada. A escolha
de dificuldade e circunstância exige contexto; os testes reais medem casos
claros, não garantem julgamento idêntico em todas as execuções. Veja a
[bateria focada](../qualidade/dificuldade-live.md).
