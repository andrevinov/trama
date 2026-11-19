# Conselho dos generais

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Objetivo e estado inicial

O cenário permite avaliar manualmente uma conversa com um NPC de personalidade
e memórias definidas. Os dados estão em
[generals_council.json](../../../src/trama/scenarios/generals_council.json), carregados
como `GameSession` comum, sem sessão especializada ou árvore de diálogo.

O jogador representa um general de Auren numa audiência com **Konrad Voss**, general
de Valdren, em um posto fronteiriço neutro. A guerra dura três anos e Valdren ocupa
a Bavária. Uma mesa de mapas separa os interlocutores; ela bloqueia movimento,
mas não visão e pode ser contornada. A porta aberta leva ao vestíbulo. O mapa é
iluminado e cada casa mede 1,5 m.

A reunião começa sob salvo-conduto, sem combate, hostilidade ou custódia.
O general aparece em dourado no mapa, como NPC não hostil.
Não há acordo inicial nem proposta obrigatória para o jogador. Ambos usam o
recorte mecânico existente de Humano/Guerreiro de nível 3, sem armadura ou armas;
“general” é um papel ficcional, não uma classe ou regra nova de D&D.

## Briefing do jogador

Este contexto foi completado em 19/11/2026 para permitir decisões informadas na
audiência. É ficção própria do cenário. A Bavária aqui é o vale descrito abaixo,
sem depender de história ou geografia reais. O texto está na descrição da Sala
do Conselho no JSON: chega à percepção do narrador na abertura e nas consultas
off, além do contexto do Mundo. Não há novo motor de guerra ou de tratados.

### O que é a Bavária

Auren fica a oeste e Valdren, reino montanhoso, a leste. Entre eles está o vale
agrícola da Bavária, ao longo do **rio Linde**. Aldeias, lavouras e moinhos
abastecem as cidades orientais de Auren. A **Ponte de Pedra** permite a passagem
de carroças para o **Passo Cinzento**, ligando Valdren aos mercados da planície.

O **Tratado da Ponte**, firmado há quarenta anos, reconhece a administração civil
e os impostos de Auren, com obrigação de garantir trânsito comercial desarmado
a Valdren. Assim, Auren pretende recuperar o governo do vale; Valdren quer uma
rota segura. A ocupação atual é controle militar, sem soberania reconhecida de
Valdren. Moradores continuam no vale, e há deslocados dos dois lados.

### Por que houve guerra e por que a trégua fracassou

Há três anos, comboios de Valdren sofreram ataques. Auren fechou a rota alegando
combater contrabando e banditismo. Valdren exigiu reabertura e invadiu o vale,
alegando defender o trânsito previsto no tratado. Auren combate a ocupação.
Não foi esclarecido quem ordenou os ataques aos comboios.

Há um ano, uma trégua levou Valdren a recuar para postos de fronteira. Esses
postos foram atacados depois da retirada; a trégua fracassou e Valdren reocupou
o vale. Os mandantes também não foram identificados com segurança. Essa história
explica a exigência de garantias sem determinar culpa ou a resposta à negociação.

### Quem você é e o que sabe

Você comanda a frente oriental de Auren há oito meses. Na última trégua,
comandava a defesa de outra passagem: não negociou aquela retirada e conhece
somente os relatórios inconclusivos sobre os ataques. Seu nome e suas opiniões
continuam à sua escolha; não existe sentimento ou decisão inicial impostos.

Você e Voss já se encontraram em duas trocas de prisioneiros sob salvo-conduto.
Não são amigos e não firmaram acordo pessoal anterior. Ele sabe que você assumiu
depois do fracasso da trégua; a cautela inicial não é uma acusação de autoria.

Na campanha recente, Auren conteve o avanço além do vale, mas Valdren manteve a
Bavária e sofreu baixas. Atacar a ponte exige enfrentar posições fortificadas e
arriscar outro cerco. Não há vitória rápida assegurada para nenhum lado. Outra
campanha ameaça a colheita, os moradores e o comércio. Você não conhece relatórios
reservados, reservas exatas ou planos secretos de Valdren.

### Seu mandato e suas opções

A Coroa de Auren o orienta a buscar trégua verificável, proteção de moradores e
deslocados, reabertura da rota e recuperação da administração civil. Procurar
ao menos trinta dias de pausa e proteção civil é uma orientação recebida, não
um resultado obrigatório ou um desejo atribuído ao personagem.

| Você está autorizado a negociar | Depende de ratificação ou de outra parte |
| --- | --- |
| Trégua de até noventa dias e recuos locais por etapas. | Tratado definitivo: ratificação da Coroa. |
| Troca simultânea de prisioneiros e retorno voluntário de deslocados. | Reconhecer anexação ou ceder soberania: fora do seu mandato. |
| Trânsito comercial desarmado sem pedágio extraordinário durante a trégua. | Tributos permanentes ou reparações do tesouro: fora do seu mandato. |
| Convidar observadores da cidade livre de Meridia. | Participação dos observadores: aceite de Meridia, ainda não concedido. |

Você pode combinar essas possibilidades, formular outra proposta, pedir consulta
ao seu governo, exigir garantias ou sair sem acordo. O mandato é contexto
ficcional, sem validação determinística de competência diplomática: falar algo
fora desses limites não transfere soberania nem obriga sua Coroa.

### O que Voss pode decidir e o que acontece sem acordo

As credenciais dos dois foram lidas antes da audiência. Voss pode pactuar trégua
de até noventa dias, recuos graduais e retorno da administração civil a Auren
sob garantias que julgue suficientes. Alterar permanentemente fronteiras ou
comprometer tributos exige ratificação do conselho de Valdren. Isso é competência,
sem oferta, retirada prometida ou condição que imponha aceitação.

A reunião ocorre no **Posto da Ponte**, pertencente à cidade livre de **Meridia**.
Ela garante a segurança da audiência e a saída dos dois. Não prometeu soldados,
observadores ou suprimentos para um futuro acordo. Não há terceiro participante
presente dentro do mapa.

Sem acordo, o salvo-conduto permanece válido, a ocupação continua e os comandos
voltam aos preparativos de campanha. Novas perdas e atraso na colheita são riscos
ficcionais; não há ofensiva ou passagem de dias executada automaticamente.

Para consultar durante o jogo, use, por exemplo:

```text
[O que é a Bavária e por que cada reino a considera importante?]
[Qual é meu mandato e o que depende da Coroa ou de Meridia?]
[O que meu personagem sabe sobre a última trégua e sobre Voss?]
```

O narrador recebe o briefing conhecido, mas pode resumir a abertura. A apresentação
completa está nesta referência; a formulação exata das respostas continua sujeita
à avaliação manual da IA. Informações novas inventadas pelo jogador são relatos,
sem se tornarem automaticamente fatos do cenário.

## Persona e memórias

Voss é leal e neutro, contido e direto. Seu objetivo central é preservar a
população e a autonomia de Valdren. Nesta audiência procura garantias executáveis
para encerrar a guerra sem repetir uma retirada que exponha seu reino.
Temperamento e objetivos estão no perfil existente, sem campos novos de planejamento.

Seus interesses são população (peso 4), segurança territorial (3), confiabilidade
dos acordos (3) e dever diante do conselho e do salvo-conduto (2). São dados da
[política social existente](../aplicacao/disposicao-social.md), não uma pontuação
nova de negociação. Não há oferta ou frase que determine a resposta.

Seis memórias registram origem/duração da guerra, situação da Bavária, consequências
da última trégua, campanha recente, credenciais públicas e um relato reservado. Voss viu postos destruídos
após a retirada, mas não sabe quem ordenou os ataques; isso não comprova traição
do jogador. Cada lembrança preserva fonte, ocasião e contexto.

Memórias públicas podem ser citadas em `say`; quem ouve aprende um relato com
origem. A memória reservada tem `shareable=false` e sua referência não pode ser
divulgada. Persona e memórias privadas ficam fora do contexto do narrador, conforme
os [contratos de conhecimento](../aplicacao/conhecimento-dos-npcs.md).

## Preparação e comandos

Na raiz, com Poetry instalado e `OPENAI_API_KEY` exportada:

```bash
poetry run trama-simulator --scenario src/trama/scenarios/generals_council.json --debug
```

Sem chave, é possível visualizar o mapa. Abertura, mensagens e reinício com IA
podem fazer chamadas pagas. Os controles são os da
[janela comum](../interfaces/pygame.md), com guias Jogo, Ficha e NPCs.

Cumprimente Voss, pergunte sobre a última trégua ou o custo da guerra, ou proponha
retirada simultânea. São assuntos para experimentar, sem resultado garantido.
Dúvidas de regras ficam entre colchetes.

Reiniciar restaura posições, porta, fichas, recursos e memórias do conselho.
Para voltar à dungeon, feche a janela e execute:

```bash
poetry run trama-simulator
```

Isso reabre a dungeon no início, sem retomar uma partida salva. Os JSONs permanecem
independentes; caminhos explícitos são relativos ao diretório de execução.

## Fluxo e limites

O mesmo `GameFlow` conduz interpretação, decisão do Mundo, execução e narração.
Uma fala dirigida ao general pode receber `say` após `speak`, mesmo sem pergunta
literal ou `parley`. O motor valida ator, memórias e audição antes de registrar
a resposta; o narrador apresenta falas e efeitos efetivamente executados.

Sem `parley`, não há resolução de Influence. Não se cria abordagem fictícia para
negociar. O [estado da conversa](../aplicacao/estado-da-conversa.md) acompanha foco,
pendências, objetivos privados e versões de propostas a partir das falas percebidas.
As [opiniões por opção e por termo](../aplicacao/opinioes-por-opcao.md) avaliam
propostas, alternativas privadas e a expectativa sem acordo, conservando motivos
e origens nos logs. O [acompanhamento](../aplicacao/intencoes-dos-npcs.md) decide
a iniciativa após essas notas na mesma interação, sem exigir abordagem.
As [relações iniciais](../aplicacao/relacoes-iniciais.md) definem confiança -1 e
afeto 0 do general para o jogador: cautela perante o representante adversário
sem atribuir-lhe os ataques da trégua. A pertinência de uma promessa pode alterar
a avaliação; isso não obriga aceitar ou recusar. A
[evolução por episódios percebidos](../aplicacao/evolucao-das-relacoes.md)
usa evidências próprias, sem pontos por quantidade de falas.

Exércitos, territórios e abastecimento são informações fora do mapa. Falar não
movimenta tropas, devolve terras, autentica documentos ou transfere itens.
Os mapas sobre a mesa são decoração estática. Não há soldado ou disparo roteirizado.
A qualidade da argumentação e da resposta continua dependente da IA.

## Critérios de avaliação manual

Abrir a sala, cumprimentar e perguntar sobre a trégua sem iniciar custódia ou combate.
Conferir conhecimento próprio, incerteza sobre os ataques e preservação do relato
reservado. Apresentar proposta nova sem narrar termos como cumpridos ou criar
efeitos físicos. Consultar off sem avançar o Mundo, contornar a mesa, reiniciar e
reabrir a dungeon pelo comando padrão.

Mude de assunto depois de perguntar sobre uma garantia e volte à pergunta.
Altere somente uma condição da proposta e confira em off os termos conhecidos.
Observe se a versão anterior foi preservada e se o general responde a uma versão
que efetivamente ouviu. Encerrar a audiência deve conservar as pendências no registro.

Registrar falhas concretas de interpretação, decisão ou narração para os próximos
incrementos. Uma conversa favorável não comprova repetibilidade. A verificação
offline com respostas fixas cobre composição e efeitos, não o julgamento real do modelo.

Compare uma oferta de retirada unilateral com uma revisão para retirada simultânea.
Nos logs `social.option_evaluated`, confira a versão, a objeção territorial
preservada e o efeito da memória da trégua para cada termo. Repetir a mesma
oferta e as mesmas promessas deve reutilizar a nota sem novo dado. Cogitar
contraproposta não deve registrá-la como fala nem executar seus termos. A resposta do general deve ser escolhida em `npc_agency`, depois do cálculo
na mesma interação, sem repetir a avaliação nem selecionar a maior nota
automaticamente.

Apresente uma solução diferente, ignore uma pergunta e traga um argumento
irrelevante. Confira se a pergunta continua pendente e se o general escolhe
esclarecer, insistir, contestar, contrapropor, ouvir ou encerrar com motivo. Uma
espera silenciosa não deve se repetir indefinidamente. Compare objetivo central
da persona, objetivo da conversa e iniciativa imediata nos logs
`agency.choice_validated`; essas razões privadas não são respostas em off.
Encerrar deve preservar pendências, e uma recusa não deve iniciar combate
automaticamente. A etapa adicional usa o mesmo diretor e configuração do jogo.

Para comparar inimigo confiável e amigo pouco confiável, configure as duas
dimensões independentemente em uma cópia do cenário e carregue-a com `--scenario`.
Promessas podem depender de confiança enquanto benefícios ao destinatário usam
afeto. Confira R e suas fontes nos logs, sem narrar sentimentos do jogador.
Encerrar e iniciar outra conversa conserva os níveis; reiniciar restaura os
valores declarados. Elogiar ou repetir promessas não modifica a relação.

Para avaliar [episódios e memória](../aplicacao/evolucao-das-relacoes.md), proponha
um compromisso local que o motor possa executar, como fechar a porta do Conselho,
e obtenha aceitação explícita com responsável. Execute a ação depois; confira
`relationship.episode_applied` com evidência, autor e níveis antes/depois.
Renarrar o mesmo cumprimento não deve pontuar de novo. Encerre a conversa e abra
outra: o NPC deve poder retomar os compromissos e perguntas que percebeu.
Dez cumprimentos protocolares não equivalem a ajuda com custo; uma acusação
pode gerar suspeita, mas não comprova traição. A correspondência semântica entre
episódio e evidência precisa ser proposta pelo diretor e avaliada manualmente.

Para o passo 7, conte uma notícia pertinente ao abastecimento ou às garantias da
trégua e compare com uma informação alheia aos interesses do encontro. Confira
se a pergunta anterior continua pendente enquanto o general pede confirmação ou
muda a prioridade. O conteúdo ouvido é relato, não prova da notícia. Um incidente
percebido pode levar à suspensão comunicada e posterior retomada da mesma
audiência. Os logs `agency.event_noticed`, `agency.review_requested` e
`agency.review_applied` distinguem percepção, revisão e escolha.

O conselho original continua com dois interlocutores: não há soldado atingido
ou mensageiro surgindo por texto. A conferência offline usa variação autoral com
mensageira para transmitir notícia pela fala real e compara audição normal com
sussurro fora do alcance do general. O
[contrato de acontecimentos](../aplicacao/acontecimentos-e-prioridades.md)
documenta pertinência por âncoras, seleção, percepção e operações disponíveis.
