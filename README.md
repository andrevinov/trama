# Trama

O Trama é uma engine em desenvolvimento para jogar **D&D 5.5e, edição 2024,
por meio de uma conversa com IA**. O usuário controla seu personagem; o sistema
representa o Mundo, resolve as regras e narra o retorno às escolhas do jogador.
O projeto usa Python e Poetry, com uma interface visual em Pygame.

Tarefas incertas usam [avaliação contextual de dificuldade](docs/sistema/aplicacao/avaliacao-de-dificuldade.md), preservando CDs fixadas pelas regras.
NPCs possuem [memórias e disposição social](docs/sistema/aplicacao/disposicao-social.md)
por pedido. Alinhamento, interesses e informação relevante orientam se aceitam,
recusam ou exigem teste; aceitar ouvir preserva os limites da custódia.
Interlocutores também têm [intenções acompanhadas em exploração](docs/sistema/aplicacao/intencoes-dos-npcs.md): conversas paralelas podem levá-los a cobrar uma resposta ou tomar outra iniciativa.

Este é o documento de **tier 1**: apresenta o sistema, suas partes, suas relações
e o alcance atual. A documentação segue do geral para o específico:

- **Tier 1 — Sistema:** esta visão geral e os caminhos de leitura.
- **Tier 2 — Módulo ou área:** responsabilidade, submódulos e relações.
- **Tier 3 — Assunto específico:** funcionamento, contratos, regras, exemplos
  e referências ao código e aos testes.

Os oito índices de tier 2 estão em `docs/sistema/` e são acessíveis pelos
[caminhos de leitura](#caminhos-para-aprofundar). Cada um apresenta suas partes,
relações e referências ao código. O tier 3 reúne documentos específicos
nessas mesmas pastas, com contratos, exemplos, referências e verificações.

## A experiência de jogo

A partida começa com uma descrição de onde o personagem está, de seu estado e
do que percebe. O jogador escreve o que deseja fazer; o sistema interpreta o
pedido, resolve suas consequências e descreve a nova situação. O mapa acompanha
as posições e os demais estados calculados pela aplicação.

Há dois participantes conceituais nessa troca:

- **Jogador:** suas decisões vêm do usuário. A interpretação deve preservar
  sua intenção e as restrições que ele declarou.
- **Mundo:** reúne lugares, objetos, NPCs, condições e acontecimentos. Suas
  respostas combinam decisões narrativas da IA, operações validadas pelo motor
  e comportamentos específicos do cenário.

A narração apresenta os fatos produzidos. Descrever uma caminhada, um ataque ou
uma descoberta depende de sua execução real. A interface consulta esse mesmo
estado para desenhar o jogo. Se a narração falhar depois de uma ação, os efeitos
já aplicados permanecem.

### Conversa em on e off

O canal **on** contém ações, falas e descrições dentro do jogo. O canal **off**
trata de regras, dúvidas e explicações, marcado por colchetes. Uma mensagem pode
conter os dois:

```text
Vou até a grade da cela e tento abri-la.
[Como funciona a interação com uma porta?]
```

Perguntas exclusivamente off recebem uma resposta sem executar ações ou avançar
turnos. Em mensagens mistas, a parte on pode produzir efeitos e a parte off é
respondida junto do resultado.

### Modos narrado e por turnos

No **modo narrado**, a exploração acontece sem orçamento artificial de movimento
por turno. Alcance, obstáculos, ocupação e recursos continuam sendo validados.

No **modo por turnos**, um conflito inicia iniciativa e passa a organizar
movimento, ações, ações bônus e reações. O sistema resolve os turnos dos NPCs e
as escolhas de reação pertinentes. Um mostrador de iniciativa apresenta a ordem,
a vez atual, os recursos restantes e as decisões pendentes durante o combate. Passar a vez é uma intenção expressa pela
conversa, inclusive ao dizer que não fará mais nada naquele turno.

Esses modos fazem parte do fluxo do jogo. Seus detalhes e pontos de interrupção
estão em [Jogador, Mundo e modos](docs/sistema/aplicacao/fluxo-do-jogo.md#modos).

## Como uma intenção se torna um resultado

Uma mensagem com ação percorre, em linhas gerais, este caminho:

1. A aplicação separa on/off e constrói o contexto a partir da partida atual.
2. O **interpretador de IA** propõe um plano estruturado para a intenção do
   jogador. A aplicação valida sua estrutura, referências e origens declaradas.
3. O **diretor do Mundo** propõe as respostas pertinentes. Uma ação do jogador
   pode acontecer sem exigir uma ação de resposta do Mundo.
4. A aplicação coordena a execução. O código determinístico valida as regras,
   calcula efeitos, atualiza o estado e registra o progresso e os impedimentos.
   Turnos de NPCs acrescentam suas próprias decisões e resoluções quando cabíveis.
5. O **narrador de IA** recebe os fatos executados e a percepção atual para
   descrever o retorno do Mundo e responder em off.
6. A interface apresenta a conversa e as projeções atualizadas do jogo.

A abertura e as perguntas exclusivamente off seguem caminhos mais curtos.
Quando uma reação exige escolha do jogador, o fluxo pode pausar e continuar
depois dela. A coordenação é compartilhada pela janela e pela execução sem janela.

### Movimento contextual e progresso parcial

Pedir uma ação pode autorizar a aproximação necessária para realizá-la. Por
exemplo, ao investigar uma cela, o sistema pode entrar nela antes da busca; ao
atacar um alvo, pode aproximar-se até o alcance permitido. A ação publica seu
requisito espacial, e a aplicação usa o movimento já existente para satisfazê-lo.

Essa preparação respeita restrições como “sem sair do lugar”, as barreiras do
mapa e o movimento disponível em combate. Ela pode provocar reações e ser
interrompida. A aplicação preserva o percurso realizado e explica o que faltou;
não acrescenta gastos de poderes ou abertura de barreiras intermediárias por
conta própria. Num ataque que inicia combate, a iniciativa precede a aproximação.

Planos com várias ações são executados na ordem. A execução para no primeiro
impedimento e preserva o que já ocorreu. A narração deve descrever o progresso em
on e explicar a interrupção em off. Veja o
[funcionamento do movimento contextual](docs/sistema/aplicacao/movimento-contextual.md#movimento-contextual-e-requisitos-espaciais).

## Partes do sistema e suas relações

As responsabilidades abaixo organizam a leitura do projeto. Regras, estado,
coordenação, interpretação e apresentação têm funções distintas, conectadas por
contratos e operações explícitos.

| Parte | Responsabilidade | Relação com as demais |
| --- | --- | --- |
| **Regras** | Calcular movimento, orçamento de ações, rolagens, recursos de personagens, ataques e reações implementados. | A aplicação usa esses cálculos para validar operações e aplicar seus efeitos. As regras básicas não dependem de Pygame ou OpenAI. |
| **Mundo** | Representar grade, lugares, passagens, objetos, criaturas posicionadas e visibilidade. | Fornece geometria e percepção para movimento, execução, contextos e desenho. Representar uma criatura não decide seu comportamento. |
| **Aplicação** | Manter a sessão e a conversa; coordenar planos, execução, modos, NPCs, reações e resultados. | Combina regras e estado, constrói contextos e usa contratos para solicitar os serviços de IA. É o fluxo comum às entradas do sistema. |
| **IA** | Interpretar o jogador, propor decisões do Mundo e narrar os resultados, em papéis separados. | Recebe projeções da aplicação e devolve respostas estruturadas. Os adaptadores de infraestrutura concentram a comunicação com o provedor. |
| **Interfaces** | Receber mensagens e escolhas e apresentar mapa, conversa e fichas. | A janela agenda os pedidos do fluxo e exibe suas projeções. A entrada sem janela conduz o mesmo fluxo para outros consumidores, incluindo testes. |
| **Simulador** | Compor uma partida jogável e exercitar a engine com um cenário concreto. | Reutiliza carregamento, regras, serviços, fluxo e interface; acrescenta os dados e a adjudicação específica da aventura. |
| **Observabilidade** | Registrar eventos, erros, decisões observáveis e seus identificadores de correlação. | Permite acompanhar operações e chamadas de IA entre módulos. As ferramentas de análise consomem os logs. |
| **Qualidade** | Verificar regras, integração, contratos e comportamentos com ou sem serviços reais. | Usa entradas e operações da aplicação, com critérios independentes para avaliar os resultados. É uma área transversal de desenvolvimento. |

Por exemplo, um ataque com aproximação cruza várias dessas partes: a IA
identifica a intenção, a aplicação coordena a iniciativa e a caminhada, o mapa
fornece obstáculos, as regras resolvem alcance e dano, e o narrador descreve os
efeitos. A interface desenha a posição resultante; os logs permitem investigar
esse percurso.

O estado completo do Mundo e o conhecimento do jogador são informações
distintas. A aplicação constrói contextos próprios para interpretação, decisão
do Mundo e narração. O narrador pode conhecer segredos para manter a coerência,
mas deve respeitar os limites de percepção ao descrevê-los. A avaliação dos
textos continua necessária para verificar esse comportamento.

As referências de regras da edição 2024, as decisões do usuário e as
simplificações dos cenários devem permanecer identificadas nos documentos
específicos. Uma decisão da dungeon, como a rotina de um guarda, vale para
aquele cenário; sua presença não constitui uma regra geral do motor.

### Caminhos para aprofundar

Comece pelo índice da área para entender suas responsabilidades e suas relações.
Cada índice conduz às partes do código e às referências de funcionamento, onde
ficam APIs, campos, configurações e procedimentos detalhados.

| Índice de tier 2 | O que apresenta |
| --- | --- |
| [Regras](docs/sistema/regras/README.md) | Movimento, ações, personagens, combate, reações e dados. |
| [Mundo](docs/sistema/mundo/README.md) | Mapas, passagens, objetos, criaturas e percepção. |
| [Aplicação](docs/sistema/aplicacao/README.md) | Sessão, conversa, planos, coordenação, movimento contextual e execução do Mundo. |
| [IA](docs/sistema/ia/README.md) | Interpretação, decisão, narração, contextos e integração com o provedor. |
| [Interfaces](docs/sistema/interfaces/README.md) | Janela Pygame, consulta de fichas e execução sem janela. |
| [Simulador](docs/sistema/simulador/README.md) | Composição jogável, carregamento e adjudicação do cenário de fuga. |
| [Observabilidade](docs/sistema/observabilidade/README.md) | Eventos, correlação, diagnóstico e análise dos logs. |
| [Qualidade](docs/sistema/qualidade/README.md) | Testes locais/live, preparação, contratos, cobertura e evidências. |

## Estado atual e alcance

O cenário jogável atual é uma **fuga de dungeon**, com quatro celas, corredor
iluminado por tochas, um guarda, banheiro, saída e outro prisioneiro. O jogador
é um Guerreiro Humano de nível 3, Campeão, com estilo Defesa, inicialmente em
trapos e sem itens. A abertura mágica de sua cela dá início à história.

O simulador exercita exploração, descoberta e coleta de itens, portas e chaves,
disfarce, furtividade, interação com o prisioneiro e combate básico. A
[conversa antes do combate](docs/sistema/aplicacao/conversa-antes-do-combate.md) é
uma capacidade geral: abordagens preservam a distância e permitem resposta social
antes da iniciativa. Há mapa,
campo de visão e consulta de fichas, com **metros como unidade padrão** e casas
de 1,5 m. O comportamento específico da dungeon inclui testes e respostas
determinísticas na exploração; as decisões de combate do guarda passam pela IA.

A [percepção dos NPCs](docs/sistema/mundo/visao-e-percepcao.md) também é uma
capacidade geral: sentidos e alcances próprios, visão/ruídos, percepção passiva,
Hide, busca deliberada e despertar. O prisioneiro tem perfil sensorial sem ficha
de Guerreiro. As respostas narrativas continuam cabendo ao Mundo/cenário.

O [conhecimento dos personagens](docs/sistema/aplicacao/conhecimento-dos-npcs.md)
usa memórias com origem, ocasião e entidades relacionadas. Observações e relatos
permanecem distintos da verdade atual; somente memórias relevantes entram no
contexto da IA. A informação da chave do prisioneiro vem desses dados do NPC.

O recorte de personagens cobre Humano, Guerreiro dos níveis 1 a 3 e Campeão.
Inventário, magia e interações sociais atendem somente aos casos implementados.
Algumas regras têm API determinística, mas ainda não têm comando na conversa.
Outras ações de D&D, condições, testes de morte e um sistema geral de magias
ainda não têm resolução completa. As limitações estão nos
[documentos do cenário](docs/sistema/simulador/fuga-da-dungeon.md#simplificações-deliberadas) e das
[regras exercitadas](docs/sistema/regras/movimento.md#referências-e-limites).

Os [mapas anteriores](tests/fixtures/scenarios/README.md) continuam disponíveis
como fixtures de regressão, carregáveis pelo mesmo simulador com `--scenario`.
O cenário de fuga é uma aplicação concreta do motor; o objetivo do Trama é
ampliar gradualmente as capacidades reutilizáveis para outras aventuras.

## Preparação e execução

Use Python 3.14 e Poetry. Na raiz do repositório:

```bash
poetry install
poetry run trama-simulator
```

O comando é instalado pelo Poetry. O cenário padrão acompanha o pacote e não
depende de arquivos externos ao pacote. O executável instalado também pode ser
usado fora da raiz; caminhos fornecidos em `--scenario` e `--log-file` são
relativos ao diretório de onde ele é chamado. Os detalhes estão em
[execução do simulador](docs/sistema/simulador/execucao.md).

A conversa utiliza o SDK oficial da OpenAI e a Responses API, autenticados por
`OPENAI_API_KEY` exportada no ambiente. `TRAMA_OPENAI_MODEL` permite escolher o
modelo. Os padrões e a precedência estão na
[configuração dos serviços](docs/sistema/ia/integracao-openai.md#configuração-e-precedência).
Sem chave, a janela permite visualizar o cenário e informa a configuração
necessária. O uso interativo do Pygame requer um ambiente gráfico.

**Enter** envia a mensagem; **Shift+Enter** insere uma nova linha. As guias
**Jogo**, **Ficha** e **Inimigos** permitem consultar o estado durante a partida.
Consulte os [controles](docs/sistema/interfaces/pygame.md#controles) e os
[exemplos da dungeon](docs/sistema/simulador/fuga-da-dungeon.md#interações) para continuar.

### Logs

Para acompanhar também os pedidos completos enviados à IA e as respostas:

```bash
poetry run trama-simulator --debug
```

O simulador registra eventos estruturados em `logs/trama.jsonl`. O formato
comum preserva dados específicos dos módulos e relaciona mensagens, operações
e chamadas à IA. O modo normal inclui conversa, resultados, erros e consumo
informado; debug acrescenta prompts e detalhes técnicos. Veja
[como investigar](docs/sistema/observabilidade/logs.md) e [como usar o lnav](docs/sistema/observabilidade/investigacao-com-lnav.md).

## Testes e confiança nos resultados

A suíte padrão é local, independente de rede, credenciais ou modelos de IA:

```bash
poetry run pytest
poetry check
```

Testes unitários verificam componentes isolados; testes de integração exercitam
componentes reais em conjunto, com transporte simulado quando necessário.
Os contratos de contexto também têm verificação offline para tornar visíveis
mudanças nos dados, nas instruções e nos esquemas enviados à IA. Consulte
[os contratos e seu procedimento de revisão](docs/sistema/ia/contextos-e-contratos.md).

Os **live tests** usam serviços reais e são executados explicitamente. Antes
de criar, alterar ou executar um caso, leia a
[política obrigatória](docs/sistema/qualidade/politica-live-tests.md) e as
[instruções da suíte](tests/live/README.md). Aberturas, mensagens, reinícios e
turnos de NPCs também podem fazer chamadas pagas durante o uso do simulador.

As [análises parciais de interpretação](docs/sistema/qualidade/analise-de-interpretacao.md)
usam um módulo importável e fixtures compartilhadas, sem dependência de scripts
de POCs. A ferramenta `tools/analyze_interpretation.py` oferece uma prévia offline;
seus resultados são identificados como contrato parcial do interpretador.

Os [13 casos de percepção](docs/sistema/qualidade/percepcao-live.md) usam salas
genéricas e perfis sensoriais configuráveis pelo mesmo carregador e runner.
Suas preparações e critérios foram validados offline; não há execução paga
afirmada por sua criação.
Os [dois casos de conclusão de NPCs](docs/sistema/qualidade/turnos-npc-live.md)
avaliam aproximação, ataque ao alcançar e devolução do turno, com execução
focada e [evidências datadas](docs/evidencias/2026-11-16-conclusao-turnos-npc/relatorio.md).
Os [quatro casos de conversa](docs/sistema/qualidade/conversa-live.md) cobrem
abordagem distante, sucesso/falha de Persuasão e ataque escolhido pelo jogador.
Foram preparados e validados offline; sua criação não executa chamadas pagas.
Os oito casos de movimento contextual usam o carregamento, os contextos, os
adaptadores e o fluxo compartilhados com o simulador. As demais suítes live
mantêm os limites parciais ou experimentais descritos na documentação. A
preparação dessas situações agora faz parte da aplicação e pode ser aberta na
janela, com os mesmos dados dos testes:

```bash
poetry run trama-simulator --situation investigar-cela-do-log --debug
```

O [catálogo de situações](docs/sistema/simulador/carregamento-de-cenarios.md#situações-reproduzíveis)
declara operações, dados e pré-condições. Mensagens avaliadas, limites e critérios
independentes continuam nos testes. Reiniciar refaz a situação selecionada.

Compartilhar o fluxo aproxima o teste da experiência real. Critérios
independentes verificam se os efeitos esperados aconteceram, e a revisão dos
textos avalia aspectos que as asserções mecânicas não certificam. Uma execução
aprovada constitui evidência sobre aquela amostra; a variação dos modelos ainda
exige avaliação. O [relatório do experimento contextual](docs/evidencias/2026-11-16-movimento-contextual/relatorio.md)
registra resultados, configuração e ressalvas de narração.

## Estrutura do repositório

| Local | Conteúdo |
| --- | --- |
| `src/trama/` | Regras e representação do mundo; aplicação, adaptadores de infraestrutura, interface e composição. |
| `src/trama/scenarios/` | Cenários distribuídos com o pacote; a dungeon é o padrão do comando oficial. |
| `src/trama/analysis/` | Diagnóstico parcial da interpretação, usando carregadores, serviços e contratos da aplicação. |
| `tests/unit/` | Verificações isoladas. |
| `tests/integration/` | Integração local e regressões sem serviços externos. |
| `tests/live/` | Avaliações explícitas com serviços externos e modelos reais. |
| `tests/fixtures/` | Dados e situações compartilhados entre testes. |
| `docs/sistema/` | Índices de tier 2 e referências específicas de tier 3 de cada área. |
| `docs/roadmaps/` | Planos por estado e arquivo datado de implementações. |
| `docs/evidencias/` | Relatórios e manifestos datados de experimentos. |
| `docs/contracts/` | Referências técnicas revisadas dos contratos de contexto. |
| `tools/` | Ferramentas auxiliares, como verificação de contratos e análise com lnav. |
| `logs/` | Evidências locais de execução, ignoradas pelo Git. |

## Como vamos construir e documentar

O desenvolvimento acontece em incrementos orientados pelo usuário. Cada avanço
deve preservar a separação de responsabilidades e transformar os comportamentos
validados em regressões pertinentes. Regras e estado são implementados de forma
determinística; a integração com IA usa essas capacidades para interpretar,
decidir e narrar.

Na hierarquia documental, cada assunto tem uma referência canônica. Os tiers
superiores apresentam conceitos e relações e apontam para os detalhes. Mudanças
locais de comportamento atualizam a referência específica; mudanças de
responsabilidade também precisam alcançar a visão do módulo e, quando cabível,
esta visão geral.

Roadmaps descrevem trabalho a realizar e seu acompanhamento. Relatórios de
experimentos registram o que foi observado numa execução. O funcionamento atual
deve ser explicado pelos documentos do sistema. Os
[roadmaps](docs/roadmaps/README.md) ficam separados por estado:
não implementados, em implementação e implementados em arquivo datado.
[Evidências](docs/evidencias/README.md) preservam os resultados dos experimentos.

As análises históricas têm um inventário de preservação, separado dos contratos
atuais. `poetry run python tools/check_evidence.py` confere os documentos e logs
disponíveis; `--require-local` exige também todos os arquivos locais registrados.
Essa verificação de integridade não executa IA nem avalia o comportamento atual.
As [convenções de manutenção](docs/sistema/qualidade/documentacao.md) descrevem
como acrescentar assuntos e manter a navegação entre os três tiers.

Orientações de contribuição e trabalho no repositório estão
em [AGENTS.md](AGENTS.md).
