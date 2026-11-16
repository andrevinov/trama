# Iniciativa, turnos e ataques

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Combate por turnos: alcance deste incremento

Ver guardas não inicia combate automaticamente. A intenção de ataque ou uma
resposta justificada do Mundo inicia conflito e rola iniciativa antes dos golpes.
Se o jogador ganha, o ataque pedido é resolvido; se um guarda ganha, o jogador
aguarda os turnos dos NPCs antes de escolher sua ação. Não há ataque gratuito
antes da iniciativa. Campeão tem vantagem; guardas idênticos rolam em grupo.
Desempates são uma decisão do cenário: jogador primeiro, guardas na ordem do JSON.

`Encerro meu turno` avança a vez do jogador. Cada turno de NPC é consultado à IA,
executado e encerrado automaticamente. Recursos de turno retornam no início do
turno correspondente; usos da classe e Inspiração não são recuperados por isso.
Uma decisão de trégua/fim do conflito retorna ao narrado, preservando PV e usos.
Não há relógio contínuo de exploração nem turnos artificiais fora de conflito.
Veja [o contrato de modos, respostas e pontos de interrupção](../aplicacao/fluxo-do-jogo.md).

Para exercitar os recursos, o recorte inclui **um ataque corpo a corpo por ação**
contra um participante visível e adjacente (1,5 m), sem obstáculo no alcance.
A IA envia somente intenção, alvo e arma. O Python usa FOR + proficiência,
rola o d20, compara com CA, resolve 1/20 naturais, crítico e dano. Críticos dobram
os dados, sem dobrar o modificador. O jogador ainda não tem Ataque Extra, que
chega no nível 5; Surto de Ação permite uma segunda ação de Ataque ou Dash.

Graze causa apenas o modificador de atributo quando o ataque erra. Sap impõe
desvantagem no próximo ataque do alvo até o início do próximo turno da fonte.
Slow reduz velocidade em 3 m sem acumular, até o início do próximo turno da
fonte. O movimento de Atleta Notável tem saldo separado, consumido primeiro;
termina ao realizar outra operação ou encerrar o turno. O relatório identifica
quanto movimento ficou protegido. Esse trecho protegido não provoca ataques
de oportunidade. O movimento normal pode provocá-los ao sair do alcance de um
adversário que vê a criatura; entrar ou circular dentro do alcance não provoca.
Um ataque de oportunidade usa reação, sem consumir a ação normal. O Jogador
confirma ou recusa no painel de turno; os guardas reagem automaticamente neste
cenário. A reação volta no início do turno do seu dono. Veja
[detalhes e simplificações](reacoes.md).

Exemplos após abrir a porta e se aproximar de um guarda:

```text
Ataque o Guarda 1 com o mangual.
Use Surto de Ação e ataque o Guarda 1 com a espada grande.
Use Retomar o Fôlego.
Encerre o turno.
```

Inspiração Heroica tem API para rerrolar **qualquer dado**, mantendo o novo
resultado mesmo pior. No prompt de ataque, `use_inspiration` autoriza rerrolar
obrigatoriamente o d20 imediatamente após a rolagem original, antes do dano.
Escolhas interativas após ver os dados, condições como “só se errar” e rerrolagens
de outros dados por prompt ainda pedem esclarecimento.

Descansos, Dados de Vida, testes de atributo, Mente Tática e troca de maestria
têm funções puras em `characters.py`, testadas sem IA. Ainda não há comandos
para eles na janela. A aplicação que chamar os efeitos de descanso deve antes
validar duração, interrupções e elegibilidade; não há avanço instantâneo de tempo
por prompt. Um descanso longo válido recupera todos os Dados de Vida na edição
2024; não cria novas azagaias.

A 0 PV, a criatura fica **fora de combate** e não age. Seu turno é pulado.
No mapa, seu marcador fica escuro, com um pequeno **X** no canto e o número
preservado para identificação. Continua sujeito ao campo de visão.
Quando o ataque deixa todos os inimigos com 0 PV, o combate termina automaticamente.
A IA não declara morte: testes de morte, inconsciência e a opção de deixar uma
criatura inconsciente ainda não têm resolução completa. A sessão genérica conserva ocupação mesmo a 0 PV. A dungeon tem a política
específica de atravessar corpos como terreno difícil, sem terminar neles; veja
[criaturas](../mundo/criaturas.md). Ataques à distância, cobertura completa,
ações de combate adicionais e condições ficam para os próximos incrementos.

Código: [combat.py](../../../src/trama/combat.py) e [encounter.py](../../../src/trama/application/encounter.py). Referências: PHB 2024, combate/iniciativa, Fighter e Champion; detalhes de recursos em [personagens](personagens.md), e gatilhos em [reações](reacoes.md). As regressões estão em [tests/unit](../../../tests/unit) e [tests/integration](../../../tests/integration).
