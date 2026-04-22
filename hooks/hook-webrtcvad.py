from PyInstaller.utils.hooks import copy_metadata


try:
    datas = copy_metadata("webrtcvad-wheels")
except Exception:
    datas = []
