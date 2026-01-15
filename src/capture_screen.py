import subprocess
import io
import os
from PIL import Image

ADB_SERIAL = "127.0.0.1:5585"   # ajuste se necessário

def take_screenshot(output_path="screen.png"):
    """
    Captura uma screenshot do dispositivo Android.
    
    Args:
        output_path: Caminho do arquivo de saída. Se relativo, salva na raiz do projeto.
    
    Returns:
        bool: True se sucesso, False caso contrário
    """
    # Se o caminho for relativo, salva na raiz do projeto
    if not os.path.isabs(output_path):
        project_root = os.path.dirname(os.path.dirname(__file__))
        output_path = os.path.join(project_root, output_path)
    
    # executa screencap
    result = subprocess.run(
        ["adb", "-s", ADB_SERIAL, "exec-out", "screencap", "-p"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        print("Erro ao capturar screenshot:", result.stderr.decode(errors='ignore'))
        return False

    # converte bytes → imagem → salva arquivo
    try:
        img = Image.open(io.BytesIO(result.stdout))
        img.save(output_path)
        print(f"Screenshot salva como {output_path}")
        return True
    except Exception as e:
        print("Falha ao processar imagem:", e)
        return False


if __name__ == "__main__":
    take_screenshot("screen.png")
