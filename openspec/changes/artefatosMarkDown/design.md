# Design

## Contexto

Projeto novo, sem código. A motivação está em `proposal.md` e os comportamentos esperados estão nas specs (`captura-scan`, `ranking-similaridade`, `catalogo-itens`, `interface-scanner`, `comparacao-imagens`, `camera-dispositivos`). Restrições que moldam o desenho:

- Aplicativo desktop, executado localmente, com webcam e sem servidor.
- Backend majoritariamente em Python.
- Deve rodar em CPU comum, sem exigir GPU.
- Rostos e objetos precisam ser comparáveis no mesmo ranking.

## Objetivos / Fora de escopo

**Objetivos:**
- Pipeline único de captura, recorte, embedding e busca, usado tanto pelo scanner quanto pelo seed.
- Ranking pronto em até 2 s após a janela de captura, com até 10.000 itens, em CPU.
- Interface que nunca trava durante a captura ou o processamento.

**Fora de escopo:**
- Identificação biométrica: o sistema mede semelhança visual, não responde "quem é esta pessoa".
- Sincronização entre máquinas, contas de usuário e controle de acesso.
- Treinamento ou ajuste fino de modelos. Só são usados modelos pré-treinados.

## Arquitetura

```
  +------------------------- Aplicativo (PySide6) --------------------------+
  |                                                                         |
  |  [Thread câmera] --frames--> [GUI: preview + moldura]                   |
  |        |                                                                |
  |        | (durante o scan: n frames)                                     |
  |        v                                                                |
  |  [Worker de processamento]                                              |
  |    qualidade -> detecção de rosto -> recorte -> embedding (por frame)   |
  |        |                                                                |
  |        v  (fim dos 5 s)                                                 |
  |    agregação -> busca -> % calibrada -> top 10 --> [GUI: resultados]    |
  |        |                                                                |
  |        v                                                                |
  |    regra dos 90% -> (consentimento se rosto) -> inserção no catálogo    |
  +-------------------------------------------------------------------------+
                    |                                   ^
                    v                                   |
           +------------------+              +--------------------+
           | SQLite           |              | CLI de seed        |
           | itens, imagens,  |              | seed/<item>/*.jpg  |
           | vetores          |              | (mesmo pipeline)   |
           +------------------+              +--------------------+
           | data/images/...  |
           +------------------+
```

Os módulos ficam em um pacote Python único: `captura`, `qualidade`, `recorte`, `embedding`, `catalogo`, `ranking`, `calibracao`, `gui` e `cli`. A GUI e a CLI usam os mesmos módulos de pipeline.

## Decisões

### D1. Linguagem: Python 3.11+
Todo o pipeline de visão (OpenCV, PyTorch, ONNX Runtime) e a GUI (Qt) têm bibliotecas maduras em Python, então nenhuma outra linguagem traz vantagem relevante.
*Alternativas:* C++/Qt seria mais rápido, mas o gargalo é a inferência do modelo, que já roda em código nativo. Electron com backend Python acrescentaria um processo e IPC sem ganho.

### D2. GUI: PySide6 (Qt for Python)
Tem widgets maduros, licença LGPL, renderiza bem o vídeo da câmera em tempo real e oferece `QThread`/`QThreadPool` para manter a interface responsiva.
*Alternativas:* Tkinter (exibe vídeo com dificuldade e tem visual datado), Kivy (pensado para toque e com menos widgets prontos) e uma interface web local (desktop foi decisão explícita).

### D3. Câmera: OpenCV `VideoCapture` em thread dedicada
A thread lê frames continuamente para o preview. Durante o scan, amostra n frames espaçados uniformemente em 5 s (padrão n = 15, ou 3 fps). Os frames ficam só em memória.
*Alternativa:* QtMultimedia. É menos previsível entre sistemas operacionais, e o OpenCV já é necessário para o restante do pipeline.

### D4. Detecção de rosto: YuNet (`cv2.FaceDetectorYN`)
Modelo ONNX leve que roda em tempo real em CPU, vem integrado ao OpenCV e retorna caixa, landmarks e confiança.
*Alternativas:* Haar cascades (muitos falsos positivos), MediaPipe (dependência extra) e RetinaFace (pesado demais para CPU).

### D5. Recorte do objeto: a moldura da interface
Quando não há rosto, o recorte é a região da moldura exibida na tela de captura. A interface orienta o usuário a centralizar o objeto ali, o que torna o recorte determinístico e barato.
*Alternativa:* um detector de objetos (YOLO). Ele só reconhece classes pré-definidas, falharia com objetos fora delas e adicionaria um modelo.
Quando há rosto, o recorte é a caixa do YuNet com margem de 20%, alinhada pelos olhos.
No scan pela câmera, só conta um rosto cujo centro fica dentro da moldura. Um rosto fora dela (por exemplo, o de quem segura o objeto, ou alguém ao fundo) é ignorado: não vira o sujeito do scan e não invalida o frame como "rosto pequeno demais". No seed não há moldura na tela, então vale qualquer rosto da imagem.

### D6. Embedding: DINOv2 ViT-S/14
O mesmo modelo serve para rostos e objetos e gera vetores de 384 dimensões. O DINOv2 é treinado para similaridade visual fina entre instâncias (esta lata vs. aquela lata), justamente o que o ranking mede. A variante pequena (cerca de 21M parâmetros) roda em torno de 50 a 100 ms por imagem em CPU. A licença é Apache 2.0.
*Alternativas:* CLIP (mais semântico: aproxima "duas latas quaisquer", o que é pior para distinguir instâncias), ArcFace (só funciona para rostos e quebraria o ranking misto) e dois modelos com roteador (gera porcentagens não comparáveis entre si).
O modelo é carregado via PyTorch. Exportar para ONNX Runtime fica como otimização, caso a meta de tempo não seja atingida.

### D7. Embeddings calculados durante a captura
Cada frame amostrado é processado pelo worker enquanto a janela de 5 s ainda corre. Ao fim da janela, só faltam agregação e busca. É isso que viabiliza a meta de 2 s em CPU.
A thread da câmera numera cada frame novo. Se, no instante de uma amostra, o último frame já foi enviado (câmera lenta ou timers disparando juntos), a amostra espera o próximo frame em vez de repetir o anterior. Há uma folga de até 250 ms após os 5 s para a última amostra pendente.

### D8. Qualidade do frame
Um frame é válido se passa em todos estes critérios:
- nitidez (variância do Laplaciano acima de um limiar);
- brilho médio dentro de uma faixa;
- se houver rosto: confiança do detector de pelo menos 0,8 e lado mínimo de 80 px.

A pontuação de qualidade (nitidez normalizada) também ordena os frames para escolher os k melhores na inserção. Valores padrão: M = 5 frames válidos mínimos, k = 3 frames guardados. Todos os limiares ficam em `config.toml`.

### D9. Marcação "contém rosto"
O scan é marcado como "contém rosto" se mais da metade dos frames válidos teve rosto detectado. Na agregação, entram só os frames da classe majoritária, para não misturar recortes de rosto com recortes da moldura.

### D10. Agregação do scan
Cada vetor é normalizado (L2), a média é calculada e o resultado é normalizado de novo. A média de vetores normalizados é robusta a variações pequenas de pose e de luz.

### D11. Busca e agregação por item
Todos os vetores de imagens ficam em uma matriz NumPy em memória (10.000 itens × cerca de 5 imagens × 384 floats ≈ 77 MB), com um vetor de `item_id` em paralelo. A busca é um produto escalar (similaridade de cosseno) seguido de um agrupamento por item usando o máximo. O argmax por item fornece a "imagem mais parecida" exigida pela spec. Nessa escala, a força bruta leva milissegundos.
*Alternativas:* FAISS e bancos vetoriais só compensam com milhões de vetores. A média do top-3 por item foi descartada porque penaliza itens com uma única imagem, que é o caso de todos os itens criados por scan.

### D12. Calibração da porcentagem
A porcentagem é um mapeamento linear por partes do cosseno, com duas âncoras:
- `cos_zero`: similaridade típica entre itens não relacionados, mapeada para 0%;
- `cos_noventa`: similaridade típica entre duas capturas do mesmo item em condições diferentes, mapeada para 90%.

Entre 90% e 100%, a interpolação vai até cosseno 1,0. O resultado é limitado ao intervalo [0, 100].
As âncoras vêm de um script de calibração que roda sobre um conjunto rotulado de pares "mesmo item" e "itens diferentes", formado pelo próprio seed e por alguns scans de teste. `cos_zero` é a mediana dos pares diferentes, e `cos_noventa` é o percentil 10 dos pares iguais. Os valores ficam salvos em `config.toml`.
Por que linear por partes: é simples, explicável e fixa diretamente o ponto de 90%, que é onde a regra de inserção decide.

### D13. Armazenamento: SQLite + arquivos
- `itens(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, origem TEXT, criado_em)`
- `imagens(id, item_id, caminho, qualidade, vetor BLOB)`
- As imagens ficam em `data/images/<nome>/<n>.jpg`.

O `AUTOINCREMENT` do SQLite garante que um id nunca é reutilizado, nem depois de uma remoção. O nome do item de scan é `item-{id:06d}`. Itens de seed usam o nome da subpasta, que precisa ser único. Se o nome já existir, a CLI informa o conflito e pula a subpasta.
Na inicialização, a matriz em memória é montada a partir do SQLite. Inserções e remoções atualizam o banco e a matriz.

### D14. CLI de seed
`python -m scanner seed <pasta>` percorre as subpastas, aplica o mesmo pipeline de recorte e qualidade de D5 e D8 sobre as imagens estáticas e grava os itens com origem "seed". Ao final, imprime um relatório com os itens criados e as imagens ignoradas, cada uma com o motivo.

### D15. Concorrência na GUI
A thread de câmera emite frames por sinal. Os frames do scan vão para um worker em `QThreadPool`, e o resultado volta por sinal para a thread da GUI. Nenhuma inferência roda na thread da interface.

### D16. Ciclo de vida dos dados de um scan
Os frames e vetores de um scan vivem só em memória. Se o scan não for inserido (90% ou mais, consentimento recusado ou falha), as referências são descartadas e nada chega ao disco.

### D17. Adição manual de imagens pela interface
A tela de espera ganha o botão "Adicionar imagens", que abre um `QFileDialog` com seleção múltipla. Os arquivos vão para o mesmo worker do scan (D15). Cada um passa pelo pipeline do seed (D14): filtro de qualidade e recorte com a imagem inteira como "moldura", porque não há moldura na tela. As imagens válidas viram um único item gravado por `Catalogo.inserir_scan`, igual a um scan: origem "scan", nome `item-NNNNNN`, arquivos em `data/images/<nome>/<n>.jpg` e vetores no SQLite e na matriz em memória. Assim o item aparece na tela de remoção como qualquer item criado pelo aplicativo. Todas as imagens válidas são guardadas (não só as k melhores), porque o usuário as escolheu uma a uma. Não há regra dos 90% nem consentimento: é uma inserção deliberada de quem opera o aplicativo.
*Alternativa:* uma origem nova, "manual". Ela exigiria migrar a restrição `CHECK` da tabela `itens` nos bancos existentes, e a tela de remoção teria de listar duas origens, sem ganho para o fluxo atual.

### D18. Comparação de imagens com o catálogo
A tela de espera ganha o botão "Comparar imagens", que abre uma tela onde o usuário arrasta imagens (drag and drop) ou as escolhe por um `QFileDialog` de seleção múltipla. Os caminhos vão para o mesmo worker do scan (D15). O motor processa cada arquivo pelo pipeline da adição manual (D17): qualidade e recorte com a imagem inteira como moldura, valendo qualquer rosto.
As imagens válidas são agrupadas em ordem, por um agrupamento de líder com centroide: cada vetor entra no grupo, entre os já formados, cuja média normalizada seja a mais parecida, desde que a semelhança na escala calibrada (D12) atinja o mínimo de `[comparacao] similaridade_minima` (padrão 50%); senão, abre um grupo novo. Vence o grupo com mais imagens; em empate, o formado primeiro. A média normalizada do grupo vencedor é buscada no índice como o vetor de um scan (D11), e a regra dos 90% decide a inserção: abaixo disso, todas as imagens do grupo viram um item por `Catalogo.inserir_scan`, sem consentimento, por decisão do produto. Com 90% ou mais, nada é gravado.
O ranking aparece na mesma tela de resultados do scan, com um resumo (usadas, descartadas por qualidade e descartadas por estarem fora do grupo).
*Alternativas:* agrupamento por componentes conexas (encadeia imagens pouco parecidas por intermediárias) e k-médias (exige saber o número de grupos). O agrupamento de líder é simples, previsível e respeita a ordem das imagens, que define o desempate.

### D19. Câmera opcional e detecção de dispositivos
A câmera vira opcional. O módulo `dispositivos` lista os dispositivos de vídeo: no Linux, lê `/sys/class/video4linux`, usa o nome do dispositivo e mantém só os nós de captura (atributo `index` igual a 0; os nós de metadados de webcams UVC têm `index` 1); em outros sistemas, testa os índices de 0 a 9 com o OpenCV. A tela de espera ganha uma barra com a lista de dispositivos, um botão Ativar/Desativar e um botão para atualizar a lista. Ativar cria a thread da câmera (D3) para o dispositivo escolhido; desativar ou trocar encerra a thread e libera o dispositivo. Durante o scan, os controles ficam desabilitados, e sem câmera ativa o "Escanear" fica bloqueado.
A escolha (índice do dispositivo e estado) é gravada em `[camera]` no `config.toml` (`fonte` e `ativa`), preservando o resto do arquivo, e lida na abertura. Se o dispositivo guardado não aparecer na lista, o aplicativo abre com a câmera desativada. Uma fonte passada por `--camera` (vídeo ou pasta de imagens) entra na lista como uma opção a mais e não é gravada.

## Riscos / Trade-offs## Riscos / Trade-offs

- [O DINOv2 mede semelhança visual, não identidade: duas pessoas diferentes com luz e cabelo parecidos podem pontuar alto] → Aceito por design, já que o produto é de semelhança. O recorte justo do rosto (D5) reduz a influência do fundo.
- [Calibração mal ajustada torna a regra dos 90% inútil: tudo entra no catálogo ou nada entra] → Script de calibração com relatório da distribuição dos pares e âncoras configuráveis. Recalibrar depois de mudar o modelo.
- [A mesma pessoa, escaneada em dias diferentes, pode virar vários itens] → Aceito: a regra dos 90% reduz o efeito, mas não o elimina. A tela de remoção permite limpar duplicatas.
- [Scans ruins poluem o catálogo] → Filtro de qualidade (D8), mínimo de M frames e agregação por média.
- [Desempenho em CPUs fracas] → Embeddings calculados durante a captura (D7), modelo pequeno e, se preciso, exportação para ONNX Runtime ou redução de n.
- [Qualquer pessoa com acesso à máquina pode remover itens de scan] → Aceito no escopo local. Restringir o acesso exigiria mudar a spec `interface-scanner`.
- [Os pesos do modelo são baixados no primeiro uso, e o aplicativo não funciona offline na primeira execução] → Comando de preparação que baixa e guarda os pesos localmente antes do uso.
- [Imagens de rosto adicionadas manualmente não pedem consentimento (D17)] → Aceito por decisão do produto: a adição é feita por quem opera o aplicativo, as imagens ficam só nesta máquina e o item pode ser removido na tela de remoção.
- [Imagens de rosto inseridas pela comparação não pedem consentimento (D18)] → Aceito por decisão do produto: quem escolhe as imagens é quem opera o aplicativo, os dados ficam só nesta máquina e o item pode ser removido na tela de remoção.
- [O índice de um dispositivo pode mudar quando câmeras são conectadas em outra ordem (D19)] → A lista mostra o nome de cada dispositivo e a troca é feita pela interface; se o índice guardado não existir, o aplicativo abre com a câmera desativada.
- [LGPD: imagens de rosto de usuários] → Consentimento explícito com texto claro, armazenamento só local, remoção definitiva e nenhum frame persistido sem inserção (D16).

## Plano de implantação

1. Instalar as dependências (`pip install -e .` ou `uv sync`) e baixar os pesos dos modelos.
2. Montar a pasta `seed/` e rodar a CLI de seed.
3. Rodar o script de calibração e gravar as âncoras em `config.toml`.
4. Abrir o aplicativo.

Rollback: o catálogo inteiro está em `data/` (o arquivo SQLite e as imagens). Basta fazer backup ou apagar essa pasta.
