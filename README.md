# Scanner de similaridade visual

Aplicativo desktop que, em uma janela de 5 segundos, captura o rosto ou o objeto
diante da webcam e mostra os 10 itens mais parecidos de um catálogo local, com a
porcentagem de similaridade de cada um. Scans suficientemente novos (1º colocado
abaixo de 90%) viram itens do catálogo.

## Requisitos

- Python 3.11 ou mais recente
- Webcam (opcional: sem câmera, só o scan fica indisponível)
- Cerca de 1,5 GB livres em disco (PyTorch para CPU e pesos dos modelos)
- Acesso à internet só na instalação e no `preparar`. Depois disso, tudo roda offline.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e . --extra-index-url https://download.pytorch.org/whl/cpu
```

O `--extra-index-url` instala o PyTorch só para CPU, que é bem menor. Se você tiver
uma GPU NVIDIA e quiser usá-la, omita essa opção. O aplicativo usa a GPU
automaticamente quando ela está disponível.

## Preparar os modelos

```bash
python -m scanner preparar
```

Baixa para a pasta `models/` os pesos do detector de rostos (YuNet, cerca de 0,2 MB)
e do modelo de embedding (DINOv2 ViT-S/14, cerca de 88 MB). Rodar de novo não baixa
nada que já esteja presente.

## Catálogo inicial (seed)

O catálogo começa com itens inseridos manualmente, pessoas públicas ou objetos, a
partir de uma pasta com **uma subpasta por item**:

```
seed/
  pele/
    1.jpg
    2.jpg
    perfil.png
  lata-coca/
    frente.jpg
    lado.jpg
```

- O nome da subpasta vira o nome interno do item. Nomes no formato `item-NNNNNN`
  são reservados para itens criados pelo scanner.
- Formatos aceitos: `.jpg`, `.jpeg`, `.png`, `.bmp` e `.webp`. Outros arquivos são ignorados.
- Cada imagem passa pelo mesmo filtro de qualidade e pelo mesmo recorte do scanner.
  Se houver rosto, o recorte é o rosto. Senão, é o maior quadrado central da
  imagem, então centralize o objeto nas fotos.
- Imagens inválidas (borradas, escuras demais, com rosto pequeno demais) são
  ignoradas e listadas no relatório. Subpastas sem nenhuma imagem válida não
  geram item.
- Rodar o seed de novo é seguro: itens que já existem são pulados.

Importe com:

```bash
python -m scanner seed seed/
```

Exemplo de relatório:

```
[criado] lata-coca: 2 de 2 imagem(ns)
  [ignorada] pele/perfil.png: borrado
[criado] pele: 2 de 3 imagem(ns)
Seed concluído: 2 item(ns) criado(s).
```

Para experimentar sem fotos próprias, `python -m tests.seed_exemplo seed/` gera
uma pasta de exemplo com 4 itens a partir das imagens de teste.

## Calibração da porcentagem

A porcentagem exibida não é o cosseno bruto do modelo. Ela vem de um mapeamento
com duas âncoras, guardadas em `config.toml`, seção `[calibracao]`:

- `cos_zero`: similaridade típica entre itens diferentes, exibida como **0%**;
- `cos_noventa`: similaridade típica entre duas fotos do mesmo item, exibida como **90%**.

A regra de inserção decide no ponto de 90%, então calibre depois do seed:

```bash
python -m scanner calibrar
```

O comando compara todos os pares de imagens do catálogo, mostra as distribuições
e grava as âncoras no `config.toml`. Ele exige pelo menos 2 itens e pelo menos um
item com 2 ou mais imagens. Quanto mais o seed se parecer com o que a webcam vai
ver (luz, distância, fundo), melhor fica a calibração. Recalibre sempre que o
catálogo inicial mudar bastante.

## Uso

```bash
python -m scanner            # ou: python -m scanner app
```

1. A tela inicial mostra o preview da câmera com uma **moldura**. Centralize o rosto
   ou o objeto nela e clique em **Escanear**. Só conta o que está na moldura: um rosto
   cujo centro fica fora dela (por exemplo, o de quem segura o objeto) é ignorado.
2. Durante **5 segundos** o aplicativo captura vários frames (a contagem aparece na
   tela). Fique parado e com boa iluminação.
3. A tela de resultados mostra os **10 itens mais parecidos**, só com imagem e
   porcentagem, sem nomes.
4. Se o 1º colocado tiver **menos de 90%**, o scan vira um novo item:
   - **objeto**: é adicionado automaticamente, com o aviso "Novo item adicionado ao catálogo";
   - **rosto**: o aplicativo pede **consentimento** antes. Se você recusar, nada é guardado.
5. Com 90% ou mais, o scan é descartado e nada é gravado.
6. Se o scan falhar (frames borrados, escuros ou sem sujeito), aparece "Tente novamente".

**Adicionar imagens** cria um item a partir de arquivos, sem passar pelo scanner.
Escolha uma ou mais imagens do mesmo rosto ou objeto (`.jpg`, `.jpeg`, `.png`, `.bmp`
ou `.webp`). Cada uma passa pelo mesmo filtro de qualidade e recorte do seed, e as
válidas viram **um único item**, guardado como um item de scan: nome `item-NNNNNN` e
imagens em `data/images/item-NNNNNN/`. Todas as imagens válidas são guardadas, sem a
regra dos 90% e sem pedido de consentimento. As imagens ignoradas aparecem na mensagem,
com o motivo. O botão funciona mesmo sem câmera.

**Comparar imagens** busca no catálogo a partir de fotos, sem câmera, como se fosse
um scan:

1. Clique em **Comparar imagens** na tela inicial (funciona mesmo sem câmera).
2. **Arraste** para a área tracejada uma ou mais fotos **de um mesmo objeto**, ou use
   **Escolher imagens…**. Arquivos que não são imagem são ignorados, e fotos repetidas
   não entram duas vezes. **Limpar** esvazia a lista.
3. Clique em **Comparar**. Antes da busca, o aplicativo valida as fotos:
   - descarta as de baixa qualidade (borradas, escuras, ilegíveis), com o motivo;
   - agrupa as válidas por semelhança: cada foto entra no grupo mais parecido, se a
     semelhança atingir o mínimo (`[comparacao] similaridade_minima`, padrão **50%**);
     senão, forma um grupo novo;
   - usa o **maior grupo**; em empate, o **primeiro formado**. As fotos dos outros
     grupos são descartadas como diferentes do grupo escolhido.
4. A tela de resultados mostra o **top 10** do catálogo, com um resumo das fotos usadas
   e descartadas.
5. Se o 1º colocado ficar **abaixo de 90%**, as fotos do grupo viram **um novo item**
   (nome `item-NNNNNN`), **sem pedido de consentimento**, mesmo que sejam de um rosto.
   Com 90% ou mais, nada é gravado.
6. **Nova comparação** volta para a tela de comparação, vazia.

### Câmera

A câmera é opcional. A barra no topo da tela inicial tem:

- a **lista de câmeras** detectadas, com o nome de cada uma (no Linux, nós que só
  entregam metadados são ignorados);
- **Ativar/Desativar**: liga ou libera a câmera. Desativada, o preview mostra
  "Câmera desativada";
- **Atualizar lista**: procura de novo as câmeras, por exemplo depois de conectar uma.

Escolher outra câmera na lista troca o preview na hora. Sem câmera ativa, **Escanear**
fica desabilitado; **Adicionar imagens**, **Comparar imagens** e **Gerenciar itens**
continuam funcionando. Durante um scan, os controles de câmera ficam travados.

A câmera escolhida e o estado (ativa ou não) ficam gravados em `[camera]` no
`config.toml` e são usados na próxima abertura. Se a câmera gravada não estiver
conectada, o aplicativo abre com a câmera desativada.

**Gerenciar itens** lista os itens criados pelo aplicativo (por scan ou por
**Adicionar imagens**) e permite removê-los definitivamente. Os itens do catálogo
inicial não aparecem nessa tela.

Um vídeo ou uma pasta de imagens também servem de fonte, o que é útil para testes.
Eles entram na lista de câmeras como uma opção a mais e não são gravados no config:

```bash
python -m scanner app --camera 1
python -m scanner app --camera video.mp4
python -m scanner app --camera pasta-de-imagens/
```

## Configuração (`config.toml`)

| Seção | Chave | Padrão | Significado |
|---|---|---|---|
| `camera` | `fonte` | `0` | índice da câmera escolhida (gravado pelo aplicativo) |
| | `ativa` | `true` | se a câmera começa ligada (gravado pelo aplicativo) |
| `comparacao` | `similaridade_minima` | `50.0` | semelhança mínima (%) para duas fotos da comparação contarem como o mesmo objeto |
| `captura` | `duracao_s` | `5.0` | duração da janela de captura |
| | `n_frames` | `15` | frames amostrados na janela |
| | `min_frames_validos` | `5` | mínimo de frames válidos para o scan não falhar |
| | `moldura_fracao` | `0.6` | lado da moldura / menor lado do frame |
| `qualidade` | `nitidez_min` | `25.0` | variância mínima do Laplaciano |
| | `brilho_min`, `brilho_max` | `40`, `220` | faixa de brilho aceita |
| | `rosto_confianca_min` | `0.8` | confiança mínima do detector de rosto |
| | `rosto_lado_min_px` | `80` | tamanho mínimo do rosto |
| `catalogo` | `diretorio_dados` | `data` | banco SQLite e imagens |
| | `imagens_por_item` | `3` | frames guardados quando um scan vira item |
| `ranking` | `top` | `10` | itens exibidos |
| | `limiar_insercao` | `90.0` | % do 1º colocado a partir da qual o scan é descartado |
| `calibracao` | `cos_zero`, `cos_noventa` | `0.0`, `0.7` | âncoras da % (use `calibrar`) |
| `modelos` | `diretorio` | `models` | pesos baixados pelo `preparar` |

Caminhos relativos são resolvidos a partir da pasta do `config.toml`. Para usar
outro arquivo, passe `python -m scanner --config outro.toml <comando>`.

## Privacidade

- Frames de scans que não viram item ficam só na memória e nunca são gravados.
- Rostos escaneados só entram no catálogo com consentimento explícito, e o texto avisa
  que a imagem poderá aparecer para outras pessoas.
- Imagens escolhidas em **Adicionar imagens** ou em **Comparar imagens** (abaixo de 90%)
  entram sem pedido de consentimento: quem as escolhe é quem opera o aplicativo.
- Tudo fica nesta máquina, em `data/`. Itens criados por scan podem ser removidos
  em **Gerenciar itens**. Para apagar o catálogo inteiro, apague a pasta `data/`.

## Testes

```bash
pip install -e ".[dev]" --extra-index-url https://download.pytorch.org/whl/cpu
python -m scanner preparar      # testes com modelos são pulados sem os pesos
pytest
```

Os testes da interface rodam sem tela (`QT_QPA_PLATFORM=offscreen`) e usam pastas
de imagens no lugar da webcam.

## Estrutura

```
scanner/
  captura.py     fonte de frames, processamento por frame, agregação do scan
  qualidade.py   filtro de nitidez e brilho
  recorte.py     detecção de rosto (YuNet) e recortes (rosto / moldura)
  embedding.py   DINOv2 ViT-S/14 -> vetor de 384 dimensões
  catalogo.py    SQLite + imagens, seed, inserção e remoção
  ranking.py     índice em memória, top 10 por item, regra de inserção
  calibracao.py  escala cosseno -> % e comando calibrar
  comparacao.py  agrupamento por semelhança das fotos da comparação
  dispositivos.py  detecção das câmeras disponíveis
  motor.py       fachada usada pela interface
  gui/           janela, telas, tema escuro, thread da câmera e trabalhador
  cli.py         comandos app, preparar, seed, calibrar
```
