# Orientações para trabalhar no Trama

## Objetivo e ritmo

O Trama será um sistema de RPG de D&D 5.5e com IA narrando para o jogador como em uma mesa. A construção deve acontecer **aos poucos**, com escopo guiado pelo usuário.

- Implemente apenas o incremento solicitado. Evite antecipar um motor completo de RPG, arquitetura de agentes ou infraestrutura para necessidades futuras.
- Priorize regras, estado do jogo e operações determinísticas antes das integrações com IA.
- Use Python e suas bibliotecas. Gerencie projeto, dependências e comandos com o Poetry instalado na máquina.
- Escreva documentação e explicações em português. Prefira nomes de código consistentes em inglês.

## Código e regras

- Mantenha o código reutilizável em `src/trama/`.
- Separe regras e alterações do estado de entrada/saída, interpretação de linguagem natural e narração quando essas partes forem introduzidas.
- A IA pode propor uma intenção ou ação estruturada; o código determinístico valida a ação e calcula seus efeitos antes da narração.
- Não invente regras de D&D nem misture edições silenciosamente. Registre a referência ou a decisão do usuário ao implementar uma regra; explicite simplificações dos cenários e recortes implementados.
- Prefira soluções pequenas e legíveis. Adicione bibliotecas conforme a necessidade concreta, com `poetry add` ou `poetry add --group dev`.

## Testes

- Use pytest para testar os comportamentos implementados.
- Coloque testes isolados em `tests/unit/` e testes de integração local em `tests/integration/`.
- Mantenha a suíte padrão independente de rede, credenciais e modelos de IA. Use dados fixos e aleatoriedade controlada nos cenários que exigirem resultados reproduzíveis.
- Coloque testes com serviços externos ou modelos reais em `tests/live/` e marque-os com `@pytest.mark.live`. Execute-os explicitamente, seguindo as instruções do cenário.
- Antes de criar, alterar ou executar testes live, leia obrigatoriamente [a política dos live tests](docs/sistema/qualidade/politica-live-tests.md). Siga suas regras de reúso do fluxo, construção de cenários/contextos, critérios independentes e evidências; consulte [a cobertura atual](docs/sistema/qualidade/cobertura-atual.md) para identificar os limites de cada suíte.
- Ao alterar contextos, instruções ou esquemas da IA, siga [os contratos de contexto](docs/sistema/ia/contextos-e-contratos.md) e execute `poetry run python tools/context_contracts.py --check`. Uma mudança intencional exige revisão do diff e justificativa em `--update --reason`; não atualize a referência automaticamente para ocultar uma regressão.
- Não execute chamadas pagas de IA apenas para validar uma alteração local; siga o escopo autorizado para o experimento.
- Nunca versione chaves, tokens ou arquivos com segredos. Documente as variáveis necessárias sem registrar seus valores.
- Execute os testes pertinentes às mudanças e relate o resultado, incluindo verificações que não puderam ser realizadas.

## Simulador, situações e análises

- Evolua o único simulador jogável em `src/trama/simulator.py`, pelo comando `poetry run trama-simulator`. A migração foi concluída; não recrie entradas independentes ou a pasta `pocs/`.
- Documente objetivo, escopo, simplificações, preparação, comandos e critérios na referência correspondente de `docs/sistema/`, preservando a hierarquia existente.
- O cenário jogável e o catálogo de situações ficam em `src/trama/scenarios/`. Situações reproduzíveis usam `load_situation`/`open_situation`, incluindo preparação e reinício. Leia [o formato e seus limites](docs/sistema/simulador/carregamento-de-cenarios.md#situações-reproduzíveis).
- Os mapas anteriores ficam em `tests/fixtures/scenarios/`; frases, escolhas, limites e expectativas de avaliação ficam nas fixtures pertinentes, sem cópia do motor ou do contexto da IA.
- Testes de fluxo completo usam a composição e `game.runner`; a janela recebe o mesmo `GameFlow`. Não introduza coordenação alternativa em testes ou ferramentas.
- Análises parciais reutilizam código importável em `src/trama/analysis/` e ferramentas de diagnóstico em `tools/`, com escopo explicitamente identificado. Elas não são novos simuladores nem comprovam o fluxo completo.
- Converta os comportamentos aprovados em testes de regressão. Preserve os cenários com IA real como testes live quando fizer sentido.
- Não trate resultados de uma chamada real de IA como garantia determinística. Defina critérios de avaliação claros para o comportamento observado.
- Preserve as evidências datadas e seus caminhos/hashes originais. Novas observações recebem registros próprios; não atualize inventários históricos para ocultar divergências. Veja [o procedimento de preservação](docs/evidencias/2026-11-16-preservacao-das-analises/relatorio.md).

## Comandos e documentação

- Instalar o ambiente: `poetry install`.
- Executar o simulador oficial: `poetry run trama-simulator`, opcionalmente com `--debug`. O padrão é a dungeon do pacote; `--scenario CAMINHO` e `--situation ID` são seleções alternativas.
- Rodar testes locais: `poetry run pytest`.
- Rodar testes live: `poetry run pytest tests/live -m live`, com o ambiente exigido pelo cenário.
- Verificar os metadados: `poetry check`.
- Conferir contratos de IA sem rede: `poetry run python tools/context_contracts.py --check`.
- Conferir evidências históricas: `poetry run python tools/check_evidence.py`; `--require-local` exige também todos os logs inventariados.
- Atualize o README quando a estrutura ou as instruções de uso mudarem. Siga [a política de documentação](docs/sistema/qualidade/documentacao.md): tier 1 para visão geral, tier 2 para módulos e tier 3 para contratos e detalhes; mantenha roadmaps e evidências nos arquivos próprios.
- Não crie funcionalidades ou documentos vazios apenas para preencher pastas; descreva as capacidades e os limites efetivamente implementados.
