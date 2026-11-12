# Provas de conceito

Experimentos pequenos, orientados pelo usuário, para validar partes do Trama antes de ampliar o sistema.

- [Movimento, ações e conversa](movimento/README.md): mapas Pygame, portas, visão e guardas estáticos; diálogo on/off com descrição inicial, execução até o impedimento e narração pela OpenAI. Inclui o cenário Cela/Corredor/Sala dos Guardas e o tabuleiro original 10×10.

Crie uma pasta por experimento, como `pocs/movimento/`. Use Python, execute pelo Poetry e mantenha os dados do cenário junto do experimento.

O README de cada prova de conceito deve registrar:

1. Objetivo e comportamento a explorar.
2. Escopo, regras consideradas e simplificações.
3. Preparação, dependências e variáveis de ambiente necessárias.
4. Comando para execução a partir da raiz do repositório.
5. Entradas de exemplo e critérios observáveis de sucesso.
6. Testes automatizados derivados do experimento, quando existirem.

As primeiras experiências devem priorizar componentes determinísticos. Conforme houver integração com IA, documente quais etapas fazem chamadas reais e seus requisitos. Depois da validação pelo usuário, transforme os comportamentos pertinentes em testes locais ou live, conforme suas dependências.
