# GameGraph: tutorial completo

**GameGraph by MadDev Studios**: o mapa de como o seu jogo Godot é feito, montado por IA, editável por você e lido por qualquer agente.

---

## 1. O problema que ele resolve

Quando você pede para uma IA "criar um inimigo novo", ela costuma:
- inventar uma estrutura diferente da que o projeto já usa;
- colocar a IA do inimigo dentro da cena, quando o seu padrão é usar uma state machine;
- esquecer de criar o `.tres` com os status;
- não registrar o inimigo no spawner.

O motivo: ela **não sabe como o seu jogo é feito**. O `CLAUDE.md` ajuda, mas é um texto solto. Ele fica desatualizado, não aponta para os arquivos reais e ninguém sabe o que tem dentro.

O GameGraph resolve isso com um **mapa vivo** do projeto:
- **Processos**: "Criar inimigo", "Criar arma", "Criar item". Cada um tem os passos em ordem e os arquivos reais que servem de base.
- **Sistemas**: autoloads, managers, event bus.
- **Entidades**: Goblin, Player, Espada. São os exemplos concretos.
- **Regras**: "todo inimigo herda BaseEnemy", "status ficam em .tres".
- **Arquitetura real**: quem herda de quem, qual cena usa qual script. Isso é detectado sozinho a partir dos arquivos.

## 2. Por que usar (vantagens)

| Sem GameGraph | Com GameGraph |
|---|---|
| A IA adivinha a estrutura | A IA segue o **processo** do seu jogo, passo a passo |
| `CLAUDE.md` escrito à mão e desatualizado | O mapa é **gerado pela IA** a partir do código real e atualizado com `/gamephy --update` |
| Texto solto, sem link com arquivos | Cada passo aponta para o **arquivo real** (`.gd`, `.tscn`, `.tres`) |
| Só a IA entende (ou ninguém) | **Humanos também leem**: cartões visuais, com textos nas conexões |
| Vários agentes fazem cada um de um jeito | Todos os agentes leem o **mesmo mapa** e seguem as mesmas regras |
| Arquivo apagado fica referenciado para sempre | Referências quebradas aparecem **em vermelho** |
| Novo membro da equipe leva dias para entender o projeto | Abre o GameGraph e vê **como cada coisa é feita** |

Outras vantagens:
- **Não mexe no seu jogo.** O GameGraph só lê os arquivos do Godot. Tudo dele fica em `gamegraph-out/`, e o Godot esconde essa pasta.
- **Suas edições valem mais que as da IA.** Se você editar ou apagar um nó, a IA não sobrescreve nem recria.
- **Leve.** Precisa só de Python, sem instalar bibliotecas. O scan de um projeto grande leva segundos.
- **Funciona com qualquer projeto Godot 3 ou 4.**

## 3. Instalação

Requisito: **Python 3.10+** (`python --version`).

**Como plugin do Claude Code** (quando publicado):
```
/plugin marketplace add <usuario>/gamegraph
/plugin install gamephy@gamegraph
```

**Manual:** copie a pasta `GameGraph` para qualquer lugar e a pasta do skill para `~/.claude/skills/gamephy/`. Ajuste o caminho dentro do `SKILL.md`.

## 4. Primeiro uso, passo a passo

### Passo 1: gerar o mapa
Abra o Claude Code **na pasta do seu jogo** (onde está o `project.godot`) e digite:
```
/gamephy
```
O que acontece:
1. O Python indexa todos os arquivos (segundos).
2. O Claude lê a arquitetura e os scripts principais e identifica processos, sistemas, entidades e regras.
3. Ele grava o grafo e abre a interface em **http://127.0.0.1:8765**.

Em projetos grandes, o passo 2 pode levar alguns minutos, porque a IA está lendo o código. É normal.

### Passo 2: conhecer a tela
Na primeira vez, o **Guia** abre sozinho. Ele também fica no botão **? Guia**.

```
┌──────────────┬───────────────────────────────┬──────────────────┐
│ ARQUIVOS DO  │                               │ Inspetor │Arquivo│
│ PROJETO      │   [CRIAR INIMIGO]             │ Contexto IA      │
│              │   ┌──────────────────────┐    │                  │
│ ▾ enemies    │   │■ 1. herdar de · base │    │  (edita o nó     │
│   goblin.tscn│   │■ 2. cena exemplo ·.. │    │   selecionado)   │
│   goblin.gd  │   └──────────────────────┘    │                  │
│              │        │ exemplo              │                  │
│ (arraste p/  │   [Goblin]                    │                  │
│  um cartão)  │                               │                  │
└──────────────┴───────────────────────────────┴──────────────────┘
```

- **Topo**:
  - **Processos / Arquitetura**: troca a vista do grafo.
  - **Buscar nó**: digite e aperte Enter para ir até o nó.
  - **+ Nó**, **Relacionar…**, **Organizar** e **Enquadrar**: editam e arrumam o grafo.
  - **Regras**, **Contexto IA** e **Reescanear**.
  - **? Guia**: abre o guia.
- **Esquerda**: os arquivos reais do projeto.
- **Centro**: o grafo.
- **Direita**: o Inspetor (edita o nó), o Arquivo (mostra o conteúdo) e o Contexto IA (o que o agente recebe).

### Passo 3: revisar o que a IA fez
1. Sem nada selecionado, o painel da direita mostra a **lista de todos os processos, sistemas e entidades**. Clique num item para ir até ele.
2. Clique no **título** de um cartão para abrir o Inspetor.
3. Confira:
   - **Descrição**: está certa?
   - **Passos**: é assim mesmo que se faz no seu jogo?
   - **Arquivos ligados**: são os arquivos certos? O texto de cada conexão explica bem para que ele serve?
4. Corrija o que estiver errado. **Tudo que você edita fica protegido**: a IA não sobrescreve depois.

### Passo 4: ajustar a organização
- **Mover**: arraste o cartão pelo título.
- **Organizar**: refaz a grade (processos em cima, depois sistemas, depois entidades).
- **Apagar** um nó inútil: botão Apagar no Inspetor. A IA não vai recriá-lo.
- **Criar** um processo que a IA não viu: **+ Nó** (ou duplo clique no fundo). Mude o tipo para *Processo* e escreva os passos.
- **Ligar um arquivo**: arraste da lista da esquerda para cima do cartão.
- **Relacionar dois nós**: selecione um, clique em **Relacionar…**, clique no outro e escreva a relação (ex.: *exemplo*, *usa*, *depois de*).

### Passo 5: escrever as regras
Clique em **Regras**:
- **Regras do jogo**: "Todo inimigo herda BaseEnemy", "Nunca usar get_node com caminho absoluto".
- **Instruções para os agentes**: "Antes de criar algo, siga o PROCESSO correspondente", "Rode os testes antes de terminar".

Isso aparece **no topo** do contexto de todo agente.

### Passo 6: ligar os agentes ao mapa
No fim do `/gamephy`, o Claude oferece trocar o seu `CLAUDE.md` por:
```
Antes de qualquer tarefa neste projeto Godot, leia gamegraph-out/CONTEXT.md e siga o PROCESSO correspondente.
Para detalhes de um nó: python <caminho>/gamegraph . --context "<nó>" --code
Depois de criar algo novo, rode /gamephy --update.
```
A partir daí, o conhecimento mora no GameGraph, não no CLAUDE.md.

## 5. As duas vistas

### Processos (padrão)
Mostra o que a IA e você montaram. Cada cartão é um nó, e dentro dele estão os arquivos com o texto da conexão:

```
        CRIAR INIMIGO
┌─────────────────────────────────┐
│ ■ 1. herdar de  · base_enemy.gd │
│ ■ 2. cena base  · goblin.tscn   │
│ ■ 3. dados      · goblin_data…  │
└─────────────────────────────────┘
```
- Cores:
  - **Cartão**: vermelho = processo, azul = sistema, laranja = entidade.
  - **Quadradinho do arquivo**: verde = cena, azul = script, roxo = dados, vermelho = arquivo que sumiu.
- **Clique num arquivo** para ver o conteúdo na aba **Arquivo**.

### Arquitetura
Mostra as ligações **reais** entre os arquivos, detectadas sem IA:
- **Código** (azul): `goblin.gd → herda → base_enemy.gd`, preloads.
- **Arquivos** (verde): `goblin.tscn → usa → goblin.gd`, `→ instancia → hitbox.tscn`.

Use quando quiser entender dependências, ou para conferir se o que a IA escreveu bate com o código.

## 6. Ver arquivos sem abrir o Godot
Clique em qualquer arquivo e a aba **Arquivo** mostra o conteúdo conforme o tipo:
- **`.gd`**: código colorido, números de linha e busca. No topo aparecem classe, de quem herda, sinais, variáveis exportadas e funções. Clique numa função para pular até a linha.
- **`.tscn`**: árvore de nós da cena (clique num nó para ver as propriedades), recursos externos, sub-recursos e conexões de sinais.
- **`.tres`**: tipo e todas as propriedades (vida, dano, velocidade…).
- **Imagens e áudio**: preview direto na tela.

Em todos aparecem também **"Usado nos nós"**, para ver em quais processos o arquivo aparece, e **"Ligações detectadas"**, com quem usa e quem é usado por ele.

## 7. O que a IA recebe (Contexto IA)
- **Sem nó selecionado**: o mapa inteiro do jogo, com regras, instruções e todos os processos com passos e arquivos. É o arquivo `gamegraph-out/CONTEXT.md`.
- **Com um nó selecionado**: o detalhe daquele nó, com a árvore da cena, o resumo do script e a cadeia de herança, as propriedades do `.tres` e as ligações detectadas. Com **incluir código**, vão também os scripts inteiros.

Exemplo do que um agente lê ao trabalhar em "Criar inimigo":
```
## REGRAS DO JOGO
- Todo inimigo herda BaseEnemy

## Criar inimigo  (processo)
### PASSOS
1. Criar a cena herdando base_enemy.tscn
2. Script com class_name X extends BaseEnemy
3. Criar o EnemyData .tres com vida/dano/velocidade
### ARQUIVOS
- 1. herdar de → res://enemies/base/base_enemy.gd
- cena exemplo → res://enemies/goblin/goblin.tscn
### CENA EXEMPLO
Raiz: Goblin (CharacterBody2D)
  - Sprite2D (Sprite2D)
  - StateMachine (Node)
...
```

## 8. Vários agentes trabalhando juntos
Como todos leem o mesmo `CONTEXT.md`:
- o **agente de inimigos** segue "Criar inimigo";
- o **agente de UI** segue "Criar tela";
- o **agente de balanceamento** mexe só nos `.tres` que os processos apontam.

Todos respeitam as mesmas **regras** e **instruções**. Quando um agente cria algo novo, roda `/gamephy --update` e o mapa cresce sem perder as suas edições.

## 9. Manter atualizado (e confiável)
Mapa desatualizado é pior que mapa nenhum, porque o agente segue passos velhos com confiança. Por isso o GameGraph **guarda uma impressão digital de cada arquivo** no momento em que o nó foi criado ou revisado:
- Se um arquivo ligado muda, o cartão ganha **borda laranja tracejada e "⚠ revisar"**, e o arquivo mostra "⚠ mudou".
- O agente também é avisado: no `CONTEXT.md` o nó aparece como **⚠ REVISAR**, e o arquivo do nó lista quais arquivos mudaram.
- Na tela, abra o nó, confira os passos e clique em **✔ Marcar como revisado**.

Para atualizar:
- **Mudou arquivos no Godot?** A tela percebe e reindexa sozinha a cada poucos segundos (ou use **Reescanear**).
- **Criou coisas novas?** Rode `/gamephy --update`. É **incremental**: a IA relê só os arquivos que mudaram e só os scripts e cenas que nenhum nó cobre ainda. Gasta uma fração dos tokens da primeira geração.

## 10. Comandos (para usar fora do Claude)
```
python gamegraph <projeto>                      # indexa + abre a interface
python gamegraph <projeto> --no-serve           # só atualiza gamegraph-out/
python gamegraph <projeto> --context "<nó>"     # contexto de um nó (--code inclui scripts)
python gamegraph <projeto> --import arquivo.json  # grava um grafo feito pela IA
python gamegraph <projeto> --port 9000          # usar outra porta
```

## 11. Arquivos gerados (`<projeto>/gamegraph-out/`)
| Arquivo | O que é | Quem mexe |
|---|---|---|
| `design.json` | O grafo (nós, arquivos ligados, relações, regras) | A interface e a IA (via `--import`) |
| `CONTEXT.md` | **Índice curto** do jogo: regras e uma linha por nó. Todo agente lê | Gerado automaticamente |
| `nodes/<nome>.md` | **Detalhe de cada nó**: passos, arquivos, árvore da cena, o que muda entre as variações, tabela de valores | Gerado automaticamente |
| `ARCHITECTURE.md` | Classes, cenas e recursos do projeto | Gerado automaticamente |
| `index.json` | Todos os dados lidos dos arquivos | Gerado automaticamente |

Dica: coloque `gamegraph-out/` no git para a equipe inteira compartilhar o mesmo mapa.

## 12. Por que isso economiza tokens
- **O `CONTEXT.md` é curto de propósito.** Ele é lido em toda sessão, então tem só o índice. O detalhe fica em `nodes/<nome>.md`, e o agente lê **só o do processo da tarefa**.
- **O agente não precisa explorar o projeto.** O arquivo do nó já diz quais arquivos abrir. Sem isso, um agente costuma gastar dezenas de milhares de tokens com buscas e leituras só para entender o padrão.
- **"Faça como o Goblin" já vem pronto.** Para um script base, o arquivo do nó lista o que **cada variação muda**: funções sobrescritas, funções novas e valores exportados. Para um `.tres`, mostra uma **tabela com os valores** de todos os recursos do mesmo tipo (vida, dano, velocidade), pronta para balancear. A IA não precisa abrir 10 arquivos para descobrir isso.
- **Ler é direto, sem ferramenta.** Os arquivos ficam prontos em disco, então o agente não precisa rodar nenhum comando para obter contexto.
- **Atualizar é incremental.** O `--update` só relê o que mudou.

## 13. Como medir se está valendo a pena
Não confie, meça. Escolha uma tarefa real e repetível, como *"crie um inimigo novo parecido com o Goblin, que ataca à distância"*, e rode duas vezes, cada uma em uma sessão nova do Claude Code:
1. **Sem GameGraph:** renomeie temporariamente `gamegraph-out/` e tire a linha do `CLAUDE.md`.
2. **Com GameGraph:** tudo no lugar.

Anote em cada rodada:
| | Sem | Com |
|---|---|---|
| Tokens gastos (veja `/cost` ou o uso da sessão) | | |
| Tempo até terminar | | |
| Quantas correções você precisou pedir | | |
| Seguiu o padrão do projeto? (herança, .tres, registro) | | |

O ganho principal costuma ser nas **correções**: menos retrabalho. Se o "com" não ganhar, revise os processos. Provavelmente estão genéricos demais.

## 14. Perguntas frequentes
**Ficou lento / "travado".** O comando sem `--no-serve` sobe a interface e fica rodando até você apertar Ctrl+C. Isso é normal. Se o Claude ficar esperando, peça para ele rodar em segundo plano.

**A porta 8765 está ocupada.** Use `--port 8766` ou feche o GameGraph anterior.

**Os cartões ficaram bagunçados.** Clique em **Organizar**.

**A IA apagou o que eu fiz?** Não. Nós editados por você ficam marcados como "✔ Editado por você" e nunca são sobrescritos. Nós apagados não voltam.

**Funciona com C#?** Os arquivos `.cs` aparecem na lista e no viewer, mas a análise detalhada é só de GDScript.

**E arquivos `.res` / `.scn` binários?** Aparecem na lista, mas não são lidos. Salve como `.tres` / `.tscn` no Godot para inspecionar.
