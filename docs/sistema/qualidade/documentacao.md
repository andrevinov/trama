# Manutenção da hierarquia documental

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## Tiers e referência canônica

O [README da raiz](../../../README.md) é tier 1: propósito, experiência, áreas e relações.
Os oito índices em `docs/sistema/<area>/README.md` são tier 2: responsabilidades,
partes e conexões. Os demais documentos dessas pastas são tier 3: contratos,
comportamentos, exemplos, limites, fontes e verificações de um assunto específico.

Cada assunto tem uma referência canônica. Documentos relacionados resumem o
necessário e apontam para ela. O código continua sendo o comportamento executado;
a documentação deve explicar sua intenção, seus contratos e suas limitações.

Um assunto novo pode começar como seção de um documento. Separe-o quando tiver
contrato, exemplos ou regras próprias suficientes. Evite criar arquivos vazios
para recursos futuros ou replicar uma mesma API em vários módulos.

## O que registrar num documento específico

1. Propósito e vínculo ao índice da área e à visão geral.
2. Código responsável, entradas e saídas ou estruturas relevantes.
3. Comportamento normal, impedimentos e efeitos parciais.
4. Regras com referência da edição, decisões do usuário e simplificações explícitas.
5. Relações com outros documentos canônicos, sem copiar suas definições.
6. Exemplos e testes pertinentes; limites de suporte da API e da interface.

Use português para explicações e preserve identificadores de código em inglês.
Links são relativos ao documento. Prefira nome de arquivo e símbolo a números
de linha que envelhecem rapidamente. Atualize o índice da área ao criar uma folha.

## Atualizar uma implementação

Uma mudança local atualiza o documento específico e seus exemplos. Se mudar
responsabilidades ou relações, revise o tier 2; se alterar a visão da aplicação,
revise também o tier 1. Distinga API disponível, comando disponível na conversa,
comportamento exclusivo do cenário e capacidade ainda não implementada.

Leia [AGENTS.md](../../../AGENTS.md) antes de trabalhar no repositório. Para criar,
alterar ou executar live tests, leia também a [política](politica-live-tests.md).
Mudanças de contexto seguem a [revisão de contratos](../ia/contextos-e-contratos.md#como-revisar-uma-mudança).
Mudar a documentação não autoriza chamadas pagas ou atualização automática da referência.

## Roadmaps e evidências

[Roadmaps](../../roadmaps/README.md) vivem separados, por estado:
`nao-implementados`, `em-implementacao` e `implementados/AAAA-MM-DD-nome`.
Cada pasta pode conter plano e materiais auxiliares. A data é de conclusão,
não de reorganização. Preserve objetivo, critérios, resultado e pendências.
Antes de arquivar, incorpore o funcionamento entregue às referências do sistema.

[Evidências](../../evidencias/README.md) guardam relatórios e manifestos datados.
Elas registram o que foi observado com uma configuração e estado específicos.
Retenha proveniência, falhas, inconclusivos e limites da amostra; uma nova
implementação não reescreve os resultados antigos como se tivessem sido medidos nela.

Na reorganização de arquivos, preserve os caminhos literais e os hashes dos
registros originais. Documente relocações em registro separado e distinga bytes
preservados de refatorações. O [inventário das análises](../../evidencias/2026-11-16-preservacao-das-analises/relatorio.md)
mostra esse procedimento; `tools/check_evidence.py` confere integridade sem
recalcular expectativas ou atualizar os hashes aprovados.

Referências do simulador e READMEs de testes e ferramentas mantêm objetivo, escopo, simplificações,
preparação, comandos e critérios locais, com links para a referência técnica.
Dados e fixtures permanecem nos locais que a aplicação efetivamente utiliza.

## Verificar uma edição

Confira destinos e âncoras dos links, navegação tier 1 → tier 2 → tier 3,
blocos de código e caminhos usados nos comandos. Use `git diff --check` e
`poetry check`. Execute testes adequados quando houver impacto em exemplos,
contratos ou código. Não apresente uma pasta planejada como já implementada.
