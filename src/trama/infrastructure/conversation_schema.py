"""Esquema compartilhado dos metadados de fala, sem novos pedidos ao provedor."""

from trama.conversation_state import POINT_KINDS, TERM_KINDS, PROPOSAL_ACTIONS, STATUSES


def _object(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def _text(maximum=400, *, nullable=False):
    return dict(type=['string', 'null'] if nullable else 'string', minLength=1, maxLength=maximum)


def _ids():
    return dict(type='array', maxItems=8, items=_text(120))


TERM_SCHEMA = _object(dict(id=_text(120, nullable=True),
    kind=dict(type='string', enum=list(TERM_KINDS)), text=_text(), actor_id=_text(120, nullable=True),
    order=dict(type=['integer', 'null'], minimum=1, maximum=8)))
PROPOSAL_SCHEMA = _object(dict(action=dict(type='string', enum=list(PROPOSAL_ACTIONS)),
    proposal_id=_text(120, nullable=True), version=dict(type=['integer', 'null'], minimum=1),
    in_reply_to=_text(120, nullable=True), terms=dict(type='array', maxItems=8, items=TERM_SCHEMA),
    remove_term_ids=_ids()))
CONVERSATION_SCHEMA = _object(dict(conversation_id=_text(120, nullable=True), target_ids=_ids(),
    focus=_text(160, nullable=True), points=dict(type='array', maxItems=8,
        items=_object(dict(kind=dict(type='string', enum=list(POINT_KINDS)), text=_text()))),
    resolves=_ids(), proposal=dict(anyOf=[PROPOSAL_SCHEMA, dict(type='null')]),
    goal=_text(300, nullable=True), waiting_for=_text(300, nullable=True),
    status=dict(type=['string','null'], enum=[None, *STATUSES]), reason=_text(300, nullable=True),
    romance_boundary=dict(type=['string','null'], enum=[None, 'open', 'declined']),
    boundary_text=_text(400, nullable=True), romantic_expression=dict(type='boolean')))
OPTIONAL_CONVERSATION_SCHEMA = dict(anyOf=[CONVERSATION_SCHEMA, dict(type='null')])

CONVERSATION_INSTRUCTIONS = """
conversation em speak/challenge/say anota SOMENTE a fala proposta nesta etapa.
Use objeto quando houver interlocutor ou conversa em andamento; null em fala
sem destinatário/contexto identificável e nas operações que não sejam fala.
target_ids identifica destinatários conhecidos; conversation_id referencia um
registro conhecido em conversations ou é null para selecionar/iniciar a conversa.
focus é um rótulo semântico curto do assunto, sustentado pela fala atual e pelo
contexto percebido da conversa; pode resumir sem copiar palavras literalmente.
Não é citação, novo fato, compromisso ou objetivo privado do interlocutor.
points.text contém trechos LITERAIS da fala em text. points distingue statement,
question, request, offer, condition, objection e topic. Registre assuntos laterais
como topic; uma pergunta não respondida continua pendente ao mudar o foco.
resolves lista ids de pendências realmente respondidas/retiradas nesta fala.
'latest' referencia a última pendência conhecida de OUTRO participante após as
falas anteriores realmente executadas, inclusive a fala do jogador nesta etapa.
Não marque resolvida uma pergunta apenas porque ela foi mencionada.
proposal registra offer/revise/accept/reject/withdraw, sem efeitos materiais.
Nova oferta tem proposal_id/version=null; contraproposta é nova offer com
in_reply_to da proposta conhecida. Revise somente proposta do PRÓPRIO autor:
terms contém apenas termos novos/alterados; id=null cria termo, id existente o
substitui, remove_term_ids retira termos. Os demais termos são preservados.
Separe request, counterpart e condition; actor_id é quem faria a parte, ou null
se não foi definido. order registra ordem explícita (1, 2...), não uma iniciativa
ou preferência inventada. Cada term.text é trecho literal da fala ATUAL.
Para responder a uma proposta da fala anterior, proposal_id='latest' usa a última
oferta conhecida após a comunicação real. version=null usa a versão conhecida
mais recente; nunca aceite termos não conhecidos. Aceitar não significa cumprir.
goal e waiting_for são privados do PRÓPRIO NPC e só em say; no jogador ambos
são null. Não invente o objetivo do jogador, nem use perfil/memória alheia.
Uma alternativa apenas cogitada não aparece em proposal nem points.
status/reason são null para continuar; active retoma, suspended suspende e closed
encerra, com reason LITERAL da fala. Encerrar não exige pedido ou acordo formal.
active sem reason só pode repetir o estado de conversa já ativa ou nova; é
normalizado como continuação, nunca retoma conversa suspensa ou encerrada.
Uma despedida pode reconhecer uma conversa closed sem reabri-la: use seu id,
sem novo foco, pendência, proposta ou objetivo. Novos assuntos exigem retomada.
Os metadados só entram no estado quando a fala é executada; ouvintes dependem
da audição real. Ver a boca mover não ensina os termos. Não antecipe recepção.
Conversa casual não exige proposal: acolhimento, agradecimento, conselho e oferta
de orientação podem ser falas comuns. Só registre proposta quando houver termos
ou compromissos efetivamente apresentados. focus pode resumir o assunto da fala;
encerrar esgota o encontro sem apagar seu foco histórico. Não invente
emoção, atração, necessidade ou objetivo do jogador. Uma moeda anterior declarada
na memória do cenário não é transferência nesta interação; não crie moedas ou
saldo por fala, gesto narrado ou anotação de conversa.
Passo 9: romance_boundary registra SOMENTE disponibilidade própria declarada:
open ou declined, com boundary_text LITERAL e exatamente um target_id conhecido.
Deixe ambos null se não houve declaração explícita. Não trate educação, amizade,
nota, silêncio ou uma fala de terceiro como consentimento ou mudança de limite.
O prefixo de Claim romance_boundary: é reservado ao código; use os campos de
conversation em vez de claims ou memory_ids. Compartilhar uma declaração antiga
não substitui uma declaração própria literal nem revoga limites posteriores.
O jogador declara sua escolha, sem receber valores
ou sentimentos calculados pela IA. Recusa pode ser falada mesmo ao encerrar.
romantic_expression=true anota expressão ou investida amorosa dirigida àquele
único target_id, inclusive do jogador; false para amizade, carinho não romântico
e recusa. O código exige adultos declarados e respeito a limites conhecidos.
Disponibilidade open não promete reciprocidade, amor, encontro ou aceitação.
"""
