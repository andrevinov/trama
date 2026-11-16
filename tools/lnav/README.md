# Ferramentas do Trama para lnav

[Índice de observabilidade](../../docs/sistema/observabilidade/README.md) ·
[Manual de instalação, comandos e consultas](../../docs/sistema/observabilidade/investigacao-com-lnav.md)

O pacote em `formats/trama/` reconhece os logs do Trama e fornece tabelas de
eventos, IA e erros, além de leitura do texto completo. Não depende da engine.
Requer lnav 0.14 ou superior.

Para usar a versão do repositório sem instalar, na raiz:

```bash
lnav -I tools/lnav logs/trama.jsonl
lnav -C -I tools/lnav logs/trama.jsonl
poetry run pytest tests/integration/test_lnav_format.py -q
```

O manual canônico descreve instalação no perfil, `|trama-events`, `|trama-detail`,
atalhos, SQL e limites de leitura. A verificação local usa o binário real com
configuração temporária, sem chamadas de IA.
