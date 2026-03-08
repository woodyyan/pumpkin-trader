#!/bin/bash

# =================================================================
# Pumpkin-Trader (南瓜交易系统) 一键安装部署脚本
# =================================================================

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}      🎃 欢迎使用 Pumpkin-Trader 一键部署工具     ${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# 安装目录 (默认在当前用户的 home 目录下)
INSTALL_DIR=${1:-$HOME/pumpkin-trader}

# 1. 检查 Docker 是否安装
check_docker() {
    echo -e "${BLUE}▶ 检查 Docker 环境...${NC}"
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: 未检测到 Docker。请先安装 Docker。${NC}"
        echo "参考: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        echo -e "${RED}错误: Docker 守护进程未启动。请启动 Docker 后重试。${NC}"
        exit 1
    fi
    echo -e "${GREEN}✔ Docker 环境正常${NC}"
}

# 2. 设置目录并获取代码
setup_and_fetch() {
    echo -e "${BLUE}▶ 准备部署目录: ${INSTALL_DIR}...${NC}"
    
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}目录已存在，准备更新代码...${NC}"
        cd "$INSTALL_DIR"
        
        # 检查是否为 git 仓库
        if [ -d ".git" ]; then
            git pull origin master || git pull origin main
        else
            echo -e "${RED}错误: 目录 $INSTALL_DIR 存在但不是 git 仓库。${NC}"
            echo "请选择一个新的安装路径。"
            exit 1
        fi
    else
        echo -e "${BLUE}正在克隆代码仓库...${NC}"
        #  Git 仓库地址
        git clone https://github.com/woodyyan/pumpkin-trader.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    echo -e "${GREEN}✔ 代码准备完成${NC}"
}

# 3. 构建 Docker 镜像
build_image() {
    echo -e "${BLUE}▶ 开始构建 Docker 镜像 (可能需要几分钟，请耐心等待)...${NC}"
    echo -e "${YELLOW}▶ 启用详细日志模式，这会输出每一步的构建详情和完整报错信息...${NC}"
    
    if DOCKER_BUILDKIT=1 docker build --progress=plain -t pumpkin-trader:latest .; then
        echo -e "${GREEN}✔ 镜像构建成功${NC}"
    else
        echo -e "${RED}=================================================${NC}"
        echo -e "${RED}错误: Docker 镜像构建失败！请查看上方的详细报错信息。${NC}"
        echo -e "${YELLOW}常见问题排查建议:${NC}"
        echo -e "  1. 网络问题: 检查服务器是否能正常访问外部网络，如下载 pip 依赖等"
        echo -e "  2. 权限问题: 确保当前用户有权限执行 docker 命令"
        echo -e "  3. 磁盘空间: 执行 'df -h' 检查磁盘空间是否充足"
        echo -e "${RED}=================================================${NC}"
        exit 1
    fi
}

# 4. 运行服务
start_services() {
    echo -e "${BLUE}▶ 启动服务...${NC}"
    
    # 检查 8501 端口是否被占用
    if lsof -i :8501 >/dev/null 2>&1 || netstat -an | grep -q ":8501 "; then
        echo -e "${YELLOW}警告: 端口 8501 被占用。尝试停止旧容器...${NC}"
        # 尝试停止并删除同名容器
        docker stop pumpkin-app >/dev/null 2>&1 || true
        docker rm pumpkin-app >/dev/null 2>&1 || true
    fi

    if docker run -d -p 8501:8501 --name pumpkin-app pumpkin-trader:latest; then
        echo -e "${GREEN}✔ 服务启动成功${NC}"
    else
        echo -e "${RED}错误: 服务启动失败。${NC}"
        exit 1
    fi
}

# 5. 获取服务器 IP
get_server_ip() {
    local ip
    
    # 尝试获取公网 IP
    ip=$(curl -s --connect-timeout 2 ifconfig.me || curl -s --connect-timeout 2 icanhazip.com)
    
    # 如果没有公网 IP，获取局域网 IP
    if [ -z "$ip" ]; then
        if command -v ip &> /dev/null; then
            ip=$(ip route get 1 | awk '{print $(NF-2);exit}')
        elif command -v ifconfig &> /dev/null; then
            ip=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
        fi
    fi
    
    # 最后回退到 localhost
    if [ -z "$ip" ]; then
        ip="localhost"
    fi
    
    echo "$ip"
}

# 6. 打印成功信息
print_success() {
    SERVER_IP=$(get_server_ip)
    
    echo ""
    echo -e "${GREEN}=================================================${NC}"
    echo -e "${GREEN}        🎉 Pumpkin-Trader 部署成功！ 🎉          ${NC}"
    echo -e "${GREEN}=================================================${NC}"
    echo ""
    echo -e "访问地址:"
    echo -e "▶ 局域网/公网访问: ${YELLOW}http://${SERVER_IP}:8501${NC}"
    echo -e "▶ 本机访问:        ${YELLOW}http://localhost:8501${NC}"
    echo ""
    echo -e "${BLUE}常用管理命令 (在 ${INSTALL_DIR} 目录下执行):${NC}"
    echo -e "▶ 查看运行日志:    ${YELLOW}docker logs -f pumpkin-app${NC}"
    echo -e "▶ 停止服务:        ${YELLOW}docker stop pumpkin-app${NC}"
    echo -e "▶ 重启服务:        ${YELLOW}docker restart pumpkin-app${NC}"
    echo -e "▶ 卸载清理:        ${YELLOW}docker rm -f pumpkin-app && docker rmi pumpkin-trader:latest${NC}"
    echo ""
    echo -e "${YELLOW}注意: 如果使用了云服务器，请确保防火墙/安全组已放行 8501 端口！${NC}"
}

# 执行主流程
main() {
    check_docker
    setup_and_fetch
    build_image
    start_services
    print_success
}

main
