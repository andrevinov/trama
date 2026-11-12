import pytest

from trama.application.dialogue import Speech, split_speech


@pytest.mark.parametrize("text,on,off", [
    ("Ando para o norte.", "Ando para o norte.", ""),
    ("[Quanto posso andar?]", "", "Quanto posso andar?"),
    ("Ando 5 m.\n\n[Como funciona Dash?]", "Ando 5 m.", "Como funciona Dash?"),
    ("[Dúvida 1] Abro a porta. [Dúvida 2]", "Abro a porta.", "Dúvida 1\nDúvida 2"),
    ("[Não execute [abra a porta]]", "", "Não execute [abra a porta]"),
])
def test_on_off_split(text, on, off):
    assert split_speech(text) == Speech(on, off)


@pytest.mark.parametrize("text", ["Abra [a porta", "Ande]", "[Pergunta]]"])
def test_unbalanced_brackets_require_correction(text):
    with pytest.raises(ValueError):
        split_speech(text)


def test_off_is_rendered_between_brackets():
    assert Speech("Você caminhou 3 m.", "Restam 6 m.").text == "Você caminhou 3 m.\n\n[Restam 6 m.]"
    assert Speech(off="Não foi possível.").text == "[Não foi possível.]"
