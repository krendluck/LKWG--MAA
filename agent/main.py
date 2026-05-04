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

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    class Logger:
        def __init__(self, path):
            self.path = path
            self._file = None

        def write(self, msg):
            if self._file is None:
                self._file = open(self.path, "a", encoding="utf-8")
            self._file.write(msg)
            self._file.flush()

        def close(self):
            if self._file:
                self._file.close()
                self._file = None

    logger = Logger(log_file)
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


def main():
    logger, log_file = setup_logging()
    sys.stdout = logger
    sys.stderr = logger

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
        logger.close()


if __name__ == "__main__":
    main()