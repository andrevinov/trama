# Situações de amizade e romance

Tier 3 · [Simulador](README.md) · [Política dos vínculos](../aplicacao/vinculos-afetivos.md)

As situações usam `bonds_encounter.json`, o catálogo e a mesma composição,
`GameFlow`, janela e runner do simulador oficial. Marina e o jogador são adultos
declarados; há um pátio e uma varanda. Marina tem ficha mecânica mínima de nível
1, sem armas e não hostil, para usar as operações existentes. É simplificação
do cenário, sem novo bloco oficial de D&D.

## Preparação e comandos

Com Poetry e os serviços configurados conforme a [execução](execucao.md):

```bash
poetry run trama-simulator --situation vinculo-amizade-sem-atracao --debug
poetry run trama-simulator --situation vinculo-em-formacao --debug
poetry run trama-simulator --situation vinculo-afeto-sem-confianca --debug
poetry run trama-simulator --situation vinculo-interesse-nao-correspondido --debug
```

A preparação executa somente “Olá, Marina.” dirigido à interlocutora. Não escolhe
resposta, tema, sentimento ou recusa do jogador. Reiniciar restaura posições,
memórias, vínculos e cumprimento. As situações não fornecem dados para testes
de combate ou outras operações fora desse recorte.

| Situação | Base e avaliação proposta |
| --- | --- |
| `vinculo-amizade-sem-atracao` | Amizade apoiada em dois cuidados anteriores, confiança 2/afeto 3, sem atração. Marina já declarou que prefere amizade. Avaliar acolhimento e recusa franca sem conversão em romance. |
| `vinculo-em-formacao` | Mesma história de cuidado, sem vínculo qualitativo inicial nem limite prévio. Avaliar formação explicitamente justificada; notas altas e cumprimento isolado não bastam. |
| `vinculo-afeto-sem-confianca` | Confiança −2/afeto 4, amizade e amor ativos, paixão encerrada após quebra de promessa conhecida. Avaliar cuidado acompanhado de cautela e garantias, preservando a história. |
| `vinculo-interesse-nao-correspondido` | Amizade e atração próprias de Marina, sem escolha amorosa atribuída ao jogador. Para avaliar interesse não correspondido, o usuário pode dizer “Eu não quero romance com você.”; só depois de ouvida existe essa recusa no estado. |

`--scenario src/trama/scenarios/bonds_encounter.json` também abre o mapa-base,
sem variação ou cumprimento do catálogo. Não há comando de somar pontos ou
controle de sentimentos na interface do jogador.

## Critérios e limites

Compare amizade sem aproximação amorosa, amor com confiança reduzida e recusa
respeitada sem apagamento automático da afeição. Uma declaração posterior de
abertura permite reconsideração, sem obrigar aceitação ou reciprocidade. Confira
o que foi realmente dito, quem ouviu e qual resposta foi executada. Somente a
perspectiva de cada NPC deve orientar seu comportamento.

O vínculo pode mudar atenção, cuidado e forma de recusar; não cria transferência
de bens, cura, companhia obrigatória ou bônus novo. Não há transformação de
alinhamento, relógio de relações ou progressão automática entre estágios.

Os testes locais compartilham dados/preparação e usam escolhas fixas para
verificar execução, privacidade, limites, off e reinício. A auditoria de contextos
observa as projeções da aplicação. Isso não mede a qualidade da conversa real:
a avaliação manual deve registrar incoerências, classificações equivocadas e
limites respeitados ou ignorados, preservando as evidências da execução.
