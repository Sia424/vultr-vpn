# 环境配置说明

`config/environment.example.json` 是公共示例；`private/environment.json` 是当前用户环境唯一入口。脚本通过 `project_config.py` 读取，错误时不输出配置值。JSON 仅用 Python 标准库解析，无需 `.env`、PyYAML 或额外运行依赖。

## 初始化与路径规则

```sh
python3 scripts/project_config.py init
```

已有配置时退出且不覆盖。填写后运行 `python3 scripts/project_config.py check`；占位值、非公网 IPv4、相同 SSH／代理端口、无效端口和越出 `private/` 的产物目录会被拒绝。结构检查不测试连接，不保证 SSH 密钥、内核或地理库存在。

路径允许绝对路径、`~` 或相对仓库根目录的路径，不相对启动目录。`paths.artifacts_dir` 必须位于仓库 `private/` 内。私钥可引用用户已有的受限文件，不能复制进公开目录；不同 AI 环境的沙箱权限需要单独处理。

| 字段 | 作用 | 填写方式 |
|---|---|---|
| `server.host` | 目标服务器与预期 IPv4 出口 | 从用户控制台取得公网 IPv4；当前直出模型不适用于出口不同的 NAT／链式代理 |
| `server.expected_hostname` | 安装／检查的目标身份保护 | 通过已核验 SSH 读取 `hostname`，不使用控制台标签猜测 |
| `server.ssh_user` | SSH 用户 | 现有安装器要求 `root`；无 root 登录需先适配，不自动加 sudo |
| `server.ssh_port` | 已验证的 SSH 端口 | 不因示例值而修改服务器 SSH 配置 |
| `server.ssh_key` | SSH 私钥路径 | 示例位于 `private/credentials/`，不把私钥内容写进 JSON |
| `server.known_hosts` | 已核验的主机公钥文件 | 由可信控制台核验后建立，维护时严格匹配 |
| `reality.port` | Xray TCP 监听端口 | 必须空闲，与 SSH 端口不同，按需放行两层防火墙 |
| `reality.server_name` | REALITY SNI 与目标域名 | 示例不是可用性承诺；安装前从服务器检查 TLS 1.3、h2、证书与可达性；目标使用该域名的 TCP 443 |
| `client.node_name` | 生成配置中的节点名与测试预期链路 | 选择自己的名称，生成器同步填入代理组 |
| `client.mihomo_binary` | 本地可执行 Mihomo 内核 | 根据实际系统定位，不预设安装目录或自动全局安装 |
| `client.geodata_dir` | 分流测试需要的地理库目录 | 包含可信 `geosite.dat` 和 `Country.mmdb`；手机也需自己的库 |
| `client.runtime_config` | 本地客户端生成的运行 YAML | 可为 `null`；仅 `--live` 要求提供，当前还需 Ruby 和 Unix socket |
| `paths.artifacts_dir` | 凭据副本和客户端产物目录 | 新用户默认 `private/generated`；既有环境可引用原私有目录，无须移动已有文件 |

部署版本与软件校验值放在公共 `config/release.json`，它是可复现的软件基线，不是个人配置。更换版本必须一起核对官方发布资产、SHA256、安装器行为和客户端兼容性，不能只改版本号。

## 私有文件约定

| 目录／文件 | 生成或提供方 |
|---|---|
| `private/environment.json` | 初始化生成模板，AI 按用户实际情况填写 |
| `private/credentials/` | 用户提供或授权生成的 SSH／API 凭据；不要求 Vultr API Key |
| `private/deployment-bundle.sh` | `prepare-deployment.py` 生成，仅含环境与部署参数，执行它会改变远端 |
| `paths.artifacts_dir/node-credentials.json` | 导出时从服务器捕获，包含 UUID、REALITY 密钥和 short ID |
| `paths.artifacts_dir/xray-config.json` | 远端运行配置副本，含服务端私钥 |
| `paths.artifacts_dir/clash-profile.yaml` | 完整独立配置，包含节点、代理组和分流 |
| `paths.artifacts_dir/clash-node.yaml` | 合并到已有配置的片段，不能独立导入 |
| `paths.artifacts_dir/clash-test-profile.yaml` | 回环端口测试配置，不能当成日常配置 |
| `paths.artifacts_dir/node-url.txt` | 第一行提示，第二行 VLESS URI；链接不含完整分流规则 |
| `private/records/` | 用户实例的部署、版本、验收、人工反馈与维护记录 |
| `private/backups/` | 变更前备份、恢复所需二进制及配置；加密离线副本由用户另行保存 |
| `.tmp/<task-slug>/` | 测试与诊断临时文件，可重建，按敏感数据处理 |

既有用户可能仍使用其他私有子目录，先读环境配置和历史记录，不擅自搬动或删除。目录权限 `700`、敏感文件 `600`；远端 Xray 配置需要运行账户可读，使用 `640 root:xray`、目录 `750 root:xray`。

## 配置和记录不能混为一谈

稳定输入写环境配置。现场版本、部署时间、指纹核验来源、备份路径、异常及各端验收结果写 `private/records/`。运行时生成端口／socket 优先从 `client.runtime_config` 读取，不在文档中再抄一份。Git 忽略不防止聊天、截图或日志泄漏，公开前仍须扫描。
