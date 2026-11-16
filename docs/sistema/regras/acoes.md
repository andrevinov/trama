# Ações, orçamento e portas

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Contratos

Código: [actions.py](../../../src/trama/actions.py).
`ActionBudget` registra ação, ação bônus, reação, interação gratuita e ações
extras. Seus métodos calculam um orçamento atualizado; a aplicação confirma
a alteração ao executar a operação.

A ação normal é consumida antes de uma ação extra. Ações extras de Surto de
Ação não permitem Magia. A ação bônus e a reação têm disponibilidade própria;
uma reação usada retorna no início do próximo turno da criatura. A primeira
interação com objeto é gratuita; as seguintes exigem ação disponível.

Esse orçamento é aplicado aos participantes por
[Encounter](../../../src/trama/application/encounter.py). A exploração narrada não cria
turnos artificiais para renovar interações. Recursos de classe continuam tendo
seus limites próprios; fim de turno não equivale a descanso.

## Abrir e fechar

`operate_door` recebe operação, estado aberto/trancado, alcance, ocupação e
orçamento. Retorna `DoorActionResult(is_open, budget, changed)`.

1. A operação deve ser `open` ou `close`.
2. Se a passagem já está no estado pedido, retorna `already_satisfied`, sem
   cobrar alcance ou recursos.
3. Uma alteração exige alcance; abrir exige passagem destrancada; fechar exige
   espaço desocupado.
4. O custo usa a interação disponível ou uma ação. A aplicação atualiza a
   passagem somente depois da validação.

O alcance e a ocupação são entradas fornecidas pela sessão. No recorte atual,
operar uma passagem exige proximidade de uma casa e caminho visual livre;
essa geometria de interação é uma decisão operacional do simulador.
A [preparação espacial](../aplicacao/movimento-contextual.md) pode
aproximar antes, sem alterar a regra primitiva. Destrancar com chave é operação
separada da [dungeon](../simulador/fuga-da-dungeon.md).

## Referências, limites e verificação

PHB 2024: interação com objetos durante o turno e Utilize. O projeto não
implementa todas as ações do glossário; Preparar e Desengajar continuam sem
execução. A [ficha](../interfaces/ficha-do-personagem.md) distingue
indisponibilidade momentânea de uma ação ainda não implementada.

[Testes unitários](../../../tests/unit) verificam orçamento e portas. As integrações
usam a [sessão](../aplicacao/sessoes-e-conversa.md) para conferir que
estado, custo e relatório foram aplicados. Consulte também
[passagens](../mundo/mapas-e-passagens.md) e [combate](combate.md).
