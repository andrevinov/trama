# Mapas anteriores de movimento

[Simulador atual](../simulador/README.md) · [Regras](../../docs/sistema/regras/README.md) ·
[Interfaces](../../docs/sistema/interfaces/README.md)

## Objetivo e escopo

Preservar os mapas anteriores como exemplos e bases de regressão para movimento,
portas, visão, conversa, fichas e combate básico. O código reutilizável fica em
`src/trama`; estes arquivos fornecem os dados de cenário.

- [scenario.json](scenario.json): grade original 10×10.
- [cela_guardas.json](cela_guardas.json): Cela, Corredor de 10,5 m e Sala dos
  Guardas, com três guardas; jogador Guerreiro Humano 3/Campeão/Defesa com
  equipamento marcial. As escolhas de ficha estão no JSON.

## Preparação e execução

Python 3.14, Poetry e ambiente gráfico. Conversa real usa `OPENAI_API_KEY` e
opcionalmente `TRAMA_OPENAI_MODEL`. Na raiz:

```bash
poetry install
poetry run python pocs/movimento/run.py --scenario pocs/movimento/cela_guardas.json --debug
poetry run python pocs/movimento/run.py --scenario pocs/movimento/scenario.json
```

O runner antigo abre a dungeon por padrão; especifique o JSON para reproduzir
os mapas anteriores. Aberturas, mensagens e reinícios podem chamar a API paga.

## Exemplos e critérios observáveis

- O jogador começa na Cela, coluna 4/linha 6, com grade aberta e porta fechada.
- `Ando 5 m para a direita.` avança casas inteiras, 4,5 m, e explica o resto.
- `Caminho até a porta e abro.` executa aproximação e interação se nada impedir.
- Ao abrir/fechar a porta, os guardas são revelados/ocultados pela visão.
- `Uso Surto de Ação e ataco o Guarda 1.` pede duas etapas, validadas em ordem.
- Perguntas off não alteram estado; uma falha de narração preserva efeitos.
- As guias de ficha e inimigos consultam os valores do cenário sem gastar recursos.

## Regras, referências e simplificações

O corredor de 10 m solicitado originalmente usa sete casas, 10,5 m, para manter
a grade inteira. A geometria usa metros e diagonais simples. Visão básica humana
não simula propagação de luz. O alcance operacional das portas é uma escolha
da demonstração. O recorte marcial não implementa todas as ações de D&D.

Consulte [movimento](../../docs/sistema/regras/movimento.md),
[ações](../../docs/sistema/regras/acoes.md),
[personagens](../../docs/sistema/regras/personagens.md),
[combate](../../docs/sistema/regras/combate.md) e
[visão](../../docs/sistema/mundo/visao-e-percepcao.md) para os contratos,
referências da edição 2024 e limites. Controles e fichas estão em
[Pygame](../../docs/sistema/interfaces/pygame.md) e
[ficha do personagem](../../docs/sistema/interfaces/ficha-do-personagem.md).

## Testes

```bash
poetry run pytest
poetry check
```

Os testes locais são offline. A suíte anterior de movimento é parcial;
[tests/live/README.md](../../tests/live/README.md) documenta seus casos, limites e
execução autorizada. Sua aprovação não comprova todo o fluxo do simulador.
