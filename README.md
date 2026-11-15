# vultr-vpn

一套写给 AI 工具执行的代理节点部署教程与维护工具，使用 **Xray-core + VLESS + Vision + REALITY**。AI 完成环境核对、配置生成和验收，在购买服务器、账号登录、授权等环节指导人协助。

这是应用代理节点方案；流量是否被接管取决于客户端模式、系统代理、VPN／TUN 和分流设置。支持生成 Mihomo 系客户端配置及 VLESS 节点链接，不保证所有客户端版本兼容。

## 从哪里开始

| 任务 | 入口 |
|---|---|
| 让 AI 从零部署一套独立节点 | [部署教程](docs/DEPLOY.md) |
| 填写自己的参数与定位私有文件 | [配置说明](docs/CONFIGURATION.md) |
| 已部署节点的日常维护、故障排查 | [维护手册](docs/MAINTENANCE.md) |
| 理解架构与工具分工 | [设计方案](DESIGN.md) |
| 提交或发布前检查 | [发布说明](docs/PUBLISHING.md) |
| AI 工作规范／项目进度 | [AGENTS.md](AGENTS.md)／[ROADMAP.md](ROADMAP.md) |

可以把下面这句话交给其他 AI：

> 请先读取 AGENTS.md、ROADMAP.md 和 docs/DEPLOY.md，按照教程帮我从零部署。先检查工具和条件，再指导我完成人工环节；不要使用示例占位值部署，不要输出凭据，最后分别验收服务端和实际客户端。

## 初始化与检查

在仓库根目录执行；本地需 Python 3.9+、Bash、OpenSSH、curl。真实连接测试还需可执行的 Mihomo 内核；`--live` 仅适用于提供 Unix 控制 socket 的客户端，当前解析运行 YAML 还需 Ruby。

```sh
python3 scripts/project_config.py init
```

初始化仅创建忽略目录和 `private/environment.json`，不购买资源、不连接服务器。按教程完成准备，填写示例中的占位值后检查：

```sh
python3 scripts/project_config.py check
python3 -m unittest discover -s tests -v
python3 scripts/check-public.py
```

`check` 只检查环境结构，不代表服务器或本地依赖已验证。当前安装器限定全新 Ubuntu 24.04 LTS x86_64、root SSH、已启用且保留 SSH 入口的 UFW；其他系统与架构先适配，不能直接执行。

## 部署后的验证入口

下列命令需当前用户已具备环境配置、凭据、生成产物和必要地理库，按顺序运行：

```sh
python3 scripts/check-node.py
python3 scripts/test-node.py
python3 scripts/test-clash-profile.py
python3 scripts/test-clash-profile.py --live
```

分别检查远端配置与服务、隔离节点连接与错误凭据、完整 profile 分流、实际客户端分流。最后一项依赖 `client.runtime_config`，不适用于直接在手机运行。测试会产生私有／临时文件、占用回环测试端口并发起实际请求，不更改系统代理、客户端订阅或远端服务。

## 配置与隐私

环境参数集中在 `private/environment.json`，密钥单独存放并由路径引用。新用户由公开示例生成自己的私有文件，无须作者的 IP、账号或任何私有资料。

完整客户端文件是环境配置中 `paths.artifacts_dir` 下的 `clash-profile.yaml`；`clash-node.yaml` 只有节点片段，不能独立导入。规则由模板统一管理：局域网直连，明确海外域名优先代理，国内域名／中国大陆 IP 直连，其余走节点；依赖该客户端的 `geosite.dat` 和 `Country.mmdb`。

`private/` 和 `.tmp/` 整体忽略，Git 忽略不等于加密或备份。发布工具同时扫描公共文件、暂存区和可达历史；实际环境、节点文件、凭据、原始日志及个人维护记录不上传。

## 许可证

[MIT](LICENSE)。依赖的软件和客户端分别遵循其上游许可证；本仓库不打包这些软件的二进制。
