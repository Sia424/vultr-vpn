# AI 从零部署教程

目标：为当前用户从零部署一套独立的 Xray + VLESS + Vision + REALITY 节点，交付可导入的配置、验证证据和维护记录。这不是迁移作者服务器的指南，不需要作者账号或私有资料。

先读 `AGENTS.md`、`ROADMAP.md` 和 `docs/CONFIGURATION.md`。下面命令均在仓库根目录执行；占位符必须换成当前用户的值。教程不代表已获得购买、部署、防火墙修改或重启授权。AI 能做的步骤在授权范围内执行；需要人协助时明确交代操作、输入、输出和完成标准。

## 0．确认范围和工具

AI 收集：目标用途、预算和用户所在网络、已有服务器／客户端、允许的变更、是否允许短时断连，以及本地工具环境。优先使用已有服务器和专用 API／CLI；不能访问界面时指导人操作，不索取账号密码或让用户把密钥贴入聊天。

本地要求 Python 3.9+、Bash、OpenSSH、curl；真实连接验证需要兼容 Mihomo，可使用已有客户端内核。当前自动安装器仅支持**全新 Ubuntu 24.04 LTS x86_64、root SSH**，不适用于 ARM、已有 Xray 或复杂生产主机。它会创建服务、安装必要包、写配置、启用自启并放行代理端口，不会自动购买资源。

完成标准：已明确用户授权、机器与客户端适用范围、工具及缺失条件；不把未验证的系统当作受支持。

## 1．初始化私有环境

```sh
python3 scripts/project_config.py init
```

此时占位值尚未填完，`check` 失败是预期行为。仅在用户授权生成 SSH 密钥且目标文件不存在时生成，交互式设置口令与否按用户使用方式选择。以下无口令示例用于 BatchMode 自动化，私钥应受权限和加密存储保护；有口令私钥需配置可用 ssh-agent，教程不自动启动或修改系统 agent：

```sh
ssh-keygen -t ed25519 -f private/credentials/ssh-ed25519 -N '' -C vpn-deployment
```

如果用户有可用私钥，直接填写路径，不覆盖。只把 `.pub` 公钥交给云平台；私钥保留本地。

完成标准：环境配置模板存在，用户的公钥可用，私钥未进入公共目录或对话。

## 2．人协助购买或提供服务器

已有机器时跳过购买，核对是否适合全新安装。需新购时，AI 根据用户预算与网络比较地区、规格、公网 IPv4、套餐流量、税费、超额费和附加项，查询当时官方价格及库存后形成具体方案；获得对应授权后才能创建。

若人操作 Vultr，AI 指导：

1. 人登录自己的控制台并完成支付／验证。
2. 选择适合用户网络的地区、预算内套餐、Ubuntu 24.04 LTS x64 和公网 IPv4，确认数量与附加项费用，不照搬旧教程价格。
3. 添加自己的 SSH 公钥，填写实例名称，核对预计费用后创建。
4. 等待启动，把公网 IPv4、安全登录方式和实例身份信息保存本地；不提供控制台密码或完整 API 响应。

AI 将 IP、SSH 用户／端口和密钥路径写入私有环境配置。API 是可选路径；若使用，只读取本地受限凭据，不记录 Token。创建请求超时先查是否已创建，不重复发送收费请求。

完成标准：唯一目标实例可识别、费用与范围获授权、可以进入控制台。官方入口：[实例部署与管理](https://docs.vultr.com/products/compute/instances/cloud-compute) 。

## 3．核验 SSH 主机身份

AI 通过 Vultr 可信控制台指导人运行：

```sh
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
hostname
```

人提供公钥指纹与主机名即可，不提供主机私钥。AI 在本地扫描候选主机公钥，写入任务临时文件，使用 `ssh-keygen -lf` 比对。以下 `SERVER_IPV4` 和 `SSH_PORT` 是说明占位符，不可原样执行：

```sh
mkdir -p .tmp/ssh-bootstrap
ssh-keyscan -T 10 -p SSH_PORT -t ed25519 SERVER_IPV4 > .tmp/ssh-bootstrap/candidate-known-hosts
ssh-keygen -lf .tmp/ssh-bootstrap/candidate-known-hosts -E sha256
```

扫描本身不证明身份。与控制台指纹完全一致、确认目标后，才保存到环境配置指定的 `server.known_hosts`，权限 `600`；已有文件先备份并核对，不能覆盖抹掉历史异常。填写 `server.expected_hostname` 为实际 `hostname`。

初始化未知主机时 `ssh-node.sh` 的严格检查失败属于预期，不能关闭检查来登录。然后通过 wrapper 只读检查：

```sh
bash scripts/ssh-node.sh 'hostname; cat /etc/os-release; uname -m; ss -lnt; command -v python3 curl ufw ss runuser sha256sum'
```

完成标准：指纹有可信核对来源，SSH 实际可登录，目标主机与支持的系统／架构一致，所选代理端口空闲。SSH 使用参考 [Vultr 官方说明](https://docs.vultr.com/products/compute/instances/cloud-compute/connection/openssh) 。

## 4．准备防火墙与本地验证工具

先确认主机没有需要保留的其他业务。检查 UFW、云防火墙是否启用；保持当前 SSH 会话和控制台恢复入口。当前安装器要求 UFW 已启用，避免在不知道原策略的情况下突然启用。

若为确认过的全新机器，用户已授权相关主机变更后，AI 安装缺少的必要依赖，先放行实际 SSH 端口，再启用 UFW；随后用新的 SSH 会话验证登录。下面是**远端操作模板**，端口必须取自环境配置：

```sh
ufw allow SSH_PORT/tcp
ufw enable
```

这个模板不是本地执行命令。SSH 登录失败先恢复维护通道，停止部署。若有云端防火墙，另放行实际 SSH 端口和代理 TCP 端口，按用户要求限制来源，保留其他已有规则。[云防火墙官方说明](https://docs.vultr.com/products/compute/instances/cloud-compute/networking/enable-firewall) 。

本地定位已安装的 Mihomo，运行其 `-v` 查看版本，填写 `client.mihomo_binary`。取得可信地理库并填写 `client.geodata_dir`；已有客户端可以复用其本地库，新用户不能依赖仓库中不存在的数据库。没有 Mihomo 时，先向用户说明所需客户端／内核与安装位置，按授权安装，不擅自装全局依赖。

填写其余环境字段；`client.runtime_config` 无适用桌面客户端时设 `null`：

```sh
python3 scripts/project_config.py check
```

完成标准：SSH 入口保持可用、UFW 状态符合要求、两层防火墙策略明确、本地验证依赖已定位；环境检查通过。

## 5．核对软件基线并生成安装材料

版本与安装器提交、SHA256 位于 `config/release.json`。这是固定复现基线，不承诺永远最新或没有漏洞。AI 部署前查询 [Xray 官方发行版](https://github.com/XTLS/Xray-core/releases) 和 [官方安装器](https://github.com/XTLS/Xray-install)，核对选定版本资产及校验值、系统支持和客户端兼容性；更换版本须同时更新校验信息并检查配置语法。

REALITY 目标由当前环境提供。安装器会从服务器检查目标的证书、TLS 1.3、h2 和 HTTPS 可达性；失败先查原因或另选经验证目标，不跳过检查。[REALITY 官方配置](https://xtls.github.io/config/transports/reality.html) 说明 SNI／目标等字段；SNI 不需要改成 Vultr 或服务器主机名。

```sh
python3 scripts/prepare-deployment.py
bash -n private/deployment-bundle.sh
```

该步骤只生成私有 bundle，不执行服务器变更。bundle 有差异时会拒绝覆盖，先保存旧材料再按授权更新。不要从聊天手写或复制包含凭据的 shell 命令。

完成标准：版本来源、SHA256、目标站点和授权范围明确，安装材料语法正确。

## 6．安装服务

AI 执行前向人说明具体影响：仅在已核验的目标主机安装 Xray，创建运行用户和配置、启用 systemd 服务、放行所选代理 TCP 端口，保留 SSH；安装器和防火墙原状态保存在 `/root/vultr-vpn-deployment/`。失败保留证据，不删除该目录绕过初装保护。确认已有对应授权后执行：

```sh
bash scripts/ssh-node.sh 'bash -s' < private/deployment-bundle.sh
python3 scripts/check-node.py
```

安装器会核对真实主机名、系统与架构、空闲端口、UFW 和既有部署；生成随机 UUID、REALITY 密钥和 short ID，凭据只写远端私有文件。服务配置以 `xray` 用户读取；本地无需运行长期 VPN 服务。

完成标准：语法测试成功、服务 active／enabled、正确端口监听、权限正确、SSH 可重新登录。安装失败不能把重跑初装或重新购买机器作为默认修复；进入维护流程。

## 7．导出并分发客户端配置

```sh
python3 scripts/export-node.py
```

导出从已固定身份的 SSH 捕获远端凭据及运行配置，检查二者一致后写入 `paths.artifacts_dir`，不会输出凭据。遇到任何已有内容差异，在写入前退出；先备份审查，不清空私有目录。写盘错误不保证整批原子性，应核对完整产物。

| 客户端 | 人与 AI 的操作 | 完成标准 |
|---|---|---|
| Mac Clash Verge／Android Clash Meta | 私密传输完整 `clash-profile.yaml`，导入、选中，Rule 模式在 `PROXY` 组选择新节点；手机允许 VPN 连接 | 原有订阅保留，实际连接使用新配置；该端具备对应地理库 |
| iPhone Shadowrocket | 仅复制 `node-url.txt` 中的 `vless://` 行导入，按实际版本核对 REALITY、Vision 和 TLS 指纹；路由用兼容的原生配置 | 能实际访问目标及核对出口；不能将 URI 当成已包含 Clash 规则 |

不要把 `clash-node.yaml` 节点片段独立导入，也不要导入带回环测试设置的 test profile。普通 URI 不保证携带 Mihomo 的 `support-x25519mlkem768`；本基线 Mihomo 配置包含该参数和 chrome 指纹。第三方客户端须核对实际能力，不能承诺换指纹或升级就一定可用。[Mihomo TLS 参数](https://wiki.metacubex.one/config/proxies/tls/) 。

AI 无法操作手机时，给人逐步操作说明，让人反馈去除凭据的错误或实际访问结果，不要求完整配置截图。

## 8．验收与交付

按顺序执行本地脚本，端口冲突时查原因，不杀用户进程：

```sh
python3 scripts/test-node.py
python3 scripts/test-clash-profile.py
```

有适用的桌面客户端和运行 YAML 时，再执行：

```sh
python3 scripts/test-clash-profile.py --live
```

独立节点测试验证真实 HTTPS、预期公网 IPv4 出口、第二站点、错误 UUID 拒绝及元数据阻断；分流测试验证国内域名／IP 直连、海外显式规则及兜底走节点。缺地理库、Ruby 或当前客户端规则不同，不一定是服务器故障，按维护手册分层定位。

分别让人验收每台实际设备的国内与海外访问、出口及应用接管。DNS、UDP／TUN 按需求专项验收，未测就写未测。另在明确授权及恢复准备下测试服务重启、整机重启后恢复，不能把 SSH 首次成功等同于重启恢复。

在 `private/records/` 保存带北京时间的部署记录：目标引用环境文件、现场版本、主机指纹核验来源、授权变更、备份和恢复办法、脚本与用户侧结果、未验收项。不要在公开 ROADMAP 写个人 IP 或实例状态。建议加密离线备份；远端恢复目录与服务同机，不能应对整机丢失。

交付入口为 `docs/MAINTENANCE.md` 和自己的私有记录。只有真实服务与所需客户端验收完成才能报告部署完成；缺少人协助或外部条件时准确报告阻塞，不虚构通过。
