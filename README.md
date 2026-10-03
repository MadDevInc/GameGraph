# GameGraph by MadDev Studios

**A IA mapeia como o seu jogo Godot é feito, e todos os agentes seguem esse mapa.**

O GameGraph é um plugin para o [Claude Code](https://claude.com/claude-code). Com um comando (`/gamephy`), a IA lê o seu projeto Godot e monta um mapa visual:

- **Processos**: *Criar inimigo*, *Criar arma*, *Criar item*… cada um com passos concretos ligados aos arquivos reais (`.gd`, `.tscn`, `.tres`).
- **Sistemas**: autoloads, managers, event bus.
- **Entidades**: Goblin, Player… os exemplos concretos.
- **Regras**: as convenções do seu projeto.

Você revisa e edita tudo numa interface web. Depois, qualquer agente lê o mapa antes de trabalhar e faz as coisas **do jeito do seu jogo**, sem reinventar a estrutura. Na prática, ele substitui o `CLAUDE.md`.

## Por que usar
- **Menos retrabalho:** o agente segue o processo real ("copie goblin.tscn, herde BaseEnemy, crie o .tres, registre no spawner") em vez de adivinhar.
- **Menos tokens:**
  - Um índice curto é lido em toda sessão, e o detalhe de cada processo só quando precisa.
  - O mapa aponta os arquivos certos, então o agente não precisa explorar o projeto.
- **"Faça como o Goblin" pronto:** a ferramenta calcula o que cada variação muda (funções, exports) e monta tabelas de valores dos `.tres`.
- **Nunca fica velho em silêncio:** se um arquivo muda, o processo ligado a ele é marcado como **⚠ revisar**, para você e para os agentes.
- **Suas edições valem mais que as da IA:** nós editados por você não são sobrescritos, e nós apagados não voltam.
- **Leve:** precisa só de Python 3.10+, sem dependências. Funciona com Godot 3 e 4. Não altera nada no seu projeto.

## Instalação
Requisitos: [Claude Code](https://claude.com/claude-code) e **Python 3.10+**.

No Claude Code:
```
/plugin marketplace add SEU_USUARIO/GameGraph
/plugin install gamegraph@maddev-studios
```

## Uso
Abra o Claude Code na pasta do seu jogo (onde está o `project.godot`):
```
/gamephy            # a IA monta o mapa e abre a interface em http://127.0.0.1:8765
/gamephy --update   # atualização incremental: relê só o que mudou
```
Se outro comando já usar o nome `/gamephy`, use `/gamegraph:gamephy`.

Na interface, o botão **? Guia** explica tudo. Tutorial completo: **[TUTORIAL.md](plugins/gamegraph/TUTORIAL.md)**.

## O que é gerado
Tudo fica em `<seu-jogo>/gamegraph-out/`. O Godot esconde essa pasta (por causa do `.gdignore`), e você pode versioná-la no git para a equipe compartilhar o mapa.

| Arquivo | Conteúdo |
|---|---|
| `CONTEXT.md` | Índice curto: regras e uma linha por processo, sistema e entidade |
| `nodes/<nome>.md` | Detalhe de cada nó: passos, arquivos, árvore da cena, variações, valores |
| `design.json` | O grafo, editado pela interface e pela IA |
| `ARCHITECTURE.md`, `index.json` | Dados lidos do projeto |

## Desenvolvimento
```bash
python plugins/gamegraph/gamegraph caminho/do/jogo   # rodar direto, sem Claude Code
python tests/test_godot.py                           # testes
claude plugin validate .                             # validar o marketplace
```
Código:
- `plugins/gamegraph/gamegraph/godot.py`: leitura do Godot;
- `context.py`: grafo e contexto para os agentes;
- `__main__.py`: linha de comando e servidor;
- `static/index.html`: interface.

## Licença
MIT © MadDev Studios
