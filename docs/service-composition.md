# Composição e configuração dos serviços

O passo 8 do [plano dos live tests](live-tests-plan.md) compartilha a criação dos
serviços com o simulador. A [política](live-tests-policy.md) continua valendo:
variantes experimentais não são avaliações do padrão, e criar/compor serviços
não autoriza executar chamadas pagas.

## Responsabilidades

- `infrastructure/openai_config.py`: configurações imutáveis, validação e resolução
  do modelo. Não importa o SDK, regras ou credenciais.
- `infrastructure/openai_services.py`: cria o cliente e os três adaptadores com a
  configuração resolvida. Controla o fechamento e registra a configuração.
- `bootstrap.py`: compõe sessão e `GameFlow` com esses serviços, pelo carregador
  compartilhado. Não importa Pygame nem cria outra sequência de execução.
- `simulator.py`: usa essa composição e entrega o fluxo já criado à janela.
  A janela mantém entrada, desenho e agenda de workers.

O coordenador e as regras continuam dependendo de contratos de aplicação, sem
importar a infraestrutura ou o SDK.

## Configuração e precedência

`OpenAIConfig.from_env()` usa `DEFAULT_CONFIG` e resolve `TRAMA_OPENAI_MODEL`.
O SDK lê `OPENAI_API_KEY` e suas opções de autenticação/conexão; seus valores não
são copiados para a configuração ou para os metadados. Modelo vazio é erro.
Passar um `OpenAIConfig` explicitamente à composição utiliza esse objeto, sem
consultar novamente o ambiente para sobrescrever o modelo.

Os padrões permanecem:

| Configuração | Valor |
| --- | --- |
| Modelo | `gpt-5.6-terra` |
| Timeout do SDK | 30 segundos |
| Retries do SDK | 0 |
| Contexto do interpretador | `minimal` |
| Correções do interpretador | Até 1 |
| Ordem do esquema | `operation-first` |
| Interpretação / narração | Até 1000 tokens, raciocínio `low` |
| Mundo / NPC | Até 2000 tokens, raciocínio `low` |

`ResponseOptions` declara limite de tokens e esforço por fase. Esquemas estritos,
`store=False`, instruções e projeções continuam vindo dos adaptadores reais.
A correção do interpretador e os retries de transporte são mecanismos distintos.
Nenhum prompt especial é acrescentado por esta composição.

Exemplo de composição para uma entrada de aplicação:

```python
from trama.bootstrap import open_game

with open_game('pocs/simulador/dungeon.json') as game:
    flow = game.flow
    configuration = game.services.metadata
    # A janela agenda os pedidos de flow; game.runner oferece a agenda sem janela.
```

`open_game` aceita arquivo, dados de cenário ou uma sessão já preparada. As
rolagens são injetadas ao construir a sessão; tentar trocá-las depois de preparar
uma sessão é rejeitado. `compose_game(session, services)` permite usar serviços
já abertos. Nenhuma dessas funções executa chamadas ou conduz um loop de NPCs.

## Ciclo de vida

`open_services` cria exatamente um cliente compartilhado pelos três adaptadores,
com timeout e retries explícitos, e fecha esse cliente inclusive em falhas do
consumidor, da composição ou da janela. Um cliente injetado pertence ao chamador
e não é fechado nem reconfigurado: a evidência identifica `client_source=injected`.
Nesse caso, o chamador é responsável pelas opções de transporte desse cliente;
a composição continua aplicando seus parâmetros aos adaptadores.

O simulador usa `allow_unconfigured=True` para permitir visualizar o mapa sem
chave, mantendo os serviços ausentes e sem fabricar respostas. As suítes live
não habilitam essa opção: ausência/falha do serviço é reportada, sem substituir
IA real por execução local. Seus gates de autorização permanecem.

## Experimentos e evidências

`open_game(..., budget=CallBudget(max_calls))` e `open_services(..., budget=...)`
permitem um limite opcional compartilhado entre os três adaptadores. A reserva
acontece antes de `responses.create`, inclusive para correções; ao exceder,
interrompe o pedido. O orçamento não é enviado à IA e não muda os padrões.
Se retries do SDK forem diferentes de zero, os metadados indicam também o limite
superior de tentativas de transporte. Não há teto monetário. A
[suíte contextual migrada](contextual-live-flow.md) usa esse limite e reprova
execuções incompletas, preservando os efeitos já realizados.

Uma configuração diferente do padrão é marcada como `profile=experiment`, com
`differences_from_default`. `for_experiment(nome, **alteracoes)` permite nomear a
variante mesmo quando ela coincide com o padrão. Um modelo alternativo por
`TRAMA_OPENAI_MODEL` também é identificado como alteração, quando difere do padrão.

A suíte semântica mantém zero correções como `semantic_first_attempt`; agora
respeita o mesmo modelo do ambiente. A POC e as suítes de comparação usam
`interpretation_comparison`, preservando contexto completo, esquema antigo ou
zero correções somente quando declarados. Não são apresentadas como fluxo padrão.

A configuração é emitida em `ai.services_configured`: modelo solicitado, timeout,
retries, opções de interpretação, parâmetros por fase, perfil/diferenças, versão
do SDK, host do provedor e origem do cliente. O host não inclui credenciais,
caminho ou query. Falha ao criar o cliente emite
`ai.services_configuration_failed`, com `status=initialization_failed`: registra
a configuração tentada, sem afirmar que houve execução.

Os live tests salvam `configurations.json` no diretório temporário do caso,
inclusive quando a inicialização falha. A suíte contextual inclui a configuração
no `result.json` persistente; as suítes de interações/semântica e a POC a incluem
em seus artefatos. Variantes que compartilham um cliente podem registrar uma
composição do transporte e outras dos adaptadores experimentais.

Os logs de cada pedido continuam mostrando os parâmetros efetivamente enviados,
tokens e o modelo retornado pelo provedor. Modelo solicitado e modelo reportado
pelo provedor são evidências distintas.

## Verificação e limite do incremento

```bash
poetry run pytest tests/integration/test_service_composition.py -q
```

As regressões usam transporte simulado para verificar parâmetros das três fases,
fechamento, falhas, configuração registrada, preservação das instruções e uma
mudança de padrões chegando à CLI/janela e à suíte contextual. Fronteiras de
módulos impedem que simulador, POC e arquivos live recomponham clientes/adaptadores.

Os contratos de contexto continuam passando na revisão offline sem alteração de
referência. Não foram executadas chamadas pagas. A [agenda sem janela](headless-runner.md)
está disponível em `game.runner`, sobre o mesmo `game.flow`. Os oito casos
contextuais já a utilizam; as outras cinco suítes continuam parciais/experimentais.
