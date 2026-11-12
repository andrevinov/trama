"""Coordena diálogo, execução e fatos para o narrador. Não faz chamadas de rede."""

from dataclasses import dataclass

from trama.actions import ActionError, DoorActionResult
from trama.application.dialogue import DialogueMessage, Speech, split_speech
from trama.application.intents import ActionPlan, DoorIntent
from trama.application.session import GameSession
from trama.distances import CELL_METERS
from trama.movement import MovementError, MovementResult


@dataclass(frozen=True)
class ExecutionReport:
    events: tuple[dict, ...] = ()
    progress: bool = False
    stop_reason: str | None = None
    unperformed_steps: int = 0

    def context(self) -> dict:
        return {"events": list(self.events), "progress": self.progress,
                "stop_reason": self.stop_reason, "unperformed_steps": self.unperformed_steps,
                "reactions": []}  # Guardas ainda não possuem comportamento.


class Conversation:
    def __init__(self, session: GameSession) -> None:
        self.session = session
        self.messages: list[DialogueMessage] = []

    def prepare(self, raw: str) -> Speech:
        if not raw.strip() or len(raw) > 2000:
            raise ValueError("Digite uma mensagem com 1 a 2000 caracteres.")
        speech = split_speech(raw)
        if not speech.on and not speech.off:
            raise ValueError("A mensagem está vazia.")
        self.messages.append(DialogueMessage("player", speech))
        return speech

    def interpretation_context(self) -> dict:
        context = self.session.interpreter_context()
        # Perguntas/comandos em off, inclusive no histórico, não entram na interpretação.
        context["recent_messages"] = [{"role": m.role, "on": m.speech.on}
                                      for m in self.messages[-12:] if m.speech.on]
        return context

    def execute(self, plan: ActionPlan) -> ExecutionReport:
        events = []
        progress = False
        reason = None
        attempted = 0
        for intent in plan.steps:
            attempted += 1
            before = self.session.state
            budget_before = self.session.budget
            try:
                result = self.session.execute(intent)
            except (MovementError, ActionError) as error:
                reason = str(error)
                break
            if isinstance(result, MovementResult):
                changed = before != result.state or self.session.budget != budget_before
                events.append({"operation": "move", "changed": changed,
                               "from": [before.position.x + 1, before.position.y + 1],
                               "to": [result.state.position.x + 1, result.state.position.y + 1],
                               "traveled_meters": float((len(result.path) - 1) * CELL_METERS),
                               "cost_meters": float(result.cost_meters),
                               "dash": result.state.dash_used and not before.dash_used})
                progress |= changed
                if result.stop_reason:
                    reason = result.stop_reason
                    break
            elif isinstance(result, DoorActionResult):
                assert isinstance(intent, DoorIntent)
                passage = next(p for p in self.session.scene.passages if p.id == intent.target_id)
                events.append({"operation": intent.operation, "changed": result.changed,
                               "target": passage.name, "is_open": result.is_open})
                progress |= result.changed
        return ExecutionReport(tuple(events), progress, reason, len(plan.steps) - attempted)

    def narration_context(
        self, speech: Speech = Speech(), report: ExecutionReport = ExecutionReport(),
        *, initial: bool = False,
    ) -> dict:
        context = self.session.interpreter_context()
        # O narrador descreve a percepção atual, não o mapa arquitetônico inteiro.
        visible = self.session.visibility.visible
        scene = self.session.scene
        area = scene.area_at(self.session.state.position) if scene else None
        perception = {
            "current_place": area.name if area else "passagem",
            "current_description": area.description if area else "",
            "visible_places": ([{"name": a.name, "description": a.description}
                                for a in scene.areas if a.cells & visible] if scene else []),
            "visible_passages": ([p for p in context["map"]["scene"]["passages"] if p["visible"]]
                                 if scene else []),
            "visible_creatures": context["visible_creatures"],
        }
        return {
            "phase": "initial" if initial else "reply",
            "allow_on": initial or report.progress,
            "player": {"on": speech.on, "off": speech.off},
            "execution": report.context(), "perception": perception,
            "character": context["character"],
            "history": [{"role": m.role, "on": m.speech.on, "off": m.speech.off}
                        for m in self.messages[-12:]],
            "verified_rules": [
                "PHB 2024: movimento em casas de 1,5 m; terreno difícil custa 3 m por casa.",
                "PHB 2024, Dash: usa a ação para adicionar movimento igual à velocidade no turno.",
                "PHB 2024, objetos/Utilize: primeira interação gratuita; seguinte usa a ação.",
                "PHB 2024, visão: Humano sem visão no escuro; paredes/portas fechadas bloqueiam.",
                "Cenário: guardas permanecem parados. Não há reações ou combate implementados.",
                "Decisão do usuário: executar o possível, parar no impedimento e explicar em off.",
                "POC: casas inteiras; uma fração restante não é executada nem arredondada para cima.",
            ],
        }

    def finish(self, reply: Speech, context: dict) -> Speech:
        on = reply.on if context["allow_on"] else ""
        off = reply.off
        reason = context["execution"]["stop_reason"]
        if reason:
            character = context["character"]
            place = context["perception"]["current_place"]
            where = f"{place} (coluna {character['column']}, linha {character['row']})"
            explanation = (f"Parei em {where}. " if context["execution"]["progress"]
                           else f"Não foi possível realizar a ação em {where}. ") + reason
            if context["execution"]["unperformed_steps"]:
                explanation += " As etapas seguintes não foram executadas."
            if explanation not in off:
                off = "\n".join(p for p in (off, explanation) if p)
        if not on and not off:
            off = "Nenhuma ação foi realizada."
        final = Speech(on, off)
        self.messages.append(DialogueMessage("narrator", final))
        return final

    def failure(self, explanation: str) -> Speech:
        reply = Speech(off=explanation)
        self.messages.append(DialogueMessage("narrator", reply))
        return reply
