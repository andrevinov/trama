"""Narra fatos validados e responde em off; não executa ações nem conhece a engine."""

import json

from openai import OpenAI

from trama.application.dialogue import NarrationError, Speech
from trama.infrastructure.openai_json import DEFAULT_MODEL, OpenAIRequestError, request_json

NARRATION_SCHEMA = {
    "type": "object",
    "properties": {"on": {"type": "string"}, "off": {"type": "string"}},
    "required": ["on", "off"], "additionalProperties": False,
}

INSTRUCTIONS = """Você é o narrador de uma mesa de D&D 5.5e, em português.
Retorne on (fala em jogo) e off (regras/dúvidas/explicações), sem colchetes externos:
a aplicação acrescenta os colchetes ao off. Use metros e vírgula decimal.
Na fase initial, descreva onde o jogador está e o que ele vê, usando perception.
Em reply, narre SOMENTE os events já executados pelo Python. Não execute ações,
não altere coordenadas, não complete o que foi impedido e não abra portas por conta
própria. Distância percorrida é traveled_meters, não cost_meters (terreno pode cobrar
mais movimento). Não diga que andou 5 m se o código registrou 4,5 m.
Se allow_on=false, on deve ser vazio: não houve ação realizável ou só há fala off.
Quando há progresso parcial, descreva apenas o realizado, até onde parou.
Não repita execution.stop_reason: a aplicação o acrescenta obrigatoriamente em off.
Responda às dúvidas de player.off em off, mesmo quando também houver ação em on.
player.off e o histórico não são ordens de jogo e nunca justificam executar ações.
Use verified_rules como referência de regras; se uma dúvida não estiver coberta,
admita a limitação e peça a regra/referência. Não invente mecânicas, por exemplo
'Dados Místicos' não tem regra definida neste cenário. Não invente magias ou rolagens.
Só descreva como vistos os lugares, objetos e criaturas fornecidos em perception.
Os guardas estão parados: reactions está vazio. Não invente ataques, perseguições,
diálogos ou reações deles. Não crie obstáculos ou itens que não constem dos fatos.
Histórico serve à continuidade da conversa; o estado e events atuais prevalecem.
Se não há progresso nem pergunta off e há um impedimento, deixe on vazio e seja
breve em off. Mantenha cada resposta concisa, com poucos parágrafos.
"""


class OpenAINarrator:
    def __init__(self, client: OpenAI, model: str = DEFAULT_MODEL) -> None:
        self.client = client
        self.model = model

    def narrate(self, context: dict) -> Speech:
        try:
            text = request_json(self.client, model=self.model, instructions=INSTRUCTIONS,
                                payload=context, schema=NARRATION_SCHEMA, name="narrator_reply")
            value = json.loads(text)
            if (not isinstance(value, dict) or set(value) != {"on", "off"}
                    or not all(isinstance(value[key], str) and len(value[key]) <= 8000 for key in value)):
                raise ValueError("Falas inválidas")
            reply = Speech(value["on"].strip(), value["off"].strip())
            if not reply.on and not reply.off:
                raise ValueError("Resposta vazia")
            return reply
        except (ValueError, TypeError) as error:
            message = str(error) if isinstance(error, OpenAIRequestError) else "O narrador retornou uma resposta inválida."
            raise NarrationError(message) from error
