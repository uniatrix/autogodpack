import subprocess, time, os, logging, json, threading
from PIL import Image
import io
import cv2
import numpy as np

# Thread-local storage for ADB_SERIAL to support multiple bot instances
# Each thread will have its own adb_serial value, preventing conflicts when multiple bots run simultaneously
_thread_local = threading.local()

# Legacy global variable for backward compatibility (deprecated)
# Note: This is only used as a fallback if thread-local storage is not set
ADB_SERIAL = "127.0.0.1:5585"

def get_adb_serial():
    """Get ADB_SERIAL from thread-local storage, fallback to global if not set."""
    if hasattr(_thread_local, 'adb_serial'):
        return _thread_local.adb_serial
    return ADB_SERIAL

def set_adb_serial(serial):
    """Set ADB_SERIAL in thread-local storage for current thread."""
    _thread_local.adb_serial = serial
    # Also update global for backward compatibility (but thread-local takes precedence)
    global ADB_SERIAL
    ADB_SERIAL = serial

def get_slot_id():
    """Get slot_id from thread-local storage, fallback to None if not set."""
    if hasattr(_thread_local, 'slot_id'):
        return _thread_local.slot_id
    return None

def set_slot_id(slot_id):
    """Set slot_id in thread-local storage for current thread."""
    _thread_local.slot_id = slot_id

def get_bot_prefix():
    """Get bot prefix for logging (e.g., '[Bot 1]' or '' if no slot_id)."""
    slot_id = get_slot_id()
    if slot_id is not None:
        return f"[Bot {slot_id + 1}] "
    return ""

# Tipo de automação para battle
AUTOMATION_TYPE = "battle"

# Diretório base de templates organizado por tipo de automação
# Try new location first (autogodpack/templates), fallback to old (src/templates)
_project_root = os.path.dirname(os.path.dirname(__file__))
_new_template_base = os.path.join(_project_root, "autogodpack", "templates")
_old_template_base = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(_new_template_base):
    TEMPLATE_BASE_DIR = _new_template_base
else:
    TEMPLATE_BASE_DIR = _old_template_base

TEMPLATE_DIR = os.path.join(TEMPLATE_BASE_DIR, AUTOMATION_TYPE)

# Diretórios de templates por tela (para battle) - Clean structure
BATTLE_SELECTION_DIR = os.path.join(TEMPLATE_DIR, "battle_selection")
BATTLE_SETUP_DIR = os.path.join(TEMPLATE_DIR, "battle_setup")
BATTLE_IN_PROGRESS_DIR = os.path.join(TEMPLATE_DIR, "battle_in_progress")
RESULT_DIR = os.path.join(TEMPLATE_DIR, "result")
REWARDS_DIR = os.path.join(TEMPLATE_DIR, "rewards")
SUMMARY_DIR = os.path.join(TEMPLATE_DIR, "summary")
POPUP_NEW_BATTLE_DIR = os.path.join(TEMPLATE_DIR, "popup_new_battle")
DEFEAT_DIR = os.path.join(TEMPLATE_DIR, "defeat")
DEFEAT_POPUP_DIR = os.path.join(TEMPLATE_DIR, "defeat_popup")
EXPANSION_SELECTION_DIR = os.path.join(TEMPLATE_DIR, "expansion_selection")
SERIES_A_DIR = os.path.join(EXPANSION_SELECTION_DIR, "series_a")
SERIES_B_DIR = os.path.join(EXPANSION_SELECTION_DIR, "series_b")
CLOSE_BUTTON_DIR = os.path.join(EXPANSION_SELECTION_DIR, "close_button")
SERIES_SWITCH_DIR = os.path.join(EXPANSION_SELECTION_DIR, "series")

# Legacy aliases for backward compatibility (will be removed later)
SCREEN_1_BATTLE_SELECTION_DIR = BATTLE_SELECTION_DIR
SCREEN_2_BATTLE_SETUP_DIR = BATTLE_SETUP_DIR
SCREEN_3_VICTORY_DIR = RESULT_DIR
SCREEN_4_5_6_DIR = REWARDS_DIR
SCREEN_7_DIR = SUMMARY_DIR
SCREEN_8_DIR = POPUP_NEW_BATTLE_DIR
SCREEN_DEFEAT_DIR = DEFEAT_DIR
SCREEN_DEFEAT_POPUP_DIR = DEFEAT_POPUP_DIR
SELECT_EXPANSION_DIR = EXPANSION_SELECTION_DIR

# Ordem das expansões para verificação
EXPANSIONS_SERIES_A = ["GA", "MI", "STS", "TL", "SR", "CG", "EC", "EG", "WSS", "SS", "DPex"]
EXPANSIONS_SERIES_B = ["MR", "CB"]

# Arquivo para armazenar expansões completas
COMPLETED_EXPANSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "completed_expansions.json")

# Cria pasta logs se não existir
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOGFILE = os.path.join(LOG_DIR, "battle_bot.log")

logging.basicConfig(
    level=logging.INFO,
    filename=LOGFILE,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logging.getLogger().addHandler(console)

def adb_cmd(args, capture_output=True):
    adb_serial = get_adb_serial()
    cmd = ["adb", "-s", adb_serial] + args
    return subprocess.run(cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE
    )

def screenshot_bgr():
    adb_serial = get_adb_serial()
    p = adb_cmd(["exec-out", "screencap", "-p"])
    if p.returncode != 0:
        stderr = p.stderr.decode('utf-8', errors='ignore') if p.stderr else "Unknown error"
        logging.error(f"Screenshot capture failed (device={adb_serial}): {stderr}")
        return None
    try:
        if not p.stdout:
            logging.error(f"Empty screenshot received (device={adb_serial})")
            return None
        img = Image.open(io.BytesIO(p.stdout))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        logging.error(f"Failed to process screenshot: {e}")
        return None

# Template cache for performance optimization
_template_cache = {}
_template_mtime_cache = {}

def _load_template_cached(template_path):
    """Load template with caching to reduce disk I/O."""
    # Check if template is cached and still valid
    if template_path in _template_cache:
        try:
            current_mtime = os.path.getmtime(template_path)
            if current_mtime == _template_mtime_cache.get(template_path, 0):
                return _template_cache[template_path]
        except OSError:
            # File might have been deleted, remove from cache
            _template_cache.pop(template_path, None)
            _template_mtime_cache.pop(template_path, None)
    
    # Load template from disk
    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None:
        return None
    
    # Cache template
    try:
        mtime = os.path.getmtime(template_path)
        _template_cache[template_path] = tpl
        _template_mtime_cache[template_path] = mtime
    except OSError:
        pass  # Cache without mtime if can't get it
    
    return tpl

def find_template(screen, template_path, threshold=0.82, verbose=True):
    """
    Procura um template na tela usando template matching.
    Usa cache para reduzir operações de I/O e melhorar performance.
    
    Args:
        screen: Imagem BGR da tela
        template_path: Caminho para o template
        threshold: Threshold de correspondência (0.0 a 1.0)
        verbose: Se True, loga quando encontra o template (deprecated - not used anymore)
    
    Returns:
        tuple: (x, y) se encontrado, None caso contrário
    """
    tpl = _load_template_cached(template_path)
    if tpl is None:
        # Only log errors for missing templates
        return None

    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxval, _, maxloc = cv2.minMaxLoc(res)
    
    if maxval >= threshold:
        h, w = tpl.shape[:2]
        cx = maxloc[0] + w//2
        cy = maxloc[1] + h//2
        # Removed verbose logging - too noisy
        return (cx, cy)

    return None

def tap(x, y):
    """Executa um tap na coordenada especificada e verifica se foi bem-sucedido"""
    x_int = int(x)
    y_int = int(y)
    # Removed debug logging - too verbose
    
    result = adb_cmd(["shell", "input", "tap", str(x_int), str(y_int)], capture_output=True)
    
    if result.returncode == 0:
        # Removed debug logging - too verbose
        time.sleep(0.3)
        return True
    else:
        stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
        # Only log errors, not debug info
        return False

def swipe(x1, y1, x2, y2, duration_ms=500):
    """
    Executa um swipe (arrastar) na tela.
    
    Args:
        x1, y1: Coordenadas de início
        x2, y2: Coordenadas de fim
        duration_ms: Duração do swipe em milissegundos
    
    Returns:
        bool: True se sucesso, False caso contrário
    """
    x1_int = int(x1)
    y1_int = int(y1)
    x2_int = int(x2)
    y2_int = int(y2)
    
    # Removed debug logging - too verbose
    
    result = adb_cmd(["shell", "input", "swipe", str(x1_int), str(y1_int), str(x2_int), str(y2_int), str(duration_ms)], capture_output=True)
    
    if result.returncode == 0:
        # Removed debug logging - too verbose
        time.sleep(0.3)
        return True
    else:
        # Only log critical errors
        return False

def scroll_down(slow_mode=False):
    """
    Rola a tela para baixo clicando e arrastando no meio das bordas da tela.
    Usa o meio horizontal e arrasta de baixo para cima para rolar para baixo.
    
    Args:
        slow_mode: Se True, usa scroll mais lento (útil para expansões)
    
    Returns:
        bool: True se sucesso, False caso contrário
    """
    screen = screenshot_bgr()
    if screen is None:
        logging.error("Could not capture screenshot to determine screen dimensions")
        return False
    
    screen_height, screen_width = screen.shape[:2]
    
    # Calcula pontos no meio das bordas laterais (vertical center, edges)
    center_x = screen_width // 2
    start_y = int(screen_height * 0.7)  # Começa em 70% da altura (parte inferior visível)
    end_y = int(screen_height * 0.3)    # Termina em 30% da altura (parte superior)
    
    # Usa duração maior para scroll mais lento em modo slow
    duration_ms = 1000 if slow_mode else 500
    
    # Removed debug logging - too verbose
    return swipe(center_x, start_y, center_x, end_y, duration_ms=duration_ms)

def get_template_path(filename, screen_dir=None):
    """Retorna o caminho completo do template, considerando a pasta da tela e tipo de automação"""
    if screen_dir:
        return os.path.join(screen_dir, filename)
    return os.path.join(TEMPLATE_DIR, filename)

def detect_current_battle_screen(verbose=True):
    """
    Detecta qual tela do battle bot está atualmente sendo exibida.
    
    Args:
        verbose: Se True, loga informações detalhadas sobre a detecção
    
    Returns:
        str: Nome da tela detectada ('battle_selection', 'select_expansion', 'battle_setup', 
             'battle_in_progress', 'result_screen', 'screens_4_5_6', 'screen_7', 'screen_8', 
             ou None se não reconhecida)
    """
    # Removed initial detection log - too verbose
    screen = screenshot_bgr()
    if screen is None:
        # Only log critical errors
        return None
    
    # Verifica cada tela em ordem de prioridade (da mais específica para a menos específica)
    detected_templates = []
    
    # Screen 8: Pop-up OK (mais específico - aparece sobre outras telas)
    ok_path = get_template_path("ok.png", SCREEN_8_DIR)
    if os.path.exists(ok_path):
        ok_pos = find_template(screen, ok_path, threshold=0.75, verbose=False)
        if ok_pos:
            logging.info(f"{get_bot_prefix()}Page: Popup OK (Screen 8)")
            return "screen_8"
        detected_templates.append(("ok.png", False))
    
    # Screen Defeat Popup: Defeat popup with Back button
    back_path = get_template_path("back.png", SCREEN_DEFEAT_POPUP_DIR)
    if os.path.exists(back_path):
        back_pos = find_template(screen, back_path, threshold=0.75, verbose=False)
        if back_pos:
            logging.info(f"{get_bot_prefix()}Page: Defeat Popup")
            return "defeat_popup"
        detected_templates.append(("back.png", False))
    
    # Screen 7: Next button
    next_path = get_template_path("next.png", SCREEN_7_DIR)
    if os.path.exists(next_path):
        next_pos = find_template(screen, next_path, threshold=0.75, verbose=False)
        if next_pos:
            logging.info(f"{get_bot_prefix()}Page: Summary (Screen 7)")
            return "screen_7"
        detected_templates.append(("next.png", False))
    
    # Screen Defeat: Defeat screen
    defeat_path = get_template_path("defeat.png", SCREEN_DEFEAT_DIR)
    if os.path.exists(defeat_path):
        defeat_pos = find_template(screen, defeat_path, threshold=0.75, verbose=False)
        if defeat_pos:
            logging.info(f"{get_bot_prefix()}Page: Defeat")
            return "defeat_screen"
        detected_templates.append(("defeat.png", False))
    
    # Select Expansion Screen: Tela de seleção de expansões
    # Verifica se alguma expansão está visível (qualquer uma serve como indicador)
    # Prioridade alta: verifica antes de outras telas para evitar falsos positivos
    # IMPORTANTE: Expansões também podem aparecer em screen_1_battle_selection, então verifica primeiro
    # se está na tela de seleção de expansões (com botão X/close) antes de considerar battle_selection
    close_x_path = os.path.join(CLOSE_BUTTON_DIR, "close_x.png")
    has_close_button = False
    if os.path.exists(close_x_path):
        close_pos = find_template(screen, close_x_path, threshold=0.75, verbose=False)
        if close_pos:
            has_close_button = True
    
    # If close button exists, definitely on expansion selection screen
    if has_close_button:
        logging.info(f"{get_bot_prefix()}Page: Expansion Selection")
        return "select_expansion"
    
    # Verifica se alguma expansão está visível (mas só considera select_expansion se não for battle_selection)
    for expansion in EXPANSIONS_SERIES_A + EXPANSIONS_SERIES_B:
        exp_path = None
        if expansion in EXPANSIONS_SERIES_A:
            exp_path = os.path.join(SERIES_A_DIR, f"{expansion}.png")
        else:
            exp_path = os.path.join(SERIES_B_DIR, f"{expansion}.png")
        
        if os.path.exists(exp_path):
            pos = find_template(screen, exp_path, threshold=0.75, verbose=False)
            if pos:
                # Se encontrou expansão mas também tem botão Expansions, está em battle_selection
                # Se não tem botão Expansions, está em select_expansion
                expansions_path = get_template_path("expansions.png", SCREEN_1_BATTLE_SELECTION_DIR)
                has_expansions_button = False
                if os.path.exists(expansions_path):
                    expansions_pos = find_template(screen, expansions_path, threshold=0.75, verbose=False)
                    if expansions_pos:
                        has_expansions_button = True
                
                if not has_expansions_button:
                    # No Expansions button, so it's select_expansion screen
                    logging.info(f"{get_bot_prefix()}Page: Expansion Selection")
                    return "select_expansion"
        else:
            # Log apenas se verbose e template não existe (para debug)
            if verbose:
                detected_templates.append((f"{expansion}.png (não existe)", False))
    
    # Screen 1: Battle Selection (expansions button - indicador principal)
    # IMPORTANTE: Verificar ANTES de battle_setup para evitar falsos positivos
    expansions_pos = None
    expansions_path = get_template_path("expansions.png", SCREEN_1_BATTLE_SELECTION_DIR)
    if os.path.exists(expansions_path):
        expansions_pos = find_template(screen, expansions_path, threshold=0.75, verbose=False)
        if expansions_pos:
            logging.info(f"{get_bot_prefix()}Page: Battle Selection")
            return "battle_selection"
        detected_templates.append(("expansions.png", False))
    
    # Battle In Progress: Opponent ou put_basic_pokemon (detecta quando está em batalha)
    # Usa verbose=False para não logar repetidamente durante a batalha
    opponent_path = get_template_path("opponent.png", BATTLE_IN_PROGRESS_DIR)
    put_basic_path = get_template_path("put_basic_pokemon.png", BATTLE_IN_PROGRESS_DIR)
    opponent_pos = None
    put_basic_pos = None
    
    if os.path.exists(opponent_path):
        opponent_pos = find_template(screen, opponent_path, threshold=0.75, verbose=False)
        detected_templates.append(("opponent.png", opponent_pos is not None))
    
    if os.path.exists(put_basic_path):
        put_basic_pos = find_template(screen, put_basic_path, threshold=0.75, verbose=False)
        detected_templates.append(("put_basic_pokemon.png", put_basic_pos is not None))
    
    if opponent_pos or put_basic_pos:
        logging.info(f"{get_bot_prefix()}Page: Battle In Progress")
        return "battle_in_progress"
    
    # Screen 2: Battle Setup (REQUER auto.png para evitar falsos positivos)
    # Só verifica se NÃO encontrou Expansions (para evitar detectar Screen 1 como Screen 2)
    # IMPORTANTE: Exige que auto.png esteja presente, pois battle.png pode aparecer em outras telas
    auto_path = get_template_path("auto.png", SCREEN_2_BATTLE_SETUP_DIR)
    battle_path = get_template_path("battle.png", SCREEN_2_BATTLE_SETUP_DIR)
    auto_pos = None
    battle_pos = None
    if os.path.exists(auto_path):
        auto_pos = find_template(screen, auto_path, threshold=0.75)
        detected_templates.append(("auto.png", auto_pos is not None))
    if os.path.exists(battle_path):
        battle_pos = find_template(screen, battle_path, threshold=0.75)
        detected_templates.append(("battle.png", battle_pos is not None))
    
    # Só considera Screen 2 se encontrou auto.png (obrigatório) E não encontrou Expansions
    # battle.png é opcional, mas auto.png é necessário para confirmar que está na tela correta
    if auto_pos and expansions_pos is None:
        logging.info(f"{get_bot_prefix()}Page: Battle Setup")
        return "battle_setup"
    
    # Screens 4-5-6: Tap to Proceed
    tap_4_5_6_path = get_template_path("tap_to_proceed.png", SCREEN_4_5_6_DIR)
    if os.path.exists(tap_4_5_6_path):
        tap_4_5_6_pos = find_template(screen, tap_4_5_6_path, threshold=0.75, verbose=False)
        if tap_4_5_6_pos:
            logging.info(f"{get_bot_prefix()}Page: Rewards (Screens 4-5-6)")
            return "screens_4_5_6"
        detected_templates.append(("tap_to_proceed (4-5-6)", False))
    
    # Screen 3: Result Screen (victory/defeat) - Tap to Proceed
    tap_result_path = get_template_path("tap_to_proceed.png", SCREEN_3_VICTORY_DIR)
    if os.path.exists(tap_result_path):
        tap_result_pos = find_template(screen, tap_result_path, threshold=0.75, verbose=False)
        if tap_result_pos:
            logging.info(f"{get_bot_prefix()}Page: Result Screen")
            return "result_screen"
        detected_templates.append(("tap_to_proceed (result)", False))
    
    # Screen 1: Battle Selection (hourglass - secondary indicator)
    hourglass_path = get_template_path("hourglass.png", SCREEN_1_BATTLE_SELECTION_DIR)
    if os.path.exists(hourglass_path):
        hourglass_pos = find_template(screen, hourglass_path, threshold=0.75, verbose=False)
        if hourglass_pos:
            logging.info(f"{get_bot_prefix()}Page: Battle Selection")
            return "battle_selection"
        detected_templates.append(("hourglass.png", False))
    
    # Removed verbose logging for unknown screens - too noisy
    # Only log if it's a critical issue
    return None

def find_hourglass(max_scrolls=3):
    """
    Procura pelo ícone de ampulheta (hourglass) na tela.
    Se não encontrar, tenta rolar para baixo até encontrar ou atingir o limite de scrolls.
    
    Args:
        max_scrolls: Número máximo de scrolls para baixo antes de desistir (padrão: 3)
    
    Returns:
        tuple: (x, y) se encontrado, None caso contrário
    """
    hourglass_path = get_template_path("hourglass.png", SCREEN_1_BATTLE_SELECTION_DIR)
    
    if not os.path.exists(hourglass_path):
        logging.error(f"Template hourglass.png not found at {hourglass_path}")
        logging.error("Please ensure hourglass.png exists in templates/battle/battle_selection/")
        return None
    
    scroll_count = 0
    
    while scroll_count <= max_scrolls:
        # Check stop flag in loop
        if check_stop_flag():
            return None
        
        screen = screenshot_bgr()
        if screen is None:
            time.sleep(0.6)  # Slightly longer wait on screenshot failure
            continue
        
        # Search for hourglass on current screen
        pos = find_template(screen, hourglass_path, threshold=0.75, verbose=False)
        
        if pos:
            return pos
        
        # If not found and can still scroll, scroll down
        if scroll_count < max_scrolls:
            # Check stop flag before scrolling
            if check_stop_flag():
                return None
            
            # Removed debug logging - too verbose
            if scroll_down():
                time.sleep(0.6)  # Wait for screen to stabilize after scroll (increased from 0.5)
            # Removed warning logging - too verbose
            scroll_count += 1
        else:
            # Removed warning logging - too verbose
            break
    
    return None

def wait_and_tap_template(filename, timeout=10, threshold=0.75, screen_dir=None, fast_mode=False):
    """
    Aguarda um template aparecer na tela e então executa um tap nele.
    
    Args:
        filename: Nome do arquivo do template
        timeout: Tempo máximo de espera em segundos
        threshold: Threshold de correspondência (0.0 a 1.0)
        screen_dir: Diretório da tela onde o template está (opcional)
        fast_mode: Se True, usa delays menores para execução mais rápida
    
    Returns:
        bool: True se encontrou e clicou, False caso contrário
    """
    path = get_template_path(filename, screen_dir)
    end = time.time() + timeout
    attempts = 0
    
    # Delays ajustados para modo rápido - otimizados para menos CPU
    check_interval = 0.2 if fast_mode else 0.5  # Aumentado para reduzir frequência de checks
    tap_delay = 0.2 if fast_mode else 1.0
    retry_delay = 0.15 if fast_mode else 0.5
    
    while time.time() < end:
        # Check stop flag in wait loop
        if check_stop_flag():
            return False
        
        attempts += 1
        screen = screenshot_bgr()
        if screen is None:
            time.sleep(0.3)  # Slightly longer wait on screenshot failure
            continue
        
        pos = find_template(screen, path, threshold=threshold, verbose=False)
        if pos:
            # Removed verbose logging - too noisy
            if tap(pos[0], pos[1]):
                time.sleep(tap_delay)  # Wait for action to take effect
                return True
            else:
                # Removed debug logging - too verbose
                time.sleep(retry_delay)
                continue
        
        # Optimized interruptible sleep - check less frequently to reduce CPU overhead
        sleep_remaining = check_interval
        check_interval_sleep = 0.2  # Increased from 0.05 to reduce overhead
        while sleep_remaining > 0:
            if check_stop_flag():
                return False
            actual_sleep = min(check_interval_sleep, sleep_remaining)
            time.sleep(actual_sleep)
            sleep_remaining -= actual_sleep
    
    # Only log critical failures
    return False

def handle_battle_setup_screen():
    """
    Processa a tela de configuração de batalha (após selecionar o hourglass).
    
    Fluxo:
    1. Verifica se está na tela intermediária (put_basic_pokemon) - se sim, aguarda Auto colocar Pokémon
    2. Verifica se o Auto está Off (procura pelo template auto.png)
    3. Se estiver Off, liga o Auto (clica no botão Auto)
    4. VERIFICA que Auto está ON antes de prosseguir (auto.png não deve estar visível)
    5. Só então clica no botão Battle!
    6. Aguarda a próxima tela
    """
    # Removed initial log - too verbose
    
    screen = screenshot_bgr()
    if screen is None:
        return False
    
    # Check if Auto is OFF
    auto_path = get_template_path("auto.png", SCREEN_2_BATTLE_SETUP_DIR)
    
    # Look for Auto button (when OFF)
    auto_pos = None
    if os.path.exists(auto_path):
        auto_pos = find_template(screen, auto_path, threshold=0.75, verbose=False)
    
    # If Auto is OFF, turn it ON
    if auto_pos:
        # Removed verbose logging
        if not tap(auto_pos[0], auto_pos[1]):
            return False
        time.sleep(0.5)  # Wait for toggle to take effect
        
        # Verify Auto was enabled (auto.png should no longer be visible)
        verification_screen = screenshot_bgr()
        if verification_screen is None:
            return False
        
        auto_still_off = find_template(verification_screen, auto_path, threshold=0.75, verbose=False)
        if auto_still_off:
            return False
        # Removed debug logging
    
    # Verify Auto is ON before clicking Battle
    if os.path.exists(auto_path):
        final_check_screen = screenshot_bgr()
        if final_check_screen is None:
            return False
        
        auto_off_check = find_template(final_check_screen, auto_path, threshold=0.75, verbose=False)
        if auto_off_check:
            # Only log critical errors
            if not tap(auto_off_check[0], auto_off_check[1]):
                return False
            time.sleep(0.5)
            
            # Verify again after second attempt
            final_check_screen2 = screenshot_bgr()
            if final_check_screen2 is None:
                return False
            
            auto_off_check2 = find_template(final_check_screen2, auto_path, threshold=0.75, verbose=False)
            if auto_off_check2:
                return False
            # Removed verbose logging
        # Removed debug logging
    
    # Now that Auto is confirmed ON, find and click Battle button
    battle_path = get_template_path("battle.png", SCREEN_2_BATTLE_SETUP_DIR)
    if not os.path.exists(battle_path):
        # Only log critical errors
        return False
    
    # Removed verbose logging
    if not wait_and_tap_template("battle.png", timeout=10, threshold=0.75, screen_dir=SCREEN_2_BATTLE_SETUP_DIR):
        return False
    
    # Wait for transition to next screen
    # Removed debug logging
    time.sleep(1.0)
    
    # Removed verbose logging
    return True

def _get_slot_id_from_serial():
    """Get slot ID from thread-local storage, or calculate from ADB_SERIAL port number (5585=0, 5586=1, etc.)"""
    # First check if slot_id is set in thread-local storage (from new system)
    thread_local_slot_id = get_slot_id()
    if thread_local_slot_id is not None and 0 <= thread_local_slot_id <= 3:
        return thread_local_slot_id
    
    # Fallback to calculating from port (for backward compatibility)
    try:
        adb_serial = get_adb_serial()
        if ':' in adb_serial:
            port = int(adb_serial.split(':')[1])
            slot_id = port - 5585
            if 0 <= slot_id <= 3:
                return slot_id
    except (ValueError, IndexError):
        pass
    return 0  # Default to slot 0

def load_completed_expansions():
    """Load completed expansions list from JSON file (supports multi-bot format)"""
    slot_id = _get_slot_id_from_serial()
    
    if os.path.exists(COMPLETED_EXPANSIONS_FILE):
        try:
            with open(COMPLETED_EXPANSIONS_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    logging.debug("Completed expansions file is empty, starting fresh")
                    return set()
                data = json.loads(content)
                
                # Check if it's multi-bot format
                if "bots" in data:
                    bots_data = data.get("bots", {})
                    # Convert 0-indexed internal slot_id to 1-indexed for JSON lookup
                    json_slot_id = slot_id + 1
                    slot_str = str(json_slot_id)
                    if slot_str in bots_data:
                        bot_data = bots_data[slot_str]
                        completed_list = bot_data.get("completed", [])
                        logging.debug(f"Loaded {len(completed_list)} completed expansions for slot {slot_id} (bot {json_slot_id})")
                        return set(completed_list)
                    else:
                        logging.debug(f"No data found for slot {slot_id} (bot {json_slot_id}), returning empty set")
                        return set()
                else:
                    # Legacy format - return as-is (for backward compatibility)
                    logging.debug("Using legacy format, loading all expansions")
                    return set(data.get('completed', []))
        except json.JSONDecodeError as e:
            logging.warning(f"Error parsing completed expansions JSON: {e}")
            logging.info("Initializing file with empty structure...")
            save_completed_expansions(set())
            return set()
        except Exception as e:
            logging.warning(f"Error loading completed expansions: {e}")
            return set()
    return set()

def save_completed_expansions(completed_set):
    """Save completed expansions list to JSON file (supports multi-bot format)"""
    slot_id = _get_slot_id_from_serial()
    
    try:
        # Load existing multi-bot state if file exists
        existing_data = {}
        if os.path.exists(COMPLETED_EXPANSIONS_FILE):
            try:
                with open(COMPLETED_EXPANSIONS_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        existing_data = json.loads(content)
            except (json.JSONDecodeError, Exception):
                pass
        
        # Ensure multi-bot format
        if "bots" not in existing_data:
            # Convert legacy format to multi-bot format
            if "completed" in existing_data:
                # Legacy format - convert to multi-bot (legacy is bot 1, internal slot 0)
                legacy_completed = existing_data.pop("completed", [])
                existing_data = {"bots": {"1": {"completed": legacy_completed}}}  # 1-indexed in JSON
            else:
                existing_data = {"bots": {}}
        
        # Ensure bots dict exists
        if "bots" not in existing_data:
            existing_data["bots"] = {}
        
        # Convert 0-indexed internal slot_id to 1-indexed for JSON
        json_slot_id = slot_id + 1
        slot_str = str(json_slot_id)
        existing_data["bots"][slot_str] = {"completed": list(completed_set)}
        
        # Sort bots by ID for consistent ordering (1, 2, 3, 4)
        sorted_bots = dict(sorted(existing_data["bots"].items(), key=lambda x: int(x[0])))
        existing_data["bots"] = sorted_bots
        
        # Save updated data
        with open(COMPLETED_EXPANSIONS_FILE, 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        logging.debug(f"Saved {len(completed_set)} completed expansions for slot {slot_id}")
    except Exception as e:
        logging.error(f"Error saving completed expansions: {e}")

def reset_completed_expansions():
    """Reset completed expansions list"""
    completed_set = set()
    save_completed_expansions(completed_set)
    logging.info(f"{get_bot_prefix()}Completed expansions reset")

def detect_expansion_selection_screen(screen=None):
    """
    Detecta se está na tela de seleção de expansões.
    Verifica se há templates de expansões visíveis na tela.
    Esta função é usada para verificação adicional quando necessário.
    
    Args:
        screen: Imagem BGR da tela (opcional, se None captura uma nova)
    
    Returns:
        bool: True se está na tela de seleção de expansões
    """
    if screen is None:
        screen = screenshot_bgr()
        if screen is None:
            return False
    
    # Verifica se alguma expansão está visível (qualquer uma serve como indicador)
    # Tenta todas as expansões para garantir detecção confiável
    found_expansions = []
    for expansion in EXPANSIONS_SERIES_A + EXPANSIONS_SERIES_B:
        exp_path = None
        if expansion in EXPANSIONS_SERIES_A:
            exp_path = os.path.join(SERIES_A_DIR, f"{expansion}.png")
        else:
            exp_path = os.path.join(SERIES_B_DIR, f"{expansion}.png")
        
        if os.path.exists(exp_path):
            pos = find_template(screen, exp_path, threshold=0.75, verbose=False)
            if pos:
                found_expansions.append(expansion)
                # Se encontrou pelo menos uma, está na tela de seleção de expansões
                return True
    
    return False

def tap_expansions_button():
    """
    Clica no botão "Expansions" na tela de seleção de batalhas.
    
    Returns:
        bool: True se conseguiu clicar, False caso contrário
    """
    logging.info(f"{get_bot_prefix()}Clicking Expansions button...")
    expansions_path = get_template_path("expansions.png", SCREEN_1_BATTLE_SELECTION_DIR)
    
    if not os.path.exists(expansions_path):
        logging.error(f"Template expansions.png not found at {expansions_path}")
        return False
    
    if not wait_and_tap_template("expansions.png", timeout=5, threshold=0.75, screen_dir=SCREEN_1_BATTLE_SELECTION_DIR):
        logging.error("Failed to find or click Expansions button")
        return False
    
    time.sleep(1.0)  # Wait for transition to expansion selection screen
    return True

def find_expansion_in_screen(expansion_name, series, max_scrolls=8):
    """
    Procura por uma expansão específica na tela de seleção de expansões.
    Faz scroll se necessário para encontrar a expansão.
    
    Args:
        expansion_name: Nome da expansão (ex: "GA", "MI", etc.)
        series: "A" ou "B"
        max_scrolls: Número máximo de scrolls para baixo antes de desistir
    
    Returns:
        tuple: (x, y) se encontrado, None caso contrário
    """
    exp_path = None
    if series == "A":
        exp_path = os.path.join(SERIES_A_DIR, f"{expansion_name}.png")
    else:
        exp_path = os.path.join(SERIES_B_DIR, f"{expansion_name}.png")
    
    if not os.path.exists(exp_path):
        logging.error(f"Template {expansion_name}.png not found at {exp_path}")
        return None
    
    scroll_count = 0
    
    # First check current screen WITHOUT scrolling
    screen = screenshot_bgr()
    if screen is None:
        logging.warning("Could not capture screenshot")
        return None
    
    pos = find_template(screen, exp_path, threshold=0.75, verbose=False)
    if pos:
        # Removed verbose logging - too noisy
        return pos
    
    # If not found, scroll until found or limit reached
    # Uses slow_mode=True for slower scroll to allow images to load
    while scroll_count < max_scrolls:
        # Check stop flag in scroll loop
        if check_stop_flag():
            return None
        
        # Removed debug logging - too verbose
        if not scroll_down(slow_mode=True):
            # Removed warning logging - too verbose
            break
        
        time.sleep(0.8)  # Wait longer after slow scroll for screen to stabilize
        
        screen = screenshot_bgr()
        if screen is None:
            # Removed warning logging - too verbose
            scroll_count += 1
            continue
        
        # Search for expansion on current screen after scroll
        pos = find_template(screen, exp_path, threshold=0.75, verbose=False)
        
        if pos:
            # Removed verbose logging - too noisy
            return pos
        
        scroll_count += 1
    
    # If not found after all scrolls, try resetting: click X then Expansions
    # Then try again with scroll (max 2 reset attempts)
    max_reset_attempts = 2
    for reset_attempt in range(max_reset_attempts):
        # Removed verbose logging - too noisy
        
        # Look for X (close) button
        close_x_path = os.path.join(CLOSE_BUTTON_DIR, "close_x.png")
        if not os.path.exists(close_x_path):
            # Removed warning logging - too verbose
            break
        
        screen = screenshot_bgr()
        if screen is None:
            # Removed warning logging - too verbose
            break
        
        close_pos = find_template(screen, close_x_path, threshold=0.75, verbose=False)
        if not close_pos:
            # Removed warning logging - too verbose
            break
        
        # Removed verbose logging
        if not tap(close_pos[0], close_pos[1]):
            # Removed warning logging - too verbose
            break
        
        time.sleep(1.0)  # Wait for close
        
        # Now click Expansions button to return
        expansions_path = get_template_path("expansions.png", SCREEN_1_BATTLE_SELECTION_DIR)
        if not os.path.exists(expansions_path):
            # Removed warning logging - too verbose
            break
        
        screen_after_close = screenshot_bgr()
        if screen_after_close is None:
            # Removed warning logging - too verbose
            break
        
        expansions_pos = find_template(screen_after_close, expansions_path, threshold=0.75, verbose=False)
        if not expansions_pos:
            # Removed warning logging - too verbose
            break
        
        # Removed verbose logging
        if not tap(expansions_pos[0], expansions_pos[1]):
            # Removed warning logging - too verbose
            break
        
        time.sleep(1.0)  # Wait to return to selection screen
        # Removed verbose logging
        
        # Try to find again after reset (starting from top)
        # First check current screen (top)
        screen_after_reset = screenshot_bgr()
        if screen_after_reset is None:
            # Removed warning logging - too verbose
            continue
        
        pos = find_template(screen_after_reset, exp_path, threshold=0.75, verbose=False)
        if pos:
            # Removed verbose logging - too noisy
            return pos
        
        # If not found at top, scroll again
        # Removed debug logging - too verbose
        for scroll_retry in range(max_scrolls):
            # Removed debug logging - too verbose
            if not scroll_down(slow_mode=True):
                # Removed warning logging - too verbose
                break
            
            time.sleep(0.8)  # Wait after slow scroll
            
            screen_after_scroll = screenshot_bgr()
            if screen_after_scroll is None:
                # Removed warning logging - too verbose
                continue
            
            pos = find_template(screen_after_scroll, exp_path, threshold=0.75, verbose=False)
            if pos:
                # Removed verbose logging - too noisy
                return pos
    
    # Removed warning logging - too verbose
    return None

def select_expansion(expansion_name, series):
    """
    Seleciona uma expansão específica na tela de seleção de expansões.
    Faz scroll se necessário para encontrar a expansão.
    
    Args:
        expansion_name: Nome da expansão (ex: "GA", "MI", etc.)
        series: "A" ou "B"
    
    Returns:
        bool: True se conseguiu selecionar, False caso contrário
    """
    # Removed verbose logging - too noisy
    
    # First, check if need to switch series
    if series == "B":
        # Need to be on Series B
        # Removed debug logging - too verbose
        # TODO: Add "B Series" button detection if needed
        pass
    
    # Verifica se está na tela de seleção de expansões antes de procurar
    current_screen = detect_current_battle_screen(verbose=False)
    if current_screen != "select_expansion":
        # Removed warning logging - too verbose
        return False
    
    # Search for expansion with scroll if needed
    exp_pos = find_expansion_in_screen(expansion_name, series, max_scrolls=8)
    
    if exp_pos is None:
        # Only log critical errors
        return False
    
    # Click on found expansion
    # Removed verbose logging - too noisy
    if not tap(exp_pos[0], exp_pos[1]):
        # Only log critical errors
        return False
    
    # Wait for transition and verify we actually entered the expansion
    time.sleep(1.0)  # Wait for transition to expansion battle screen
    
    # Verify we actually left the expansion selection screen
    current_screen_after = detect_current_battle_screen(verbose=False)
    if current_screen_after == "select_expansion":
        # Removed warning logging - too verbose
        return False
    
    # Only log when expansion is successfully selected - this is important page info
    logging.info(f"{get_bot_prefix()}Expansion {expansion_name} selected (Page: {current_screen_after})")
    return True

def navigate_back_to_expansion_selection():
    """
    Navega de volta para a tela de seleção de expansões.
    Procura pelo botão "Expansions" na tela e clica nele.
    
    Returns:
        bool: True se conseguiu voltar, False caso contrário
    """
    # Removed verbose logging - too noisy
    
    # Look for Expansions button on current screen
    expansions_path = get_template_path("expansions.png", SCREEN_1_BATTLE_SELECTION_DIR)
    
    if not os.path.exists(expansions_path):
        # Only log critical errors
        return False
    
    # Try to find and click Expansions button
    max_attempts = 3
    thresholds = [0.75, 0.70, 0.65]  # Try with decreasing thresholds
    
    for attempt in range(max_attempts):
        screen = screenshot_bgr()
        if screen is None:
            time.sleep(0.5)
            continue
        
        # Try with different thresholds
        threshold = thresholds[min(attempt, len(thresholds) - 1)]
        expansions_pos = find_template(screen, expansions_path, threshold=threshold, verbose=False)
        
        if expansions_pos:
            # Removed verbose logging - too noisy
            if tap(expansions_pos[0], expansions_pos[1]):
                time.sleep(0.8)  # Wait for transition
                
                # Quick check if returned to expansion selection screen
                current_screen = detect_current_battle_screen(verbose=False)
                if current_screen == "select_expansion":
                    return True
                
                # If not confirmed immediately, try once more quickly
                time.sleep(0.3)
                current_screen = detect_current_battle_screen(verbose=False)
                if current_screen == "select_expansion":
                    return True
                
                # Removed debug logging - too verbose
                # May have worked anyway - continue
                return True
        
        # Removed debug logging - too verbose
        time.sleep(0.3)
    
    # Only log critical errors
    return False

def check_expansion_for_hourglass(expansion_name, series):
    """
    Verifica se uma expansão tem hourglass disponível e clica nele se encontrar.
    
    Args:
        expansion_name: Nome da expansão
        series: "A" ou "B"
    
    Returns:
        tuple: (bool, bool) - (encontrou_expansao, encontrou_hourglass)
        - encontrou_expansao: True se conseguiu encontrar e entrar na expansão
        - encontrou_hourglass: True se encontrou e clicou no hourglass
    """
    logging.info(f"{get_bot_prefix()}Checking expansion {expansion_name} (Series {series}) for hourglass...")
    
    # Check where we are before trying to select
    current_screen = detect_current_battle_screen(verbose=False)
    if current_screen != "select_expansion":
        logging.warning(f"Not on expansion selection screen (current screen: {current_screen})")
        # Try to return to expansion selection screen
        if not navigate_back_to_expansion_selection():
            logging.error(f"Failed to return to expansion selection screen")
            return (False, False)
        # Aguarda um pouco após voltar
        time.sleep(0.5)
    
    # Seleciona a expansão (já verifica internamente se está na tela correta)
    if not select_expansion(expansion_name, series):
        logging.warning(f"{get_bot_prefix()}Could not find or select expansion {expansion_name}")
        return (False, False)
    
    # Verifica se realmente entrou na expansão (deve estar na tela de batalhas da expansão)
    # select_expansion já faz essa verificação, mas vamos confirmar novamente
    current_screen = detect_current_battle_screen(verbose=False)
    if current_screen == "select_expansion":
        logging.warning(f"{get_bot_prefix()}Still on selection screen after trying to select {expansion_name}")
        return (False, False)
    
    logging.info(f"{get_bot_prefix()}Entered expansion {expansion_name} (current screen: {current_screen})")
    
    # Procura pelo hourglass (máximo 3 scrolls)
    hourglass_pos = find_hourglass(max_scrolls=3)
    
    if hourglass_pos is None:
        logging.info(f"{get_bot_prefix()}No hourglass found in expansion {expansion_name} (probably complete)")
        # Volta para tela de seleção de expansões
        navigate_back_to_expansion_selection()
        return (True, False)
    
    # Clica no hourglass encontrado
    logging.info(f"{get_bot_prefix()}Hourglass found in expansion {expansion_name}! Clicking...")
    if not tap(hourglass_pos[0], hourglass_pos[1]):
        logging.error(f"{get_bot_prefix()}Failed to click hourglass")
        navigate_back_to_expansion_selection()
        return (True, False)
    
    time.sleep(1.0)  # Aguarda transição (reduzido de 2.0)
    return (True, True)

def ensure_expansion_selection_screen():
    """
    Garante que está na tela de seleção de expansões.
    Verifica constantemente e navega se necessário.
    
    Returns:
        bool: True se está na tela de seleção de expansões, False caso contrário
    """
    # Verificação rápida primeiro (sem verbose para ser mais rápido)
    current_screen = detect_current_battle_screen(verbose=False)
    if current_screen == "select_expansion":
        return True
    
    max_attempts = 3  # Reduzido de 5 para 3
    for attempt in range(max_attempts):
        current_screen = detect_current_battle_screen(verbose=False)
        
        if current_screen == "select_expansion":
            return True
        
        if attempt == 0:
            # Primeira tentativa: tenta clicar no botão Expansions
            if current_screen == "battle_selection":
                logging.info(f"{get_bot_prefix()}Clicking Expansions button to access selection screen...")
                if tap_expansions_button():
                    time.sleep(0.8)  # Reduzido para 0.8s
                    continue
            else:
                # Tenta voltar usando botão Expansions
                logging.info(f"{get_bot_prefix()}Current screen: {current_screen}. Trying to return to expansion selection...")
                navigate_back_to_expansion_selection()
                time.sleep(0.3)  # Reduzido para 0.3s
                continue
        else:
            # Tentativas subsequentes: usa botão Expansions
            logging.info(f"{get_bot_prefix()}Attempt {attempt + 1}/{max_attempts}: Trying to return...")
            navigate_back_to_expansion_selection()
            time.sleep(0.3)  # Reduzido para 0.3s
    
    logging.error(f"{get_bot_prefix()}Could not ensure we're on expansion selection screen")
    return False

def switch_to_series(series_letter):
    """
    Muda para Series A ou B na tela de seleção de expansões.
    
    Args:
        series_letter: "A" ou "B"
    
    Returns:
        bool: True se conseguiu mudar (ou já estava na série correta), False caso contrário
    """
    logging.info(f"{get_bot_prefix()}Trying to switch to Series {series_letter}...")
    
    # Garante que está na tela de seleção de expansões
    if not ensure_expansion_selection_screen():
        logging.error(f"{get_bot_prefix()}Not on expansion selection screen")
        return False
    
    # Template path para o botão de série
    series_template = os.path.join(SERIES_SWITCH_DIR, f"{series_letter.lower()}.png")
    
    if not os.path.exists(series_template):
        logging.error(f"Template {series_letter.lower()}.png not found at {series_template}")
        return False
    
    # Procura e clica no botão da série
    screen = screenshot_bgr()
    if screen is None:
        logging.error("Could not capture screenshot")
        return False
    
    series_pos = find_template(screen, series_template, threshold=0.75, verbose=True)
    if series_pos:
        logging.info(f"{get_bot_prefix()}Series {series_letter} button found at {series_pos}. Clicking...")
        if tap(series_pos[0], series_pos[1]):
            time.sleep(1.0)  # Aguarda transição
            logging.info(f"{get_bot_prefix()}Switched to Series {series_letter}")
            return True
        else:
            logging.error(f"Failed to click Series {series_letter} button")
            return False
    else:
        logging.debug(f"Series {series_letter} button not found - may already be on correct series")
        return True  # Assume que já está na série correta

def handle_expansion_selection():
    """
    Processa a seleção de expansões e verifica por hourglasses.
    
    Fluxo:
    1. Garante que está na tela de seleção de expansões
    2. Verifica se há expansões Series A incompletas
    3. Se houver, tenta Series A primeiro (não vai para Series B enquanto houver battles em A)
    4. Se todas Series A estiverem completas, muda para Series B
    5. Tenta cada expansão Series B
    6. Se todas Series B estiverem completas, volta para Series A e reseta completed_expansions
    7. Para cada expansão:
       - Verifica se está completa (pula se estiver)
       - Tenta encontrar e selecionar a expansão
       - Se conseguir entrar, verifica hourglass
       - Se não encontrar hourglass, marca como completa e volta
       - Se encontrar hourglass, clica e retorna True
    
    Returns:
        bool: True se encontrou hourglass em alguma expansão, False caso contrário
    """
    # Check stop flag at start
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested at start of expansion selection")
        return False
    
    logging.info(f"{get_bot_prefix()}Processing expansion selection...")
    
    completed_expansions = load_completed_expansions()
    
    # Ensure we're on expansion selection screen
    if not ensure_expansion_selection_screen():
        logging.error(f"{get_bot_prefix()}Failed to access expansion selection screen")
        return False
    
    # Check stop flag after ensuring screen
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested after ensuring expansion screen")
        return False
    
    # Check for incomplete Series A expansions
    series_a_incomplete = []
    for expansion in EXPANSIONS_SERIES_A:
        expansion_key = f"A_{expansion}"
        if expansion_key not in completed_expansions:
            series_a_incomplete.append(expansion)
    
    # Try Series A first if there are incomplete expansions
    if series_a_incomplete:
        logging.info(f"{get_bot_prefix()}Checking Series A ({len(series_a_incomplete)} incomplete expansions)...")
        
        # Ensure we're on Series A
        if not switch_to_series("A"):
            logging.warning(f"{get_bot_prefix()}Could not ensure Series A, but continuing...")
        
        for expansion in EXPANSIONS_SERIES_A:
            # Check stop flag in expansion loop
            if check_stop_flag():
                logging.info(f"{get_bot_prefix()}Stop requested during expansion selection")
                return False
            
            expansion_key = f"A_{expansion}"
            
            # Check if already completed
            if expansion_key in completed_expansions:
                logging.debug(f"Skipping expansion {expansion} (Series A) - already marked as complete")
                continue
            
            logging.info(f"{get_bot_prefix()}Checking expansion {expansion} (Series A)...")
            
            # Quick check if still on selection screen
            current_screen = detect_current_battle_screen(verbose=False)
            if current_screen != "select_expansion":
                # Only ensure navigation if really not on the screen
                if not ensure_expansion_selection_screen():
                    logging.warning(f"Lost expansion selection screen while checking {expansion}")
                    continue
            
            # Check expansion - retry until found or confirmed missing
            max_attempts_per_expansion = 3
            found_expansion = False
            found_hourglass = False
            
            for attempt in range(max_attempts_per_expansion):
                if attempt > 0:
                    logging.info(f"Retry {attempt + 1}/{max_attempts_per_expansion} to find expansion {expansion}...")
                    # Ensure we're on selection screen before retrying
                    if not ensure_expansion_selection_screen():
                        logging.warning(f"Failed to ensure selection screen on attempt {attempt + 1}")
                        time.sleep(0.5)
                
                found_expansion, found_hourglass = check_expansion_for_hourglass(expansion, "A")
                
                if found_hourglass:
                    # Found hourglass and clicked - return True
                    logging.info(f"Hourglass found in expansion {expansion}!")
                    return True
                elif found_expansion:
                    # Entered expansion but no hourglass - mark as complete
                    completed_expansions.add(expansion_key)
                    save_completed_expansions(completed_expansions)
                    logging.info(f"{get_bot_prefix()}Expansion {expansion} (Series A) marked as complete")
                    break  # Exit retry loop
                else:
                    # Could not find expansion - retry if attempts remain
                    if attempt < max_attempts_per_expansion - 1:
                        logging.debug(f"Could not find expansion {expansion} on attempt {attempt + 1}. Retrying...")
                        time.sleep(0.5)
                    else:
                        # Last attempt failed - don't mark as complete
                        logging.warning(f"Could not access expansion {expansion} after {max_attempts_per_expansion} attempts - will not be marked as complete")
        
        # After processing Series A, reload completed expansions to get latest state
        completed_expansions = load_completed_expansions()
        
        # Check if Series A still has incomplete expansions after processing
        series_a_incomplete_after = []
        for expansion in EXPANSIONS_SERIES_A:
            expansion_key = f"A_{expansion}"
            if expansion_key not in completed_expansions:
                series_a_incomplete_after.append(expansion)
        
        if series_a_incomplete_after:
            logging.info(f"Still {len(series_a_incomplete_after)} incomplete Series A expansions. Not switching to Series B.")
            logging.warning(f"{get_bot_prefix()}No hourglass found in available Series A expansions")
            return False
    else:
        # No incomplete Series A expansions - all are already complete
        logging.info(f"{get_bot_prefix()}All Series A expansions already complete. Proceeding to Series B...")
    
    # All Series A complete - now try Series B
    logging.info(f"{get_bot_prefix()}All Series A expansions complete. Switching to Series B...")
    
    # Switch to Series B
    if not switch_to_series("B"):
        logging.error(f"{get_bot_prefix()}Failed to switch to Series B")
        return False
    
    # Check for incomplete Series B expansions
    series_b_incomplete = []
    for expansion in EXPANSIONS_SERIES_B:
        expansion_key = f"B_{expansion}"
        if expansion_key not in completed_expansions:
            series_b_incomplete.append(expansion)
    
    if not series_b_incomplete:
        logging.info(f"{get_bot_prefix()}All Series B expansions also complete. Resetting and returning to Series A...")
        
        # Reset completed_expansions
        reset_completed_expansions()
        completed_expansions = set()
        
        # Return to Series A
        if not switch_to_series("A"):
            logging.error(f"{get_bot_prefix()}Failed to return to Series A after reset")
            return False
        
        logging.info(f"{get_bot_prefix()}Reset completed_expansions and returned to Series A. Bot will continue from the beginning.")
        return False  # Return False to indicate no hourglass found, but reset was done
    
    # Try Series B
    logging.info(f"{get_bot_prefix()}Checking Series B ({len(series_b_incomplete)} incomplete expansions)...")
    for expansion in EXPANSIONS_SERIES_B:
        # Check stop flag in expansion loop
        if check_stop_flag():
            logging.info(f"{get_bot_prefix()}Stop requested during expansion selection (Series B)")
            return False
        
        expansion_key = f"B_{expansion}"
        
        # Check if already complete
        if expansion_key in completed_expansions:
            logging.debug(f"Skipping expansion {expansion} (Series B) - already marked as complete")
            continue
        
        logging.info(f"{get_bot_prefix()}Checking expansion {expansion} (Series B)...")
        
        # Quick check if still on selection screen
        current_screen = detect_current_battle_screen(verbose=False)
        if current_screen != "select_expansion":
            # Only ensure navigation if really not on the screen
            if not ensure_expansion_selection_screen():
                logging.warning(f"Lost expansion selection screen while checking {expansion}")
                continue
        
        # Check expansion - retry until found or confirmed missing
        max_attempts_per_expansion = 3
        found_expansion = False
        found_hourglass = False
        
        for attempt in range(max_attempts_per_expansion):
            if attempt > 0:
                logging.info(f"Retry {attempt + 1}/{max_attempts_per_expansion} to find expansion {expansion}...")
                # Ensure we're on selection screen before retrying
                if not ensure_expansion_selection_screen():
                    logging.warning(f"Failed to ensure selection screen on attempt {attempt + 1}")
                    time.sleep(0.5)
            
            found_expansion, found_hourglass = check_expansion_for_hourglass(expansion, "B")
            
            if found_hourglass:
                # Found hourglass and clicked - return True
                logging.info(f"Hourglass found in expansion {expansion}!")
                return True
            elif found_expansion:
                # Entered expansion but no hourglass - mark as complete
                completed_expansions.add(expansion_key)
                save_completed_expansions(completed_expansions)
                logging.info(f"{get_bot_prefix()}Expansion {expansion} (Series B) marked as complete")
                break  # Exit retry loop
            else:
                # Could not find expansion - retry if attempts remain
                if attempt < max_attempts_per_expansion - 1:
                    logging.debug(f"Could not find expansion {expansion} on attempt {attempt + 1}. Retrying...")
                    time.sleep(0.5)
                else:
                    # Last attempt failed - don't mark as complete
                    logging.warning(f"Could not access expansion {expansion} after {max_attempts_per_expansion} attempts - will not be marked as complete")
    
    # Check if all Series B expansions are now complete
    series_b_incomplete_after = []
    for expansion in EXPANSIONS_SERIES_B:
        expansion_key = f"B_{expansion}"
        if expansion_key not in completed_expansions:
            series_b_incomplete_after.append(expansion)
    
    if not series_b_incomplete_after:
        logging.info(f"{get_bot_prefix()}All Series B expansions complete. Resetting and returning to Series A...")
        
        # Reset completed_expansions
        reset_completed_expansions()
        completed_expansions = set()
        
        # Return to Series A
        if not switch_to_series("A"):
            logging.error(f"{get_bot_prefix()}Failed to return to Series A after reset")
            return False
        
        logging.info(f"{get_bot_prefix()}Reset completed_expansions and returned to Series A. Bot will continue from the beginning.")
        return False  # Return False to indicate no hourglass found, but reset was done
    
    logging.warning(f"{get_bot_prefix()}No hourglass found in any available expansion")
    return False

def handle_battle_selection_screen():
    """
    Processa a tela de seleção de batalhas.
    
    Fluxo:
    1. Procura pelo hourglass (rola a tela se necessário)
    2. Se não encontrar, tenta selecionar uma expansão através do botão Expansions
    3. Quando encontrar hourglass, toca nele
    4. Aguarda a próxima tela
    """
    # Check stop flag at start
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested at start of battle selection")
        return False
    
    logging.info(f"{get_bot_prefix()}Processing battle selection screen...")
    
    # Search for hourglass (with automatic scrolling if needed)
    hourglass_pos = find_hourglass(max_scrolls=3)
    
    # Check stop flag after hourglass search
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested after hourglass search")
        return False
    
    if hourglass_pos is None:
        logging.info(f"{get_bot_prefix()}Hourglass not found on current screen. Trying to select expansion...")
        # Try to select an expansion
        if handle_expansion_selection():
            # If found hourglass in an expansion, it was already clicked
            # Need to verify if returned to selection screen or is on setup screen
            time.sleep(1.0)
            return True
        else:
            logging.warning(f"{get_bot_prefix()}Could not find hourglass in any available expansion")
            return False
    
    # Tap on found hourglass
    logging.info(f"{get_bot_prefix()}Tapping hourglass at {hourglass_pos}")
    if not tap(hourglass_pos[0], hourglass_pos[1]):
        logging.error(f"{get_bot_prefix()}Failed to tap hourglass")
        return False
    
    # Wait for transition to next screen
    logging.debug(f"{get_bot_prefix()}Waiting for screen transition...")
    time.sleep(1.0)
    
    logging.info(f"{get_bot_prefix()}Battle selection screen processed successfully")
    return True

def wait_for_battle_completion(max_wait_time=None):
    """
    Aguarda a conclusão da batalha em loop.
    
    Fluxo:
    1. Primeiro aguarda a batalha começar (detecta "Opponent" aparecer)
    2. Depois aguarda a batalha terminar (detecta "Tap to Proceed" aparecer)
    
    Args:
        max_wait_time: Tempo máximo de espera em segundos (None = sem timeout, aguarda indefinidamente)
    
    Returns:
        bool: True se encontrou a tela de resultado, False se timeout (apenas se max_wait_time for definido)
    """
    if max_wait_time:
        logging.info(f"{get_bot_prefix()}Waiting for battle to start and complete (max {max_wait_time}s)...")
    else:
        logging.info(f"{get_bot_prefix()}Waiting for battle to start and complete (no timeout)...")
    
    tap_to_proceed_path = get_template_path("tap_to_proceed.png", SCREEN_3_VICTORY_DIR)
    opponent_path = get_template_path("opponent.png", BATTLE_IN_PROGRESS_DIR)
    battle_path = get_template_path("battle.png", SCREEN_2_BATTLE_SETUP_DIR)
    auto_off_path = get_template_path("auto_off.png", BATTLE_IN_PROGRESS_DIR)
    put_basic_path = get_template_path("put_basic_pokemon.png", BATTLE_IN_PROGRESS_DIR)
    
    if not os.path.exists(tap_to_proceed_path):
        logging.error(f"Template tap_to_proceed.png not found at {tap_to_proceed_path}")
        logging.error("Please ensure tap_to_proceed.png exists in templates/battle/result/")
        return False
    
    if not os.path.exists(opponent_path):
        logging.debug(f"Template opponent.png not found at {opponent_path}")
        logging.debug("Using alternative detection method (without Opponent)")
    
    start_time = time.time()
    check_interval = 2.5  # Verifica a cada 2.5 segundos inicialmente (aumentado para reduzir CPU)
    check_interval_battle = 0.8  # Verifica a cada 0.8 segundos quando batalha já começou (aumentado de 0.5)
    attempts = 0
    battle_started = False
    last_status_log = 0  # Para controlar logs espaçados
    
    while True:
        # Check stop flag first
        if check_stop_flag():
            logging.info("Stop requested during battle wait")
            return False
        
        # Check timeout only if defined
        if max_wait_time and time.time() - start_time >= max_wait_time:
            logging.error(f"Timeout: Battle not completed after {max_wait_time}s")
            final_screen = detect_current_battle_screen()
            if final_screen:
                logging.error(f"Current screen at timeout: {final_screen}")
            else:
                logging.error("No known screen detected at timeout")
            return False
        
        attempts += 1
        elapsed = int(time.time() - start_time)
        
        screen = screenshot_bgr()
        if screen is None:
            logging.debug(f"Attempt {attempts}: Could not capture screenshot (elapsed: {elapsed}s)")
            time.sleep(check_interval)
            continue
        
        # FIRST: Check if result screen appeared (tap_to_proceed)
        # This should be checked BEFORE anything else, as when battle ends,
        # battle_in_progress may no longer be detected
        tap_result_pos = find_template(screen, tap_to_proceed_path, threshold=0.75, verbose=False)
        if tap_result_pos:
            logging.info(f"Result screen found after {elapsed}s (victory or defeat)")
            return True
        
        # Detecta qual tela está sendo exibida PRIMEIRO (sem logs verbosos)
        detected_screen = detect_current_battle_screen(verbose=False)
        
        # Verifica se ainda estamos na tela de Battle Setup (o clique pode não ter funcionado)
        # IMPORTANTE: Só tenta clicar novamente se realmente estiver em battle_setup
        # Verifica auto.png para confirmar que está realmente na tela de Battle Setup
        # Se detectou outra tela (como battle_selection), não deve tentar clicar
        if detected_screen == "battle_setup":
            auto_setup_path = get_template_path("auto.png", SCREEN_2_BATTLE_SETUP_DIR)
            # Confirma que está realmente na tela de Battle Setup verificando auto.png
            if os.path.exists(auto_setup_path):
                auto_setup_pos = find_template(screen, auto_setup_path, threshold=0.75, verbose=False)
                if auto_setup_pos and os.path.exists(battle_path):
                    battle_pos = find_template(screen, battle_path, threshold=0.75, verbose=False)
                    if battle_pos:
                        logging.warning(f"{get_bot_prefix()}Still on Battle Setup screen after {elapsed}s - click may not have worked")
                        logging.info(f"{get_bot_prefix()}Trying to click Battle button again...")
                        if tap(battle_pos[0], battle_pos[1]):
                            time.sleep(2.0)  # Wait for transition
                        continue
        elif detected_screen == "battle_selection":
            # If detected battle_selection, battle ended and returned to selection
            logging.info(f"{get_bot_prefix()}Battle completed! Returned to battle selection screen after {elapsed}s")
            return True
        
        # Verifica se está na batalha (detecta battle_in_progress, opponent ou put_basic_pokemon)
        is_in_battle = False
        
        if detected_screen == "battle_in_progress":
            is_in_battle = True
        elif os.path.exists(opponent_path):
            opponent_pos = find_template(screen, opponent_path, threshold=0.75, verbose=False)
            if opponent_pos:
                is_in_battle = True
        elif os.path.exists(put_basic_path):
            put_basic_pos = find_template(screen, put_basic_path, threshold=0.75, verbose=False)
            if put_basic_pos:
                is_in_battle = True
                logging.debug(f"'Put Basic Pokémon' screen detected - waiting for Auto to place Pokémon...")
        
        # Check if Auto is OFF during battle
        if is_in_battle and os.path.exists(auto_off_path):
            auto_off_pos = find_template(screen, auto_off_path, threshold=0.75, verbose=False)
            if auto_off_pos:
                logging.warning(f"{get_bot_prefix()}Auto is OFF during battle after {elapsed}s! Enabling Auto...")
                if tap(auto_off_pos[0], auto_off_pos[1]):
                    time.sleep(0.5)  # Wait for toggle to take effect
                    logging.info(f"{get_bot_prefix()}Auto enabled during battle")
                continue
        
        # Check if battle started (Opponent appeared or put_basic_pokemon detected)
        if not battle_started:
            if detected_screen == "battle_in_progress":
                battle_started = True
                logging.info(f"{get_bot_prefix()}Battle started! Detected battle_in_progress after {elapsed}s")
            elif os.path.exists(opponent_path):
                opponent_pos = find_template(screen, opponent_path, threshold=0.75, verbose=False)
                if opponent_pos:
                    battle_started = True
                    logging.info(f"{get_bot_prefix()}Battle started! Opponent found after {elapsed}s")
            elif os.path.exists(put_basic_path):
                put_basic_pos = find_template(screen, put_basic_path, threshold=0.75, verbose=False)
                if put_basic_pos:
                    battle_started = True
                    logging.info(f"{get_bot_prefix()}Battle started! 'Put Basic Pokémon' screen detected after {elapsed}s")
        else:
            # Battle already started - log every 60 seconds to avoid log spam
                        if elapsed - last_status_log >= 60:
                            logging.info(f"{get_bot_prefix()}Battle in progress... waiting for completion ({elapsed}s)")
                            last_status_log = elapsed
        
        # Usa intervalo menor quando batalha já começou para detectar resultado mais rapidamente
        sleep_time = check_interval_battle if battle_started else check_interval
        
        # Optimized interruptible sleep - check less frequently to reduce CPU overhead
        sleep_remaining = sleep_time
        check_interval_sleep = 0.3  # Increased from 0.1 to reduce overhead (still responsive)
        while sleep_remaining > 0:
            if check_stop_flag():
                logging.info("Stop requested during sleep in wait_for_battle_completion")
                return False
            actual_sleep = min(check_interval_sleep, sleep_remaining)
            time.sleep(actual_sleep)
            sleep_remaining -= actual_sleep

def handle_defeat_screen():
    """
    Processa a tela de derrota.
    
    Fluxo:
    1. Verifica Screen 8 ANTES de qualquer ação (verificação rápida)
    2. Procura pelo primeiro "Tap to Proceed" e clica
    3. Procura pelo segundo "Tap to Proceed" e clica
    4. Procura pelo terceiro "Tap to Proceed" e clica
    5. Procura pelo botão "Next" e clica
    6. Verifica Screen 8 APÓS Next com cautela (é aqui que geralmente aparece)
    7. Retorna para battle_selection
    """
    logging.info(f"{get_bot_prefix()}=== Processing defeat screen ===")
    
    # Verifica Screen 8 ANTES de qualquer ação (verificação rápida apenas)
    handle_screen_8_quick()
    
    # Procura pelo texto "Tap to Proceed" (usa o mesmo template da vitória)
    tap_to_proceed_path = get_template_path("tap_to_proceed.png", SCREEN_3_VICTORY_DIR)
    
    if not os.path.exists(tap_to_proceed_path):
        logging.error(f"{get_bot_prefix()}Template tap_to_proceed.png not found at {tap_to_proceed_path}")
        logging.error(f"{get_bot_prefix()}Please ensure tap_to_proceed.png exists in templates/battle/result/")
        return False
    
    # First "Tap to Proceed"
    logging.info(f"{get_bot_prefix()}Looking for first 'Tap to Proceed' on defeat screen...")
    if not wait_and_tap_template("tap_to_proceed.png", timeout=3, threshold=0.75, screen_dir=SCREEN_3_VICTORY_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click first 'Tap to Proceed'")
        return False
    
    # Wait for quick transition
    time.sleep(0.3)
    
    # Second "Tap to Proceed"
    logging.info(f"{get_bot_prefix()}Looking for second 'Tap to Proceed' on defeat screen...")
    if not wait_and_tap_template("tap_to_proceed.png", timeout=3, threshold=0.75, screen_dir=SCREEN_3_VICTORY_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click second 'Tap to Proceed'")
        return False
    
    # Wait for quick transition
    time.sleep(0.3)
    
    # Check if defeat popup appeared with Back button after second tap
    back_path = get_template_path("back.png", SCREEN_DEFEAT_POPUP_DIR)
    if os.path.exists(back_path):
        screen_after_second = screenshot_bgr()
        if screen_after_second is not None:
            back_pos = find_template(screen_after_second, back_path, threshold=0.75, verbose=False)
            if back_pos:
                logging.info(f"{get_bot_prefix()}Defeat popup detected after second 'Tap to Proceed'. Clicking Back...")
                if tap(back_pos[0], back_pos[1]):
                    time.sleep(0.5)  # Wait for popup to close
                    logging.info(f"{get_bot_prefix()}Defeat popup closed")
                else:
                    logging.warning(f"{get_bot_prefix()}Failed to click Back button")
    
    # Verifica se já está na Screen 7 (botão Next) após o segundo tap
    # Se não estiver, tenta o terceiro "Tap to Proceed"
    next_path = get_template_path("next.png", SCREEN_7_DIR)
    screen_after_second = screenshot_bgr()
    
    if screen_after_second is not None and os.path.exists(next_path):
        next_pos = find_template(screen_after_second, next_path, threshold=0.75, verbose=False)
        if next_pos:
            logging.info(f"{get_bot_prefix()}Already on Screen 7 after second 'Tap to Proceed'. Skipping third tap.")
        else:
            # Not on Screen 7 yet, try third "Tap to Proceed"
            logging.info(f"{get_bot_prefix()}Looking for third 'Tap to Proceed' on defeat screen...")
            if not wait_and_tap_template("tap_to_proceed.png", timeout=3, threshold=0.75, screen_dir=SCREEN_3_VICTORY_DIR, fast_mode=True):
                # If third tap not found, check if already on Screen 7
                logging.debug(f"{get_bot_prefix()}Third 'Tap to Proceed' not found. Checking if already on Screen 7...")
                time.sleep(0.3)
                check_screen = screenshot_bgr()
                if check_screen is not None and os.path.exists(next_path):
                    next_check = find_template(check_screen, next_path, threshold=0.75, verbose=False)
                    if next_check:
                        logging.info(f"{get_bot_prefix()}Already on Screen 7. Continuing...")
                    else:
                        logging.warning(f"{get_bot_prefix()}Not on Screen 7 and third tap not found. Continuing anyway...")
                else:
                    logging.warning(f"{get_bot_prefix()}Could not verify Screen 7. Continuing...")
            else:
                # Found and clicked third tap
                time.sleep(0.3)
                # Check if defeat popup appeared after third tap
                if os.path.exists(back_path):
                    screen_after_third = screenshot_bgr()
                    if screen_after_third is not None:
                        back_pos = find_template(screen_after_third, back_path, threshold=0.75, verbose=False)
                        if back_pos:
                            logging.info(f"{get_bot_prefix()}Defeat popup detected after third 'Tap to Proceed'. Clicking Back...")
                            if tap(back_pos[0], back_pos[1]):
                                time.sleep(0.5)  # Wait for popup to close
                                logging.info(f"{get_bot_prefix()}Defeat popup closed")
                            else:
                                logging.warning(f"{get_bot_prefix()}Failed to click Back button")
    else:
        # Could not verify, try third tap normally
        logging.info(f"{get_bot_prefix()}Looking for third 'Tap to Proceed' on defeat screen...")
        if not wait_and_tap_template("tap_to_proceed.png", timeout=3, threshold=0.75, screen_dir=SCREEN_3_VICTORY_DIR, fast_mode=True):
            logging.warning(f"{get_bot_prefix()}Third 'Tap to Proceed' not found. Continuing to look for Next button...")
        else:
            time.sleep(0.3)
            # Check if defeat popup appeared after third tap
            if os.path.exists(back_path):
                screen_after_third = screenshot_bgr()
                if screen_after_third is not None:
                    back_pos = find_template(screen_after_third, back_path, threshold=0.75, verbose=False)
                    if back_pos:
                        logging.info(f"{get_bot_prefix()}Defeat popup detected after third 'Tap to Proceed'. Clicking Back...")
                        if tap(back_pos[0], back_pos[1]):
                            time.sleep(0.5)  # Wait for popup to close
                            logging.info(f"{get_bot_prefix()}Defeat popup closed")
                        else:
                            logging.warning(f"{get_bot_prefix()}Failed to click Back button")
    
    # Look for "Next" button
    if not os.path.exists(next_path):
        logging.error(f"{get_bot_prefix()}Template next.png not found at {next_path}")
        logging.error(f"{get_bot_prefix()}Please ensure next.png exists in templates/battle/summary/")
        return False
    
    logging.info(f"{get_bot_prefix()}Looking for 'Next' button after defeat...")
    if not wait_and_tap_template("next.png", timeout=5, threshold=0.75, screen_dir=SCREEN_7_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click 'Next' button")
        return False
    
    # Wait for transition
    time.sleep(0.5)
    
    # Check Screen 8 AFTER Next carefully (this is where it usually appears)
    handle_screen_8()
    
    logging.info(f"{get_bot_prefix()}Defeat screen processed successfully! Returning to battle selection...")
    return True

def handle_defeat_popup():
    """
    Processa o pop-up de derrota que aparece após os taps de "Tap to Proceed".
    Este pop-up mostra uma recomendação de tipo e tem um botão "Back".
    
    Fluxo:
    1. Procura pelo botão "Back" no pop-up
    2. Clica no botão "Back" para fechar o pop-up
    3. Aguarda a transição
    """
    logging.info(f"{get_bot_prefix()}Processing defeat popup...")
    
    back_path = get_template_path("back.png", SCREEN_DEFEAT_POPUP_DIR)
    
    if not os.path.exists(back_path):
        logging.error(f"{get_bot_prefix()}Template back.png not found at {back_path}")
        logging.error(f"{get_bot_prefix()}Please ensure back.png exists in templates/battle/defeat_popup/")
        return False
    
    logging.info(f"{get_bot_prefix()}Looking for 'Back' button in defeat popup...")
    if not wait_and_tap_template("back.png", timeout=5, threshold=0.75, screen_dir=SCREEN_DEFEAT_POPUP_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click 'Back' button")
        return False
    
    # Wait for transition after closing popup
    time.sleep(0.5)
    
    logging.info(f"{get_bot_prefix()}Defeat popup processed successfully!")
    return True

def handle_result_screen():
    """
    Processa a tela de resultado da batalha (vitória).
    A tela de derrota é tratada separadamente em handle_defeat_screen().
    
    Fluxo:
    1. Verifica Screen 8 ANTES de qualquer ação (verificação rápida)
    2. Procura pelo texto "Tap to Proceed"
    3. Quando encontrar, toca na tela para prosseguir
    4. Aguarda a próxima tela
    """
    logging.info(f"{get_bot_prefix()}Processing result screen (victory)...")
    
    # Check Screen 8 BEFORE any action (quick check only)
    handle_screen_8_quick()
    
    # Look for "Tap to Proceed" text
    tap_to_proceed_path = get_template_path("tap_to_proceed.png", SCREEN_3_VICTORY_DIR)
    
    if not os.path.exists(tap_to_proceed_path):
        logging.error(f"{get_bot_prefix()}Template tap_to_proceed.png not found at {tap_to_proceed_path}")
        logging.error(f"{get_bot_prefix()}Please ensure tap_to_proceed.png exists in templates/battle/result/")
        return False
    
    logging.info(f"{get_bot_prefix()}Looking for 'Tap to Proceed' text...")
    # Reduced timeout and fast_mode for faster detection
    if not wait_and_tap_template("tap_to_proceed.png", timeout=2, threshold=0.75, screen_dir=SCREEN_3_VICTORY_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click 'Tap to Proceed'")
        return False
    
    # Wait for transition to next screen and verify we've moved away from result screen
    logging.info(f"{get_bot_prefix()}Waiting for transition to Screen 4...")
    
    # Wait a bit longer for the transition to start
    time.sleep(0.5)
    
    # Verify we've transitioned away from result screen by checking that result screen template is gone
    # and that Screen 4 template appears (or at least result screen is gone)
    tap_result_path = get_template_path("tap_to_proceed.png", SCREEN_3_VICTORY_DIR)
    tap_4_5_6_path = get_template_path("tap_to_proceed.png", SCREEN_4_5_6_DIR)
    
    transition_timeout = 5.0  # Maximum time to wait for transition
    transition_start = time.time()
    check_interval = 0.2
    
    while time.time() < transition_start + transition_timeout:
        # Check stop flag
        if check_stop_flag():
            return False
        
        screen = screenshot_bgr()
        if screen is None:
            time.sleep(check_interval)
            continue
        
        # Check if we're still on result screen
        result_pos = find_template(screen, tap_result_path, threshold=0.75, verbose=False)
        if result_pos:
            # Still on result screen, wait a bit more
            time.sleep(check_interval)
            continue
        
        # Result screen is gone, check if Screen 4 has appeared
        screen_4_pos = find_template(screen, tap_4_5_6_path, threshold=0.75, verbose=False)
        if screen_4_pos:
            # Screen 4 has appeared, transition complete
            logging.info(f"{get_bot_prefix()}Transition to Screen 4 confirmed")
            time.sleep(0.2)  # Small delay before proceeding
            logging.info(f"{get_bot_prefix()}Result screen processed successfully!")
            return True
        
        # Neither screen detected - might be in transition, wait a bit
        time.sleep(check_interval)
    
    # If we get here, transition took too long, but result screen is gone
    # Proceed anyway - Screen 4 detection will handle it
    logging.warning(f"{get_bot_prefix()}Transition timeout, but result screen is gone. Proceeding to Screen 4...")
    time.sleep(0.3)  # Give it a bit more time
    logging.info(f"{get_bot_prefix()}Result screen processed successfully!")
    return True

def handle_screens_4_5_6():
    """
    Processa as Screens 4, 5 e 6 (todas usam o mesmo template "Tap to Proceed").
    
    Fluxo:
    Para cada tela (4, 5, 6):
    1. Procura pelo texto "Tap to Proceed"
    2. Quando encontrar, toca na tela para prosseguir
    3. Aguarda a próxima tela
    """
    logging.info(f"{get_bot_prefix()}=== Processing Screens 4, 5 and 6 ===")
    
    # Verifica se o template existe
    tap_to_proceed_path = get_template_path("tap_to_proceed.png", SCREEN_4_5_6_DIR)
    
    if not os.path.exists(tap_to_proceed_path):
        logging.error(f"Template tap_to_proceed.png not found at {tap_to_proceed_path}")
        logging.error("Please ensure tap_to_proceed.png exists in templates/battle/rewards/")
        return False
    
    # Process each of the 3 screens sequentially
    for screen_num in [4, 5, 6]:
        logging.info(f"{get_bot_prefix()}Processing Screen {screen_num}...")
        
        # For Screen 4, add extra wait time if coming from result screen (first iteration)
        # This helps handle the transition delay
        if screen_num == 4:
            # Small delay to ensure screen has fully loaded
            time.sleep(0.3)
            # Verify we're actually on Screen 4 before proceeding
            screen = screenshot_bgr()
            if screen is not None:
                tap_4_5_6_pos = find_template(screen, tap_to_proceed_path, threshold=0.75, verbose=False)
                if not tap_4_5_6_pos:
                    # Screen 4 not ready yet, wait a bit more
                    logging.info(f"{get_bot_prefix()}Screen 4 not ready yet, waiting...")
                    time.sleep(0.5)
        
        logging.debug(f"Looking for 'Tap to Proceed' text on Screen {screen_num}...")
        # Increased timeout for Screen 4 (first screen) to handle transition delays
        # Screens 5 and 6 should be faster since they're already loaded
        timeout = 8 if screen_num == 4 else 5
        if not wait_and_tap_template("tap_to_proceed.png", timeout=timeout, threshold=0.75, screen_dir=SCREEN_4_5_6_DIR, fast_mode=True):
            logging.error(f"{get_bot_prefix()}Failed to find or click 'Tap to Proceed' on Screen {screen_num}")
            return False
        
        # Wait for transition to next screen
        time.sleep(0.3)  # Minimum delay for transition
        
        logging.debug(f"Screen {screen_num} processed successfully")
    
    logging.info("Screens 4, 5, and 6 processed successfully")
    return True

def handle_screen_7():
    """
    Processa a Screen 7 (tela com botão "Next").
    
    Fluxo:
    1. Verifica Screen 8 ANTES de qualquer ação (verificação rápida)
    2. Procura pelo botão "Next"
    3. Quando encontrar, toca no botão
    4. Aguarda a próxima tela
    5. Verifica Screen 8 APÓS Next com cautela (é aqui que geralmente aparece)
    """
    logging.info(f"{get_bot_prefix()}=== Processing Screen 7 ===")
    
    # Verifica Screen 8 ANTES de qualquer ação (verificação rápida apenas)
    handle_screen_8_quick()
    
    # Procura pelo botão "Next"
    next_path = get_template_path("next.png", SCREEN_7_DIR)
    
    if not os.path.exists(next_path):
        logging.error(f"{get_bot_prefix()}Template next.png not found at {next_path}")
        logging.error(f"{get_bot_prefix()}Please ensure next.png exists in templates/battle/summary/")
        return False
    
    logging.info(f"{get_bot_prefix()}Looking for 'Next' button...")
    if not wait_and_tap_template("next.png", timeout=3, threshold=0.75, screen_dir=SCREEN_7_DIR, fast_mode=True):
        logging.error(f"{get_bot_prefix()}Failed to find or click 'Next' button")
        return False
    
    # Wait for transition to next screen
    time.sleep(0.5)
    
    # Check Screen 8 AFTER Next carefully (this is where it usually appears)
    handle_screen_8()
    
    logging.info(f"{get_bot_prefix()}Screen 7 processed successfully")
    return True

def handle_screen_8_quick():
    """
    Verificação rápida da Screen 8 (pop-up "New Battle Unlocked!").
    Usada antes de ações importantes para não bloquear se o pop-up aparecer.
    
    Returns:
        bool: True sempre (não falha se não aparecer)
    """
    ok_path = get_template_path("ok.png", SCREEN_8_DIR)
    
    if not os.path.exists(ok_path):
        return True
    
    # Verificação rápida (apenas 1 tentativa)
    screen = screenshot_bgr()
    if screen is None:
        return True
    
    ok_pos = find_template(screen, ok_path, threshold=0.75, verbose=False)
    if ok_pos:
        logging.info(f"{get_bot_prefix()}Screen 8 appeared! OK button found at {ok_pos}. Clicking...")
        if tap(ok_pos[0], ok_pos[1]):
            time.sleep(0.3)
            logging.debug(f"{get_bot_prefix()}Screen 8 processed successfully")
    
    return True

def handle_screen_8():
    """
    Processa a Screen 8 (pop-up "New Battle Unlocked!" - pode ou não aparecer).
    Verificação cuidadosa APÓS Step 7 (Next) - é aqui que geralmente aparece.
    
    Fluxo:
    1. Aguarda um tempo inicial para o pop-up aparecer
    2. Verifica múltiplas vezes se o pop-up apareceu
    3. Se encontrar, clica no botão OK
    4. Continua verificando até ter certeza que não está mais presente
    5. Se não encontrar após verificações, assume que não apareceu
    
    Returns:
        bool: True sempre (não falha se não aparecer)
    """
    logging.info(f"{get_bot_prefix()}=== Checking Screen 8 (optional) ===")
    
    # Procura pelo botão "OK"
    ok_path = get_template_path("ok.png", SCREEN_8_DIR)
    
    if not os.path.exists(ok_path):
        logging.debug(f"Template ok.png not found at {ok_path}")
        logging.debug(f"{get_bot_prefix()}Screen 8 may not appear. Continuing...")
        return True
    
    # Wait initial time for popup to appear (may take a bit after transitions)
    time.sleep(0.5)  # Initial delay to give popup time to appear
    
    # Check multiple times to ensure we find the popup if it appears
    max_checks = 5
    found_and_closed = False
    
    for check_attempt in range(max_checks):
        screen = screenshot_bgr()
        if screen is None:
            logging.debug(f"{get_bot_prefix()}Attempt {check_attempt + 1}/{max_checks}: Could not capture screenshot")
            time.sleep(0.2)
            continue
        
        # Try to find OK button
        ok_pos = find_template(screen, ok_path, threshold=0.75, verbose=False)
        
        if ok_pos:
            logging.info(f"{get_bot_prefix()}Screen 8 appeared! OK button found at {ok_pos} (attempt {check_attempt + 1}/{max_checks})")
            logging.debug(f"{get_bot_prefix()}Clicking OK button...")
            if tap(ok_pos[0], ok_pos[1]):
                time.sleep(0.5)  # Wait for popup to close
                logging.info(f"{get_bot_prefix()}Screen 8 processed successfully")
                found_and_closed = True
                # Continue checking to ensure it really closed
                continue
            else:
                logging.warning(f"{get_bot_prefix()}Failed to click OK, retrying...")
                time.sleep(0.3)
                continue
        else:
            # Did not find popup in this attempt
            if found_and_closed:
                # Already found and closed previously - check once more to confirm it closed
                logging.debug(f"{get_bot_prefix()}Screen 8 already closed. Verifying one last time to confirm...")
                time.sleep(0.2)
                # If not found after closing, assume everything is fine
                break
            else:
                # Still not found - wait a bit before next attempt
                if check_attempt < max_checks - 1:
                    time.sleep(0.3)  # Wait between checks
                    continue
                else:
                    # Last attempt without finding - assume it didn't appear
                    logging.debug(f"{get_bot_prefix()}Screen 8 did not appear (popup not found after checks). Continuing normally...")
                    break
    
    return True

def check_reset_flag():
    """
    Verifica se existe um arquivo de flag para resetar expansões completas.
    Se existir, reseta e remove o arquivo.
    
    Returns:
        bool: True se reset foi executado, False caso contrário
    """
    reset_flag_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reset_expansions.flag")
    if os.path.exists(reset_flag_file):
        reset_completed_expansions()
        try:
            os.remove(reset_flag_file)
            logging.info("Reset flag file removed")
        except Exception as e:
            logging.warning(f"Error removing reset flag file: {e}")
        return True
    return False

# Global stop checker function (injected by BattleBot)
_check_stop_flag_func = None

def set_stop_checker(check_func):
    """Set the stop flag checker function."""
    global _check_stop_flag_func
    _check_stop_flag_func = check_func

def check_stop_flag():
    """Check if stop is requested."""
    if _check_stop_flag_func:
        return _check_stop_flag_func()
    return False

def run_battle_cycle():
    """
    Executa um ciclo completo de batalha.
    Detecta a tela atual e continua a partir dela até completar o ciclo.
    
    Returns:
        bool: True se ciclo completado com sucesso, False caso contrário
    """
    # Check stop flag at start
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested at start of battle cycle")
        return False
    
    # Verifica se precisa resetar expansões completas
    check_reset_flag()
    
    # Check stop flag after reset check
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested after reset check")
        return False
    
    # Detecta em qual tela estamos atualmente
    current_screen = detect_current_battle_screen()
    
    # Check stop flag after screen detection
    if check_stop_flag():
        logging.info(f"{get_bot_prefix()}Stop requested after screen detection")
        return False
    
    if current_screen == "select_expansion":
        # On expansion selection screen
        logging.info(f"{get_bot_prefix()}Continuing from expansion selection screen...")
        if check_stop_flag():
            return False
        if handle_expansion_selection():
            # Check stop flag after expansion selection
            if check_stop_flag():
                return False
            # Found hourglass in an expansion, continue with normal flow
            if not handle_battle_setup_screen():
                logging.error(f"{get_bot_prefix()}Failed to process battle setup screen")
                return False
            if check_stop_flag():
                return False
            if not wait_for_battle_completion(max_wait_time=None):
                logging.error(f"{get_bot_prefix()}Battle not completed")
                return False
            if check_stop_flag():
                return False
            
            # Detect if victory or defeat after battle
            current_screen_after_battle = detect_current_battle_screen(verbose=False)
            if current_screen_after_battle == "defeat_screen":
                # It's defeat - process defeat flow
                if not handle_defeat_screen():
                    logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                    return False
                # Check Screen 8 after defeat (may appear after Next)
                handle_screen_8()
                logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
                return True
            
            # It's victory - process victory flow
            if not handle_result_screen():
                logging.error(f"{get_bot_prefix()}Failed to process result screen")
                return False
            if not handle_screens_4_5_6():
                logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5, and 6")
                return False
            if not handle_screen_7():
                logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
                return False
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed!")
            return True
        else:
            logging.warning(f"{get_bot_prefix()}No hourglass found in any available expansion")
            return False
    
    if current_screen == "screen_8":
        # On optional popup
        logging.info(f"{get_bot_prefix()}Continuing from Screen 8 (popup)...")
        handle_screen_8()
        # After closing popup, detect again
        current_screen = detect_current_battle_screen()
    
    if current_screen == "defeat_popup":
        # On defeat popup
        logging.info(f"{get_bot_prefix()}Continuing from defeat popup...")
        if not handle_defeat_popup():
            logging.error(f"{get_bot_prefix()}Failed to process defeat popup")
            return False
        # After closing popup, detect again
        current_screen = detect_current_battle_screen()
    
    if current_screen == "defeat_screen":
        # On defeat screen
        logging.info(f"{get_bot_prefix()}Continuing from defeat screen...")
        if not handle_defeat_screen():
            logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
            return False
        # Check Screen 8 after defeat (may appear after Next)
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
        return True
    
    if current_screen == "screen_7":
        # Already on Screen 7
        logging.info(f"{get_bot_prefix()}Continuing from Screen 7...")
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()  # Check optional popup
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    if current_screen == "screens_4_5_6":
        # Already on Screens 4-5-6
        logging.info(f"{get_bot_prefix()}Continuing from Screens 4-5-6...")
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5, and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    if current_screen == "result_screen":
        # Already on result screen - check if defeat or victory
        # Re-detect to ensure it's not defeat
        current_screen_recheck = detect_current_battle_screen(verbose=False)
        if current_screen_recheck == "defeat_screen":
            # It's defeat
            logging.info(f"{get_bot_prefix()}Continuing from defeat screen...")
            if not handle_defeat_screen():
                logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                return False
            # Check Screen 8 after defeat (may appear after Next)
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
            return True
        
        # It's victory
        logging.info(f"{get_bot_prefix()}Continuing from result screen (victory)...")
        if not handle_result_screen():
            logging.error(f"{get_bot_prefix()}Failed to process result screen")
            return False
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5, and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    if current_screen == "battle_in_progress":
        # Já está em batalha
        logging.info(f"{get_bot_prefix()}Continuing from battle in progress...")
        if not wait_for_battle_completion(max_wait_time=None):
            logging.error(f"{get_bot_prefix()}Battle not completed")
            return False
        
        # Detecta se é vitória ou derrota após a batalha
        current_screen_after_battle = detect_current_battle_screen(verbose=False)
        if current_screen_after_battle == "defeat_screen":
            # É derrota - processa fluxo de derrota
            if not handle_defeat_screen():
                logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                return False
            # Verifica Screen 8 após derrota (pode aparecer após Next)
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
            return True
        
        # É vitória - processa fluxo de vitória
        if not handle_result_screen():
            logging.error(f"{get_bot_prefix()}Failed to process result screen")
            return False
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5 and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    if current_screen == "battle_setup":
        # Already on setup screen
        logging.info(f"{get_bot_prefix()}Continuing from battle setup screen...")
        if not handle_battle_setup_screen():
            logging.error(f"{get_bot_prefix()}Failed to process battle setup screen")
            return False
        if not wait_for_battle_completion(max_wait_time=None):
            logging.error(f"{get_bot_prefix()}Battle not completed")
            return False
        
        # Detect if victory or defeat after battle
        current_screen_after_battle = detect_current_battle_screen(verbose=False)
        if current_screen_after_battle == "defeat_screen":
            # It's defeat - process defeat flow
            if not handle_defeat_screen():
                logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                return False
            # Check Screen 8 after defeat (may appear after Next)
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
            return True
        
        # It's victory - process victory flow
        if not handle_result_screen():
            logging.error(f"{get_bot_prefix()}Failed to process result screen")
            return False
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5, and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    if current_screen == "battle_selection":
        # Está na tela de seleção de batalhas
        logging.info(f"{get_bot_prefix()}Continuing from battle selection screen...")
        if check_stop_flag():
            return False
        if not handle_battle_selection_screen():
            logging.error(f"{get_bot_prefix()}Failed to process battle selection screen")
            return False
        if check_stop_flag():
            return False
        if not handle_battle_setup_screen():
            logging.error(f"{get_bot_prefix()}Failed to process battle setup screen")
            return False
        if check_stop_flag():
            return False
        if not wait_for_battle_completion(max_wait_time=None):
            logging.error(f"{get_bot_prefix()}Battle not completed")
            return False
        if check_stop_flag():
            return False
        
        # Detecta se é vitória ou derrota após a batalha
        current_screen_after_battle = detect_current_battle_screen(verbose=False)
        if current_screen_after_battle == "defeat_screen":
            # É derrota - processa fluxo de derrota
            if not handle_defeat_screen():
                logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                return False
            # Verifica Screen 8 após derrota (pode aparecer após Next)
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
            return True
        
        # É vitória - processa fluxo de vitória
        if not handle_result_screen():
            logging.error(f"{get_bot_prefix()}Failed to process result screen")
            return False
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5 and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    # Screen not recognized - try starting from beginning
    if current_screen is None:
        logging.warning(f"{get_bot_prefix()}Screen not recognized. Trying to start from beginning...")
        # Check if hourglass template exists
        hourglass_path = get_template_path("hourglass.png", SCREEN_1_BATTLE_SELECTION_DIR)
        if not os.path.exists(hourglass_path):
            logging.error(f"Template hourglass.png not found at {hourglass_path}")
            logging.error("Please save hourglass.png in templates/battle/battle_selection/")
            return False
        
        if not handle_battle_selection_screen():
            logging.error(f"{get_bot_prefix()}Failed to process battle selection screen")
            return False
        if not handle_battle_setup_screen():
            logging.error(f"{get_bot_prefix()}Failed to process battle setup screen")
            return False
        if not wait_for_battle_completion(max_wait_time=None):
            logging.error(f"{get_bot_prefix()}Battle not completed")
            return False
        
        # Detect if victory or defeat after battle
        current_screen_after_battle = detect_current_battle_screen(verbose=False)
        if current_screen_after_battle == "defeat_screen":
            # It's defeat - process defeat flow
            if not handle_defeat_screen():
                logging.error(f"{get_bot_prefix()}Failed to process defeat screen")
                return False
            # Check Screen 8 after defeat (may appear after Next)
            handle_screen_8()
            logging.info(f"{get_bot_prefix()}Battle cycle completed (defeat)! Returning to battle selection...")
            return True
        
        # It's victory - process victory flow
        if not handle_result_screen():
            logging.error(f"{get_bot_prefix()}Failed to process result screen")
            return False
        if not handle_screens_4_5_6():
            logging.error(f"{get_bot_prefix()}Failed to process Screens 4, 5, and 6")
            return False
        if not handle_screen_7():
            logging.error(f"{get_bot_prefix()}Failed to process Screen 7")
            return False
        handle_screen_8()
        logging.info(f"{get_bot_prefix()}Battle cycle completed!")
        return True
    
    return False

def main():
    logging.info(f"=== STARTING BATTLE BOT (CONTINUOUS LOOP) ===")
    logging.info("Press Ctrl+C to stop the bot")
    
    # Check if template directory exists
    if not os.path.exists(TEMPLATE_DIR):
        logging.error(f"Template directory not found: {TEMPLATE_DIR}")
        logging.error(f"Please ensure templates for 'battle' exist")
        return
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            logging.info(f"\n{'='*60}")
            logging.info(f"=== CYCLE #{cycle_count} ===")
            logging.info(f"{'='*60}\n")
            
            success = run_battle_cycle()
            
            if success:
                logging.info(f"Cycle #{cycle_count} completed successfully")
            else:
                logging.warning(f"Cycle #{cycle_count} failed. Retrying...")
            
            # Small delay before next cycle
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        logging.info(f"\n{'='*60}")
        logging.info(f"=== BATTLE BOT INTERRUPTED BY USER ===")
        logging.info(f"Total cycles executed: {cycle_count}")
        logging.info(f"{'='*60}")
        print("\nBot interrupted by user (Ctrl+C)")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        logging.info(f"Total cycles executed before error: {cycle_count}")

if __name__ == "__main__":
    main()

