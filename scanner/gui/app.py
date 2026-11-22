"""Janela principal: liga câmera, trabalhador e telas no fluxo do scan."""

from __future__ import annotations

import sys
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from scanner.captura import EXTENSOES_IMAGEM, instantes_amostragem
from scanner.config import Config, atualizar_camera, carregar_config
from scanner.dispositivos import Dispositivo, listar_dispositivos
from scanner.gui.camera import ThreadCamera
from scanner.gui.telas import (
    DICA_FALHA,
    DialogoConsentimento,
    mensagem_sem_validas,
    resumo_busca,
    TelaCamera,
    TelaComparacao,
    TelaRemocao,
    TelaResultados,
)
from scanner.gui.tema import CORES, ESTILO, aplicar_tema  # noqa: F401 (ESTILO reexportado)
from scanner.gui.trabalhador import Trabalhador
from scanner.motor import Motor
from scanner.ranking import Decisao

MSG_PRONTO = "Centralize o rosto ou o objeto na moldura e clique em Escanear."
MSG_INSERIDO = "Novo item adicionado ao catálogo"
# Folga, após os 5 s, para uma amostra pendente receber o próximo frame da câmera.
ESPERA_FRAME_MS = 250
FILTRO_IMAGENS = "Imagens ({})".format(" ".join(f"*{e}" for e in sorted(EXTENSOES_IMAGEM)))
MAX_IGNORADAS_LISTADAS = 3


class Estado(Enum):
    CARREGANDO = auto()
    PRONTO = auto()
    CAPTURANDO = auto()
    PROCESSANDO = auto()
    ADICIONANDO = auto()
    COMPARACAO = auto()
    COMPARANDO = auto()
    RESULTADOS = auto()
    REMOCAO = auto()


_STATUS = {
    Estado.CARREGANDO: ("Carregando modelos…", "texto_mudo"),
    Estado.PRONTO: ("Pronto", "ciano"),
    Estado.CAPTURANDO: ("Capturando", "rosa"),
    Estado.PROCESSANDO: ("Processando", "rosa"),
    Estado.ADICIONANDO: ("Adicionando imagens", "rosa"),
    Estado.COMPARACAO: ("Comparar imagens", "ciano"),
    Estado.COMPARANDO: ("Comparando", "rosa"),
    Estado.RESULTADOS: ("Resultados", "ciano"),
    Estado.REMOCAO: ("Gerenciando itens", "texto_mudo"),
}


def _ponto(texto: str, cor: str) -> str:
    return f"<span style='color:{CORES[cor]}'>●</span>&nbsp; {texto}"


def mensagem_adicao(resultado) -> tuple[str, bool]:
    """Texto (e se é erro) informando o resultado de uma adição manual de imagens."""
    n = resultado.adicionadas
    if resultado.item is None:
        linhas = ["Nenhuma imagem válida: nada foi adicionado ao catálogo."]
    else:
        linhas = [f"{MSG_INSERIDO} com {n} {'imagem' if n == 1 else 'imagens'}."]
    ignoradas = resultado.ignoradas
    if ignoradas:
        partes = [f"{arq} ({motivo})" for arq, motivo in ignoradas[:MAX_IGNORADAS_LISTADAS]]
        resto = len(ignoradas) - MAX_IGNORADAS_LISTADAS
        if resto > 0:
            partes.append(f"e mais {resto}")
        rotulo = "Ignorada" if len(ignoradas) == 1 else "Ignoradas"
        linhas.append(f"{rotulo}: {', '.join(partes)}.")
    return "\n".join(linhas), resultado.item is None


class JanelaPrincipal(QMainWindow):
    _pedir_iniciar = Signal()
    _pedir_novo_scan = Signal()
    _pedir_processar = Signal(object)
    _pedir_concluir = Signal()
    _pedir_inserir = Signal(object)
    _pedir_descartar = Signal(object)
    _pedir_adicionar = Signal(object)
    _pedir_comparar = Signal(object)
    _pedir_encerrar = Signal()

    def __init__(
        self,
        cfg: Config,
        fonte,
        fabrica_motor=Motor.criar,
        listar=listar_dispositivos,
        salvar_camera: bool = False,
    ):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Scanner de similaridade visual")
        self.resize(1040, 780)
        self.estado = Estado.CARREGANDO
        self.motor_pronto = False
        self.camera_ok = False  # há uma câmera ativa entregando frames?
        self.camera: ThreadCamera | None = None
        self.dispositivos: list[Dispositivo] = []
        self._erro_status: str | None = None
        self.resultado_atual = None
        self.dialogo_consentimento: DialogoConsentimento | None = None
        self._timers_amostra: list[QTimer] = []
        self._seq_amostrado = -1  # último frame da câmera enviado no scan atual
        self._amostras_pendentes = 0  # amostras à espera de um frame novo

        self.tela_camera = TelaCamera(cfg.captura.moldura_fracao)
        self.tela_resultados = TelaResultados()
        self.tela_remocao = TelaRemocao()
        self.tela_comparacao = TelaComparacao()
        self.pilha = QStackedWidget()
        for tela in (self.tela_camera, self.tela_resultados, self.tela_remocao, self.tela_comparacao):
            self.pilha.addWidget(tela)
        self.pilha.currentChanged.connect(self._atualizar_secao)
        self._montar_moldura_da_janela()

        self.tela_camera.escanear.connect(self._iniciar_scan)
        self.tela_camera.gerenciar.connect(self._abrir_remocao)
        self.tela_camera.adicionar.connect(self._abrir_adicao)
        self.tela_resultados.novo_scan.connect(self._depois_dos_resultados)
        self.tela_remocao.voltar.connect(self._voltar_camera)
        self.tela_remocao.remover.connect(self._remover)
        self.tela_camera.comparar.connect(self._abrir_comparacao)
        self.tela_comparacao.escolher.connect(self._escolher_imagens_comparacao)
        self.tela_comparacao.comparar.connect(self._comparar)
        self.tela_comparacao.voltar.connect(self._voltar_camera)

        # Trabalhador: thread única para modelos, busca e catálogo.
        self._thread_trab = QThread(self)
        self.trabalhador = Trabalhador(cfg, fabrica_motor)
        self.trabalhador.moveToThread(self._thread_trab)
        self._pedir_iniciar.connect(self.trabalhador.iniciar)
        self._pedir_novo_scan.connect(self.trabalhador.novo_scan)
        self._pedir_processar.connect(self.trabalhador.processar)
        self._pedir_concluir.connect(self.trabalhador.concluir)
        self._pedir_inserir.connect(self.trabalhador.inserir)
        self._pedir_descartar.connect(self.trabalhador.descartar)
        self._pedir_adicionar.connect(self.trabalhador.adicionar_imagens)
        self._pedir_comparar.connect(self.trabalhador.comparar)
        self._pedir_encerrar.connect(self.trabalhador.encerrar)
        self.trabalhador.pronto.connect(self._motor_pronto)
        self.trabalhador.erro_fatal.connect(self._motor_falhou)
        self.trabalhador.concluido.connect(self._scan_concluido)
        self.trabalhador.falhou.connect(self._scan_falhou)
        self.trabalhador.inserido.connect(self._inserido)
        self.trabalhador.adicionado.connect(self._imagens_adicionadas)
        self.trabalhador.comparado.connect(self._comparado)
        self.trabalhador.erro.connect(self._erro)
        self._thread_trab.start()
        self._pedir_iniciar.emit()

        # Câmera: opcional, escolhida entre os dispositivos detectados.
        self._listar = listar
        self._salvar_camera = salvar_camera
        if isinstance(fonte, str) and fonte.isdigit():
            fonte = int(fonte)
        self.fonte_atual = fonte
        # Vídeo ou pasta de imagens (--camera) entra na lista como uma opção a mais.
        self._fonte_extra = None if isinstance(fonte, int) else fonte
        self.camera_ativa = bool(cfg.camera.ativa)
        self.tela_camera.camera_escolhida.connect(self._escolher_camera)
        self.tela_camera.alternar_camera.connect(self._alternar_camera)
        self.tela_camera.atualizar_cameras.connect(self._atualizar_cameras)
        self._recarregar_dispositivos()
        if not self.camera_ativa:
            self.tela_camera.camera_desativada()
        elif self.fonte_atual not in [d.fonte for d in self.dispositivos]:
            self.camera_ativa = False  # dispositivo guardado ausente: abre desativada
            self._erro_status = "Sem câmera"
            self.tela_camera.sem_camera(f"Câmera não encontrada ({self.fonte_atual})")
        else:
            self._ligar_camera()
        self._mostrar_dispositivos()

        self._relogio = QElapsedTimer()
        self._tique = QTimer(self)
        self._tique.setInterval(50)
        self._tique.timeout.connect(self._tique_captura)
        self._atualizar_botoes()
        self._atualizar_status()

    # ------------------------------------------------------- cabeçalho/status

    def _montar_moldura_da_janela(self) -> None:
        cabecalho = QFrame()
        cabecalho.setObjectName("cabecalho")
        marca = QLabel(
            f"<span style='color:{CORES['ciano']}'>scan</span>"
            f"<span style='color:{CORES['rosa']}'>ner</span>"
            f"<span style='color:{CORES['texto_mudo']}; font-weight:400'>"
            "&nbsp;&nbsp;similaridade visual</span>"
        )
        marca.setObjectName("marca")
        self.rotulo_secao = QLabel()
        self.rotulo_secao.setObjectName("secao")
        linha = QHBoxLayout(cabecalho)
        linha.setContentsMargins(20, 10, 20, 10)
        linha.addWidget(marca)
        linha.addStretch()
        linha.addWidget(self.rotulo_secao)

        central = QWidget()
        coluna = QVBoxLayout(central)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)
        coluna.addWidget(cabecalho)
        coluna.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        self.status_estado = QLabel()
        self.status_itens = QLabel()
        self.status_dispositivo = QLabel()
        barra = self.statusBar()
        barra.setSizeGripEnabled(False)
        barra.addWidget(self.status_estado)
        barra.addPermanentWidget(self.status_itens)
        barra.addPermanentWidget(self.status_dispositivo)
        self._atualizar_secao()

    def _atualizar_secao(self, *_):
        nomes = {
            self.tela_camera: "# câmera",
            self.tela_resultados: "# resultados",
            self.tela_remocao: "# gerenciar-itens",
            self.tela_comparacao: "# comparar-imagens",
        }
        self.rotulo_secao.setText(nomes.get(self.pilha.currentWidget(), ""))

    def _atualizar_status(self) -> None:
        if self._erro_status:
            self.status_estado.setText(_ponto(self._erro_status, "perigo"))
        else:
            texto, cor = _STATUS[self.estado]
            self.status_estado.setText(_ponto(texto, cor))
        motor = self.trabalhador.motor if self.motor_pronto else None
        if motor is None:
            self.status_itens.setText("")
            self.status_dispositivo.setText("")
            return
        n = motor.indice.total_itens
        self.status_itens.setText(f"{n} {'item' if n == 1 else 'itens'} no catálogo")
        dispositivo = getattr(getattr(motor.processador, "embedder", None), "dispositivo", "cpu")
        self.status_dispositivo.setText("GPU" if str(dispositivo).startswith("cuda") else "CPU")

    # ------------------------------------------------------------ estado geral

    def _atualizar_botoes(self) -> None:
        livre = self.estado == Estado.PRONTO and self.motor_pronto
        self.tela_camera.botao_escanear.setEnabled(
            livre and self.camera_ok and self.camera is not None
        )
        controles = self._controles_camera_livres()
        tem_dispositivo = bool(self.dispositivos)
        self.tela_camera.lista_cameras.setEnabled(controles and tem_dispositivo)
        self.tela_camera.botao_camera.setEnabled(controles and tem_dispositivo)
        self.tela_camera.botao_atualizar.setEnabled(controles)
        self.tela_camera.botao_gerenciar.setEnabled(livre)
        self.tela_camera.botao_adicionar.setEnabled(livre)  # não depende da câmera
        self.tela_camera.botao_comparar.setEnabled(livre)  # não depende da câmera

    def _mudar(self, estado: Estado) -> None:
        self.estado = estado
        self._atualizar_botoes()
        self._atualizar_status()

    def _motor_pronto(self) -> None:
        self.motor_pronto = True
        if self.camera_ok:
            self.tela_camera.info(MSG_PRONTO)
        self._mudar(Estado.PRONTO)

    def _motor_falhou(self, msg: str) -> None:
        self.tela_camera.info(f"Não foi possível iniciar: {msg}", erro=True)
        self._erro_status = "Erro ao iniciar"
        self._mudar(Estado.CARREGANDO)

    def _sem_camera(self, motivo: str, cam=None) -> None:
        if cam is not None and cam is not self.camera:
            return  # aviso de uma câmera que já foi trocada ou desligada
        if self.estado == Estado.CAPTURANDO:
            self._cancelar_captura()
        self._desligar_camera()
        self.camera_ativa = False  # o dispositivo não abre: a câmera fica desativada
        self._erro_status = "Sem câmera"
        self.tela_camera.sem_camera(motivo)
        self._mostrar_dispositivos()
        self._atualizar_status()

    # ------------------------------------------------------------- câmera

    def _controles_camera_livres(self) -> bool:
        return self.estado in (Estado.PRONTO, Estado.CARREGANDO)

    def _recarregar_dispositivos(self) -> None:
        lista = list(self._listar())
        if self._fonte_extra is not None and self._fonte_extra not in [d.fonte for d in lista]:
            nome = Path(str(self._fonte_extra)).name or str(self._fonte_extra)
            lista.append(Dispositivo(self._fonte_extra, f"Arquivo: {nome}"))
        # A câmera em uso sempre fica na lista (a sondagem pode não abrir uma câmera ocupada).
        if self.camera is not None and self.fonte_atual not in [d.fonte for d in lista]:
            lista.insert(0, Dispositivo(self.fonte_atual, f"Câmera {self.fonte_atual}"))
        self.dispositivos = lista

    def _mostrar_dispositivos(self) -> None:
        self.tela_camera.mostrar_dispositivos(self.dispositivos, self.fonte_atual, self.camera_ativa)
        self._atualizar_botoes()

    def _ligar_camera(self) -> None:
        cam = ThreadCamera(self.fonte_atual, parent=self)
        cam.frame_pronto.connect(lambda img, c=cam: self._frame(img, c))
        cam.indisponivel.connect(lambda motivo, c=cam: self._sem_camera(motivo, c))
        self.camera = cam
        self.camera_ok = True
        self._erro_status = None
        cam.start()

    def _desligar_camera(self) -> None:
        cam, self.camera = self.camera, None
        self.camera_ok = False
        if cam is not None:
            cam.parar()
            cam.deleteLater()

    def _guardar_camera(self) -> None:
        if self._salvar_camera and isinstance(self.fonte_atual, int) and self.cfg.caminho:
            atualizar_camera(self.cfg.caminho, self.fonte_atual, self.camera_ativa)

    def _mensagem_camera_ligada(self) -> None:
        self.tela_camera.info(MSG_PRONTO if self.motor_pronto else "Carregando modelos…")

    def _alternar_camera(self) -> None:
        if not self._controles_camera_livres():
            return
        if self.camera_ativa:
            self._desligar_camera()
            self.camera_ativa = False
            self._erro_status = None
            self.tela_camera.camera_desativada()
        else:
            if not self.dispositivos:
                return
            if self.fonte_atual not in [d.fonte for d in self.dispositivos]:
                self.fonte_atual = self.dispositivos[0].fonte
            self.camera_ativa = True
            self._ligar_camera()
            self._mensagem_camera_ligada()
        self._guardar_camera()
        self._mostrar_dispositivos()
        self._atualizar_status()

    def _escolher_camera(self, posicao: int) -> None:
        if not self._controles_camera_livres() or not 0 <= posicao < len(self.dispositivos):
            return
        fonte = self.dispositivos[posicao].fonte
        if fonte == self.fonte_atual:
            return
        self.fonte_atual = fonte
        if self.camera_ativa:
            self._desligar_camera()
            self._ligar_camera()
            self._mensagem_camera_ligada()
        self._guardar_camera()
        self._mostrar_dispositivos()
        self._atualizar_status()

    def _atualizar_cameras(self) -> None:
        if not self._controles_camera_livres():
            return
        self._recarregar_dispositivos()
        fontes = [d.fonte for d in self.dispositivos]
        if self.camera is None and self.fonte_atual not in fontes and fontes:
            self.fonte_atual = fontes[0]
        if self.camera is None and fontes:
            self._erro_status = None
            n = len(fontes)
            self.tela_camera.info(
                f"{n} câmera{'' if n == 1 else 's'} encontrada{'' if n == 1 else 's'}. "
                "Escolha na lista e clique em “Ativar” para usar."
            )
        self._mostrar_dispositivos()
        self._atualizar_status()

    def _frame(self, img, cam=None) -> None:
        if cam is not None and cam is not self.camera:
            return  # frame atrasado de uma câmera já trocada
        if self.pilha.currentWidget() is self.tela_camera:
            self.tela_camera.preview.mostrar(img)
        if self._amostras_pendentes and self.estado == Estado.CAPTURANDO:
            if self._enviar_amostra():
                self._amostras_pendentes -= 1

    # ---------------------------------------------------------------- captura

    def _iniciar_scan(self) -> None:
        if self.estado != Estado.PRONTO or not (self.motor_pronto and self.camera_ok and self.camera):
            return
        self._mudar(Estado.CAPTURANDO)
        self.tela_camera.preview.set_capturando(True)
        self._pedir_novo_scan.emit()
        self._seq_amostrado = -1
        self._amostras_pendentes = 0
        c = self.cfg.captura
        self._timers_amostra = []
        for t in instantes_amostragem(c.n_frames, c.duracao_s):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._amostrar)
            timer.start(int(t * 1000))
            self._timers_amostra.append(timer)
        self._relogio.start()
        self._tique.start()
        self._tique_captura()

    def _amostrar(self) -> None:
        if self.estado != Estado.CAPTURANDO:
            return
        if not self._enviar_amostra():
            # A câmera ainda não entregou um frame novo desde a última amostra
            # (câmera lenta ou timers disparando juntos). Em vez de repetir o
            # mesmo frame, a amostra sai no próximo frame exibido.
            self._amostras_pendentes += 1

    def _enviar_amostra(self) -> bool:
        """Envia o último frame da câmera, se ainda não foi enviado neste scan."""
        seq, frame = self.camera.ultimo_frame_numerado()
        if frame is None or seq == self._seq_amostrado:
            return False
        self._seq_amostrado = seq
        self._pedir_processar.emit(frame)
        return True

    def _tique_captura(self) -> None:
        total = int(self.cfg.captura.duracao_s * 1000)
        decorrido = min(self._relogio.elapsed(), total)
        self.tela_camera.progresso_captura(decorrido, total)
        esperando_frame = (
            self._amostras_pendentes > 0 and self._relogio.elapsed() < total + ESPERA_FRAME_MS
        )
        if (
            decorrido >= total
            and not any(t.isActive() for t in self._timers_amostra)
            and not esperando_frame
        ):
            self._tique.stop()
            self._fim_captura()

    def _fim_captura(self) -> None:
        self._amostras_pendentes = 0  # a janela de 5 s acabou
        self.tela_camera.preview.set_capturando(False)
        self._mudar(Estado.PROCESSANDO)
        self.tela_camera.processando()
        self._pedir_concluir.emit()

    def _cancelar_captura(self) -> None:
        self._tique.stop()
        for t in self._timers_amostra:
            t.stop()
        self._amostras_pendentes = 0
        self._pedir_novo_scan.emit()  # descarta frames já enviados
        self.tela_camera.preview.set_capturando(False)
        self.tela_camera.ocioso()
        self._mudar(Estado.PRONTO)

    # -------------------------------------------------------------- resultado

    def _scan_falhou(self, falha) -> None:
        self.tela_camera.ocioso()
        self.tela_camera.info(DICA_FALHA, erro=True)
        self._mudar(Estado.PRONTO)

    def _erro(self, msg: str) -> None:
        if self.estado == Estado.COMPARANDO:
            self.tela_comparacao.ocioso()
            self.tela_comparacao.info(msg, erro=True)
            self._mudar(Estado.COMPARACAO)
        elif self.estado in (Estado.PROCESSANDO, Estado.ADICIONANDO):
            self.tela_camera.ocioso()
            self.tela_camera.info(msg, erro=True)
            self._mudar(Estado.PRONTO)
        else:
            self.tela_resultados.avisar(msg)

    def _scan_concluido(self, resultado) -> None:
        self.resultado_atual = resultado
        self.tela_camera.ocioso()
        self.tela_resultados.mostrar(resultado.resultados)
        self.tela_resultados.definir_origem("scan")
        self.pilha.setCurrentWidget(self.tela_resultados)
        self._mudar(Estado.RESULTADOS)
        scan = resultado.scan
        if resultado.decisao == Decisao.DESCARTAR:
            self._pedir_descartar.emit(scan)
        elif resultado.decisao == Decisao.INSERIR:
            self._pedir_inserir.emit(scan)
        else:
            dialogo = DialogoConsentimento(self)
            dialogo.accepted.connect(lambda: self._pedir_inserir.emit(scan))
            dialogo.rejected.connect(lambda: self._pedir_descartar.emit(scan))
            dialogo.finished.connect(lambda _: setattr(self, "dialogo_consentimento", None))
            self.dialogo_consentimento = dialogo
            dialogo.open()

    def _inserido(self, item) -> None:
        self.tela_resultados.avisar(MSG_INSERIDO)
        self._atualizar_status()

    def _depois_dos_resultados(self) -> None:
        if self.tela_resultados.origem == "comparacao":
            self.resultado_atual = None
            self.tela_comparacao.limpar()
            self.pilha.setCurrentWidget(self.tela_comparacao)
            self._mudar(Estado.COMPARACAO)
        else:
            self._voltar_camera()

    def _voltar_camera(self) -> None:
        self.resultado_atual = None
        self.pilha.setCurrentWidget(self.tela_camera)
        if self.camera_ok:
            self.tela_camera.info(MSG_PRONTO)
        elif not self.camera_ativa and self._erro_status is None:
            self.tela_camera.camera_desativada()
        self._mudar(Estado.PRONTO)

    # ------------------------------------------------------- adição manual
    def _abrir_adicao(self) -> None:
        if self.estado != Estado.PRONTO or not self.motor_pronto:
            return
        caminhos = self._escolher_arquivos()
        if caminhos:
            self._adicionar_arquivos(caminhos)

    def _escolher_arquivos(self) -> list[str]:
        caminhos, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar imagens ao catálogo", str(Path.home()), FILTRO_IMAGENS
        )
        return caminhos

    def _adicionar_arquivos(self, caminhos) -> None:
        self._mudar(Estado.ADICIONANDO)
        self.tela_camera.processando()
        self._pedir_adicionar.emit(list(caminhos))

    def _imagens_adicionadas(self, resultado) -> None:
        self.tela_camera.ocioso()
        texto, erro = mensagem_adicao(resultado)
        self.tela_camera.info(texto, erro=erro)
        self._mudar(Estado.PRONTO)

    # ------------------------------------------------- comparação de imagens

    def _abrir_comparacao(self) -> None:
        if self.estado != Estado.PRONTO or not self.motor_pronto:
            return
        self.tela_comparacao.limpar()
        self.pilha.setCurrentWidget(self.tela_comparacao)
        self._mudar(Estado.COMPARACAO)

    def _escolher_arquivos_comparacao(self) -> list[str]:
        caminhos, _ = QFileDialog.getOpenFileNames(
            self, "Imagens de um mesmo objeto", str(Path.home()), FILTRO_IMAGENS
        )
        return caminhos

    def _escolher_imagens_comparacao(self) -> None:
        if self.estado != Estado.COMPARACAO:
            return
        caminhos = self._escolher_arquivos_comparacao()
        if caminhos:
            self.tela_comparacao.adicionar(caminhos)

    def _comparar(self) -> None:
        tela = self.tela_comparacao
        if self.estado != Estado.COMPARACAO or not tela.caminhos:
            return
        self._mudar(Estado.COMPARANDO)
        tela.processando()
        self._pedir_comparar.emit(list(tela.caminhos))

    def _comparado(self, r) -> None:
        self.tela_comparacao.ocioso()
        if not r.valido:
            self.tela_comparacao.info(mensagem_sem_validas(r), erro=True)
            self._mudar(Estado.COMPARACAO)
            return
        self.resultado_atual = r
        self.tela_resultados.mostrar(r.resultados)
        self.tela_resultados.definir_origem("comparacao", resumo_busca(r))
        if r.item is not None:
            self.tela_resultados.avisar(MSG_INSERIDO)
        self.pilha.setCurrentWidget(self.tela_resultados)
        self._mudar(Estado.RESULTADOS)

    # ---------------------------------------------------------------- remoção

    def _abrir_remocao(self) -> None:
        if self.estado != Estado.PRONTO or not self.motor_pronto:
            return
        self.tela_remocao.mostrar(self.trabalhador.motor.itens_scan())
        self.pilha.setCurrentWidget(self.tela_remocao)
        self._mudar(Estado.REMOCAO)

    def _remover(self, item_id: int) -> None:
        self.trabalhador.motor.remover(item_id)
        self.tela_remocao.mostrar(self.trabalhador.motor.itens_scan())
        self._atualizar_status()

    # ------------------------------------------------------------ encerramento

    def closeEvent(self, evento) -> None:
        self._tique.stop()
        for t in self._timers_amostra:
            t.stop()
        self._desligar_camera()
        self._pedir_encerrar.emit()
        self._thread_trab.quit()
        self._thread_trab.wait(5000)
        super().closeEvent(evento)


def executar(caminho_config: Path | None, camera=None) -> int:
    cfg = carregar_config(caminho_config)
    fonte = camera if camera is not None else cfg.camera.fonte
    # Nome usado pelo sistema para identificar a janela no painel (WM_CLASS / app id).
    QApplication.setApplicationName("Scanner")
    QApplication.setDesktopFileName("scanner-similaridade")
    app = QApplication.instance() or QApplication(sys.argv)
    aplicar_tema(app)
    janela = JanelaPrincipal(cfg, fonte, salvar_camera=True)
    janela.show()
    return app.exec()
