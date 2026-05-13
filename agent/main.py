"""
MAA Agent 入口

Agent 模式下 MaaFramework 通过子进程启动此脚本，
传入 identifier 用于 IPC 通信。脚本负责：
1. 初始化 MaaFramework 配置
2. import 所有自定义模块（触发 @AgentServer.custom_action/custom_recognition 装饰器注册）
3. 启动 Agent 服务并等待退出

PI v2.5.0: Client 启动子进程时会注入 PI_* 环境变量，
包括 PI_INTERFACE_VERSION、PI_CLIENT_*、PI_VERSION、PI_CONTROLLER、PI_RESOURCE 等。
"""

import ctypes
import ctypes.wintypes
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


class _Logger:
    def __init__(self, path):
        self.path = path
        self._file = None

    def write(self, msg):
        if self._file is None:
            self._file = open(self.path, "a", encoding="utf-8")
        self._file.write(msg)
        self._file.flush()

    def flush(self):
        if self._file:
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


class _TeeStream:
    def __init__(self, logger, original):
        self._logger = logger
        self._original = original

    def write(self, msg):
        self._logger.write(msg)
        if self._original:
            self._original.write(msg)
            self._original.flush()

    def flush(self):
        self._logger.flush()
        if self._original:
            self._original.flush()


def setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger = _Logger(log_file)
    return logger, log_file


def log_env_info(logger):
    logger.write(f"=== Agent started at {datetime.now().isoformat()} ===\n")
    logger.write(f"PID: {os.getpid()}\n")
    logger.write(f"CWD: {os.getcwd()}\n")
    logger.write(f"argv: {sys.argv}\n")
    logger.write(f"Python: {sys.executable} {sys.version}\n")

    pi_vars = {k: v for k, v in os.environ.items() if k.startswith("PI_")}
    if pi_vars:
        logger.write("PI environment variables:\n")
        for k, v in sorted(pi_vars.items()):
            logger.write(f"  {k}={v}\n")
    else:
        logger.write("No PI_ environment variables found.\n")

    path_env = os.environ.get("PATH", "")
    python_in_path = any("python" in p.lower() for p in path_env.split(os.pathsep))
    logger.write(f"Python in PATH: {python_in_path}\n")
    logger.write(f"Script location: {__file__}\n")
    logger.write(f"Script exists: {Path(__file__).exists()}\n")


def find_window_by_title(title_substring):
    user32 = ctypes.windll.user32
    results = []

    def enum_callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_substring in buf.value:
                    results.append((hwnd, buf.value))

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return results


def main():
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr
    logger, log_file = setup_logging()
    sys.stdout = _TeeStream(logger, _original_stdout)
    sys.stderr = _TeeStream(logger, _original_stderr)

    interception_ctrl = None

    try:
        log_env_info(logger)

        from maa.agent.agent_server import AgentServer

        if len(sys.argv) < 2:
            logger.write(f"ERROR: No identifier provided. Usage: python main.py <identifier>\n")
            logger.write(f"  sys.argv: {sys.argv}\n")
            logger.write("In v5.10.4+, the Client (MFAAvalonia) should pass the identifier as a CLI argument and inject PI_* env vars.\n")
            logger.close()
            sys.exit(1)

        identifier = sys.argv[-1]
        logger.write(f"Using identifier: {identifier}\n")

        try:
            from maa.toolkit import Toolkit
            Toolkit.init_option("./")
        except Exception as e:
            logger.write(f"WARNING: Toolkit.init_option failed (deprecated in AgentServer): {e}\n")
            logger.write("Continuing without init_option - this is expected in v5.10.4+.\n")

        import custom
        import custom.actions
        import custom.recognition

        logger.write("Custom modules imported successfully.\n")

        from custom.interception_controller import get_controller
        interception_ctrl = get_controller()

        try:
            interception_ctrl.initialize()
            logger.write("[Interception] Context initialized.\n")

            windows = find_window_by_title("洛克王国：世界")
            if windows:
                hwnd, title = windows[0]
                interception_ctrl.set_window_hwnd(hwnd)
                logger.write(f"[Interception] Found window: {title} (hwnd={hwnd})\n")
            else:
                logger.write("[Interception] Game window not found, using screen coordinates.\n")

            keyboard_ok = interception_ctrl.discover_keyboard_device(timeout_ms=10000)
            if not keyboard_ok:
                logger.write("[Interception] WARNING: Keyboard device not discovered.\n")

            mouse_ok = interception_ctrl.discover_mouse_device()
            if not mouse_ok:
                logger.write("[Interception] WARNING: Mouse device not discovered.\n")

            interception_ctrl.start_passthrough()
            logger.write("[Interception] Passthrough started.\n")

        except Exception as e:
            logger.write(f"[Interception] Initialization failed: {e}\n")
            logger.write(f"[Interception] {traceback.format_exc()}\n")
            logger.write("[Interception] Continuing without Interception input.\n")

        logger.write(f"Starting AgentServer with identifier: {identifier}\n")

        success = AgentServer.start_up(identifier)
        if not success:
            logger.write("FATAL: AgentServer.start_up returned False! Identifier may be invalid.\n")
            logger.close()
            sys.exit(1)

        logger.write("AgentServer started successfully. Waiting for tasks...\n")
        AgentServer.join()
        logger.write("AgentServer join completed.\n")
        AgentServer.shut_down()
        logger.write("AgentServer shut down. Exiting.\n")

    except Exception as e:
        logger.write(f"FATAL ERROR: {type(e).__name__}: {e}\n")
        logger.write(traceback.format_exc())
        logger.close()
        sys.exit(1)
    finally:
        if interception_ctrl is not None:
            try:
                interception_ctrl.shutdown()
                logger.write("[Interception] Cleaned up.\n")
            except Exception:
                pass
        logger.close()


if __name__ == "__main__":
    main()