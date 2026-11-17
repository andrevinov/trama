# Dificuldades contextuais e referências de memória

Tier 3 · [Qualidade](README.md) · [Política](politica-live-tests.md)

Bateria nova em `tests/live/test_contextual_difficulty_live.py`, casos em
`tests/fixtures/adjudication/cases.json`. Fluxo completo de uma mensagem por caso,
partindo de situações preparadas pelo carregador e operações públicas, sem pagar
pela abertura/preparação. Usa `open_situation`, composição oficial e `game.runner`.
Não substitui respostas, prompts, contextos ou etapas durante os testes reais.

Dez casos, uma tentativa cada, três chamadas previstas por caso (interpretador,
Mundo e narrador), teto de quatro por caso para eventual correção de interpretação:
30 chamadas previstas e máximo de 40. Uma rodada corretiva somente dos três casos de memória preservou as falhas
e usou o saldo do teto agregado de 40 chamadas. A última revisão de furto
recebeu três chamadas restantes (teto local de três); total medido de 40. Não houve retry automático. Chamadas adicionais
ou fluxo incompleto reprovam. Os dados opcionais ficam declarados nas situações;
preparação de disfarce é determinística, não evidência de sua interpretação.

Três conversas verificam negociação com memórias privadas e relato público do
arquivista, inclusive a frase real da falha. O esquema deve deixar `memory_ids`
vazio fora de `say`; Influence usa fatos privados sem transformá-los em fala.
A gravação antiga é coberta também offline, incluindo referência alheia rejeitada.

Sete interações verificam fala normal abafada por porta grossa (passiva 8, sem
abordagem), grito através de frestas (detecção e abordagem sem ataque), escuta
ativa com porta grossa e dados baixos/altos, busca de roupa escondida com Search,
furto da chave e inspeção de espada escondida. São fatos explícitos das variações,
não propriedades supostas para todas as portas. CDs típicas e rolagens reais
resolvem efeitos; descobrir não transfere item, furtar só transfere se passar.
Escuta falha não revela conteúdo e a inspeção com dado baixo não inicia combate.
A voz percebida não implica compreensão das palavras.

`tests/integration/test_difficulty_live_scenarios.py` verifica preparações e
oráculos sem rede; adaptadores locais explícitos não comprovam o modelo real.
`test_contextual_adjudication.py` cobre validação, privacidade, CDs fixas, dados,
cache e separação entre perceber voz e compreender palavras.

Executar somente esta bateria autorizada:

```sh
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_difficulty_live.py -m live -q
```

`OPENAI_API_KEY` deve existir. Evidências completas de cada tentativa ficam em
`logs/live/difficulty/<execução>/<caso>/{trace.jsonl,result.json}`, incluindo
configuração, pedidos/respostas, antes/depois, rolagens, tokens, erros e orçamento.
Revisão humana do texto: conferir alegações incertas, fatos realmente percebidos,
nenhum pagamento/liberdade automática ou sucesso antecipado. Aprovação de JSON
não comprova coerência narrativa. Evidência datada registra tentativas e limites.
