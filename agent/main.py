"""
MAA Agent 入口

Agent 模式下 MaaFramework 通过子进程启动此脚本，
传入 socket_id 用于 IPC 通信。脚本负责：
1. 初始化 MaaFramework 配置
2. import 所有自定义模块（触发 @AgentServer.custom_action/custom_recognition 装饰器注册）
3. 启动 Agent 服务并等待退出
"""

import sys

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

# 导入自定义模块，注册所有 CustomAction 和 CustomRecognition
import custom

def main():
    # 初始化 MaaFramework 配置，使用当前目录下的配置文件
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)

    # socket_id 由 MaaFramework 主进程传入，用于建立 IPC 通道
    socket_id = sys.argv[-1]

    # 启动 Agent 服务，阻塞等待主进程指令
    AgentServer.start_up(socket_id)
    AgentServer.join()       # 阻塞主线程，等待任务执行
    AgentServer.shut_down()  # 清理资源


if __name__ == "__main__":
    main()