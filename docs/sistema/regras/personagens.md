# Personagens, traços e recursos

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Ficha e estado

Código: [characters.py](../../../src/trama/characters.py).
`FighterSheet` descreve atributos, escolhas, treinamento, armas e maestrias;
`FighterState` contém PV e recursos consumíveis. A ficha deriva modificadores,
proficiência, perícias, salvaguardas, PV máximos e CA. `sheet_from_data` lê as
escolhas declaradas no cenário; `new_fighter` cria o estado inicial desse recorte.

O suporte atual é Humano Médio, Guerreiro 1–3, Campeão no nível 3, estilo Defesa,
origem Soldado e as escolhas suportadas de perícias/talentos. Não é um criador
geral de personagens. Equipamento vem dos dados: o Guerreiro da dungeon começa
sem armadura ou armas, enquanto o mapa legado tem equipamento marcial.
Defesa só acrescenta CA com armadura; roupa de limpeza não é armadura.

## Traços e recursos implementados

| Traço/recurso | Regra implementada |
| --- | --- |
| Humano: Resourceful | Recebe Inspiração Heroica após descanso longo; não acumula duas |
| Humano: Skillful / Versatile | Uma perícia adicional e o talento de origem escolhido |
| Defesa | +1 CA com armadura; não se aplica sem armadura |
| Retomar o Fôlego | Ação bônus, cura 1d10 + nível; 2 usos; descanso curto recupera 1 e longo recupera todos |
| Maestria em Armas | Três escolhas; pode trocar uma após descanso longo |
| Surto de Ação (2) | Uma ação adicional, exceto Magia; um uso por descanso curto/longo |
| Mente Tática (2) | +1d10 a teste de atributo falho; consome Retomar o Fôlego só se converter em sucesso |
| Crítico Aprimorado (3) | Armas e ataques desarmados têm crítico com 19–20 natural |
| Atleta Notável (3) | Vantagem em iniciativa e Força (Atletismo); movimento imediato de até metade da velocidade após crítico, sem ataques de oportunidade |
| Savage Attacker | Uma vez por turno, duas rolagens dos dados de dano da arma; o recorte atual escolhe automaticamente a maior |


## Uso e recuperação

`second_wind`, `action_surge`, `tactical_mind` e as funções de inspiração
produzem estados atualizados. A [aplicação](../aplicacao/README.md)
verifica momento e orçamento de uso. Retomar o Fôlego custa ação bônus; Surto
concede uma ação extra, sem recuperar movimento gasto.

`finish_short_rest` e `finish_long_rest` calculam efeitos de um descanso já
validado. O chamador precisa verificar duração, interrupções e elegibilidade.
Há API para Dados de Vida e troca de maestria, sem comandos gerais na conversa.
Um descanso longo recupera os Dados de Vida no recorte da edição 2024; não
repõe automaticamente armas gastas. Inspiração não acumula dois usos.

`ability_check` resolve o teste com a ficha e a fonte de dados injetada.
As APIs de inspiração permitem rerrolagens; o comando atual de ataque tem
uma autorização específica descrita em [combate](combate.md), sem seletor
geral de qualquer dado depois de ver o resultado.

## Referências e verificação

PHB 2024: Fighter Traits/Features (pp. 91–92), Champion (p. 96), Soldier
(p. 185), Human (p. 194), talentos Skilled, Savage Attacker e Defense e
maestrias do capítulo Equipment. As escolhas particulares do jogador e dos
NPCs ficam no [cenário](../simulador/fuga-da-dungeon.md).

As regressões em [tests/unit](../../../tests/unit) verificam recursos e valores
calculados. A apresentação e a consulta de disponibilidade são projeções em
[sheets.py](../../../src/trama/application/sheets.py) e
[sheet_options.py](../../../src/trama/application/sheet_options.py), descritas na
[ficha visual](../interfaces/ficha-do-personagem.md).
