"""Quebra de texto por palavras para os painéis Pygame."""

def word_lines(text: str, font, width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
        while paragraph:
            count = 0
            while count < len(paragraph) and font.size(paragraph[:count + 1])[0] <= width:
                count += 1
            count = max(1, count)
            if count < len(paragraph):
                split = paragraph.rfind(" ", 0, count + 1)
                if split > 0:
                    count = split
            lines.append(paragraph[:count])
            paragraph = paragraph[count:].lstrip()
    return lines

