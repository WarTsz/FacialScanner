"""Detector de dispositivos de vídeo e gravação da câmera escolhida (9.1)."""

from scanner.config import atualizar_camera, carregar_config
from scanner.dispositivos import Dispositivo, listar_dispositivos


def _no(raiz, nome, rotulo, indice):
    d = raiz / nome
    d.mkdir(parents=True)
    (d / "name").write_text(rotulo + "\n")
    (d / "index").write_text(f"{indice}\n")


def test_lista_so_nos_de_captura_com_nome(tmp_path):
    raiz = tmp_path / "video4linux"
    _no(raiz, "video0", "Brio 100", 0)
    _no(raiz, "video1", "Brio 100", 1)  # metadados
    _no(raiz, "video10", "Placa de captura", 0)
    _no(raiz, "video2", "HD Webcam", 0)
    _no(raiz, "video3", "HD Webcam", 1)
    (raiz / "v4l-subdev0").mkdir()
    lista = listar_dispositivos(raiz)
    assert lista == [
        Dispositivo(0, "Brio 100"),
        Dispositivo(2, "HD Webcam"),
        Dispositivo(10, "Placa de captura"),
    ]
    assert lista[0].rotulo == "Brio 100 (câmera 0)"


def test_nome_ausente_vira_generico(tmp_path):
    raiz = tmp_path / "video4linux"
    (raiz / "video4").mkdir(parents=True)
    assert listar_dispositivos(raiz) == [Dispositivo(4, "Câmera 4")]


def test_lista_vazia(tmp_path):
    raiz = tmp_path / "video4linux"
    raiz.mkdir()
    assert listar_dispositivos(raiz) == []


def test_sem_sysfs_sonda_os_indices(tmp_path):
    abertos = {0, 3}
    lista = listar_dispositivos(tmp_path / "nao-existe", sondar=lambda i: i in abertos, max_indice=5)
    assert lista == [Dispositivo(0, "Câmera 0"), Dispositivo(3, "Câmera 3")]


def test_rotulo_de_arquivo():
    assert Dispositivo("/videos/teste.mp4", "teste.mp4").rotulo == "teste.mp4"


def test_gravar_camera_preserva_o_resto(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text(
        "# comentário\n[camera]\n# Índice da webcam\nfonte = 0\nativa = true\n\n[ranking]\ntop = 7\n",
        encoding="utf-8",
    )
    atualizar_camera(arq, 2, False)
    texto = arq.read_text(encoding="utf-8")
    assert "# comentário" in texto and "# Índice da webcam" in texto
    cfg = carregar_config(arq)
    assert cfg.camera.fonte == 2 and cfg.camera.ativa is False
    assert cfg.ranking.top == 7


def test_gravar_camera_cria_secao_e_aceita_caminho(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text("[ranking]\ntop = 7\n", encoding="utf-8")
    atualizar_camera(arq, 'C:\\videos\\"teste".mp4', True)
    cfg = carregar_config(arq)
    assert cfg.camera.fonte == 'C:\\videos\\"teste".mp4' and cfg.camera.ativa is True
    assert cfg.ranking.top == 7


def test_ativa_padrao_e_verdadeiro(tmp_path):
    assert carregar_config(tmp_path / "nada.toml").camera.ativa is True


def test_detecta_a_webcam_desta_maquina_sem_abrir():
    # Smoke test no sistema real: só lê o sysfs, não abre a câmera.
    lista = listar_dispositivos()
    assert all(isinstance(d.fonte, int) for d in lista)
