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
- Não invente regras de D&D nem misture edições silenciosamente. Registre a referência ou a decisão do usuário ao implementar uma regra; explicite simplificações das provas de conceito.
- Prefira soluções pequenas e legíveis. Adicione bibliotecas conforme a necessidade concreta, com `poetry add` ou `poetry add --group dev`.

## Testes

- Use pytest para testar os comportamentos implementados.
- Coloque testes isolados em `tests/unit/` e testes de integração local em `tests/integration/`.
- Mantenha a suíte padrão independente de rede, credenciais e modelos de IA. Use dados fixos e aleatoriedade controlada nos cenários que exigirem resultados reproduzíveis.
- Coloque testes com serviços externos ou modelos reais em `tests/live/` e marque-os com `@pytest.mark.live`. Execute-os explicitamente, seguindo as instruções do cenário.
- Não execute chamadas pagas de IA apenas para validar uma alteração local; siga o escopo autorizado para o experimento.
- Nunca versione chaves, tokens ou arquivos com segredos. Documente as variáveis necessárias sem registrar seus valores.
- Execute os testes pertinentes às mudanças e relate o resultado, incluindo verificações que não puderam ser realizadas.

## Provas de conceito

- As provas de conceito são orientadas pelo usuário. Organize cada uma em `pocs/<nome_do_experimento>/`.
- Inclua um README com objetivo, escopo, simplificações, preparação, comando de execução e critérios observáveis de sucesso.
- Mantenha cenários e outros dados do experimento junto da respectiva prova de conceito. Promova dados a `tests/fixtures/` quando houver compartilhamento real entre testes.
- Aproveite o código de `src/trama/` quando aplicável, sem duplicar regras no experimento.
- Converta os comportamentos aprovados em testes de regressão. Preserve os cenários com IA real como testes live quando fizer sentido.
- Não trate resultados de uma chamada real de IA como garantia determinística. Defina critérios de avaliação claros para o comportamento observado.

## Comandos e documentação

- Instalar o ambiente: `poetry install`.
- Rodar testes locais: `poetry run pytest`.
- Rodar testes live: `poetry run pytest tests/live -m live`, com o ambiente exigido pelo cenário.
- Verificar os metadados: `poetry check`.
- Atualize o README quando a estrutura ou as instruções de uso mudarem.
- Este bootstrap ainda não contém regras ou cenários. Não crie funcionalidades apenas para preencher as pastas reservadas.
