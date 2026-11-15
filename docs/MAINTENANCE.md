# AI 维护与故障排查手册

先读 `AGENTS.md`、`ROADMAP.md`、`docs/CONFIGURATION.md`，再读取当前用户的 `private/environment.json` 和 `private/records/`。只有公开仓库时无法维护别人的实例；根据当前用户的本地私有配置接手，不索取作者材料，也不让人把私钥贴入聊天。

## 接手与证据

先确定故障时间、设备与应用／内核版本、网络、所选配置、模式、具体错误、其他端是否同时失败。读取当前环境，不把旧记录当成实时状态。完成标准是知道哪台设备、哪条配置、哪种网络失败。

用户要求诊断时只读交付；要求修复时说明对象、影响、备份和恢复方式，按既有授权推进。公开项目的历史部署授权不代表当前用户已授权新收费资源、重装或凭据轮换。

服务 active、端口通、节点有延迟都不能替代实际 HTTPS、出口与路由证据。AI 实测、人工反馈、推断和未测项目分别记录。

## 1．本地条件与 SSH

从仓库根目录执行：

```sh
python3 scripts/project_config.py check
python3 scripts/export-node.py --local --check
python3 scripts/check-node.py
```

第一项仅检查配置结构。第二项只验证已有私有副本及可生成的 JSON 是否一致，不连接服务器、不写文件，不核对 URI 的提示文字，也不是对远端新状态的核验。第三项经固定主机身份 SSH 核对主机名、配置可读与语法、服务 active／enabled、监听、UFW 和权限。

检查脚本首错退出；输出不完整时按脚本内容逐项检查。期望 `ExecMainStatus=0`；`NRestarts` 要结合时间与日志，不单凭非零计数认定持续故障。配置指向了非本项目主机或指纹变化时停止核对，不能删除 known_hosts 或关闭严格检查。

缺少私有备份、SSH 权限、Mihomo 或工具网络访问能力时，先解决这一层；不要把沙箱权限错误当作用户服务器被封。只有当前用户环境、目标身份与依赖可确认时才进入下一层。

## 2．服务端补充证据

```sh
bash scripts/ssh-node.sh 'uptime; free -h; df -h /; timedatectl status'
```

根据现场配置检查 REALITY 目标 DNS、TCP 443、证书、TLS 和 HTTPS 可达性，不在手册抄写某位用户的域名或 IP。服务器能访问目标不等于 REALITY 握手兼容。只有有具体疑点才扩大到资源占用、两层防火墙或链路。

需要 journal 时只取故障窗口，先写敏感任务文件：

```sh
umask 077
mkdir -p .tmp/maintenance
bash scripts/ssh-node.sh 'journalctl -u xray --since "30 minutes ago" -n 200 --no-pager' > .tmp/maintenance/xray-journal.txt
```

该示例复用任务文件；若需保留前次证据，先另建带时间目录。工具不要直接回显完整日志。先脱敏，再汇报必要错误。没有访问明细日志不能证明没有请求，不自动长期打开访问日志。

## 3．独立节点、完整规则、实际客户端

```sh
python3 scripts/test-node.py
python3 scripts/test-clash-profile.py
python3 scripts/test-clash-profile.py --live
```

顺序运行，不能并发占用相同端口。独立节点通常使用回环 17890，完整规则使用 17891 和控制端口 17892；测试会生成私有文件和 `.tmp/` 产物，发送真实请求，结束后停止自己启动的进程，不修改系统代理、客户端选择或远端服务。端口占用时查明来源，不杀其他程序。

前两项从环境读取 Mihomo 路径，分流测试还从 `client.geodata_dir` 复制地理库。`--live` 另读取 `client.runtime_config`，当前依赖 Ruby safe YAML 解析和 `external-controller-unix`。它读取实际 mixed port／socket／secret，不输出 secret，也不会修改订阅；但仍生成本地候选文件并做语法检查。Windows 原生、无 Unix 控制接口或非此类客户端不适用该 live 测试。

| 结果 | 下一步 |
|---|---|
| 独立节点失败 | 对照凭据、内核版本、链路、监听和服务器日志 |
| 节点通过，profile 失败 | 核对规则、地理库和目标站点具体响应 |
| 隔离 profile 通过，live 失败 | 核对当前订阅、模式、覆盖脚本和运行内容；用户可能正常切到了其他订阅 |
| Mac 正常，手机失败 | 读取手机最终版本、配置、网络和 VPN 接管，不直接修改服务器 |
| 三端同时失败 | 优先核对共同节点和链路，但仍需证据定位 |

分流脚本通过控制接口读取连接链验证，而非仅看网页。站点策略和 HTTP 状态变化可能引发测试误报，应分清 TLS 连接、应用拒绝、出口和规则证据。DNS 隐私、系统全部流量、UDP 与长期稳定性没有被这些脚本全面覆盖。

## 常见故障

| 症状 | 证据与处理 |
|---|---|
| Google 出现 `dial DIRECT` | 检查最终规则、Rule／Direct 模式、是否误把节点片段独立导入；完整文件应有 proxies、proxy-groups 和 rules。卡片名称可能保留历史旧名，先看内容 |
| REALITY 认证或 TLS 失败 | 安全逐项核对 UUID、flow、SNI、公钥、short ID、时间与版本。该基线 Mihomo 配置需要 chrome 和 `support-x25519mlkem768: true`；不能给其他客户端照填同名字段 |
| 缺 GEOSITE／GeoIP 文件 | 当前 profile 的 `geodata-mode: false` 依赖 geosite.dat 和 Country.mmdb；按客户端可信方式补齐，不把规则临时改成全直连掩盖问题 |
| SSH／代理 TCP 超时 | 区分本地网络、实例状态、主机与云防火墙、服务监听；单次超时不能直接归因封锁 |
| SSH 正常，服务启动失败 | 查语法、运行用户读取权限、日志、磁盘；不重跑初装脚本 |
| 有延迟但访问失败 | 做真实 HTTPS、出口及接管检查；Android／iPhone 还要确认 VPN 授权及是否有另一个 VPN 占用 |
| 某站 HTTP 403／429 | 查账号／站点／出口策略，不直接认定代理故障；某些 API 根路径 HTTP 404 是正常已连接响应 |
| 国内外走错线路 | 查实际命中规则、顺序、地理库和覆盖设置，标准以模板为准 |
| 升级后一端失败 | 对照版本与官方发布记录，准备最小恢复；不要盲目降低安全要求、改指纹或降级服务器 |

参考：[Xray REALITY](https://xtls.github.io/config/transports/reality.html)、[Mihomo TLS](https://wiki.metacubex.one/config/proxies/tls/) 和 [已知兼容性讨论](https://github.com/XTLS/Xray-core/issues/7259) 。部署者须核对当时版本，链接不是永久兼容保证。

## 变更、备份和恢复

远端常用位置：程序 `/usr/local/bin/xray`，配置 `/usr/local/etc/xray/config.json`，单元 `/etc/systemd/system/xray.service`，初装资料 `/root/vultr-vpn-deployment/`。这些是安装布局，不是个人账号参数。远端配置权限应为 `640 root:xray`，目录 `750 root:xray`。

1. 保存本次实际配置、服务单元及相关 drop-in、文件权限／SHA256 和现场版本至私有备份。通过程序捕获内容写文件，不在工具输出中显示。升级还需备份当前可运行二进制，只有配置不能回滚程序。
2. 准备候选配置，按运行用户执行 Xray `run -test`；保持目录可遍历、文件可读。语法通过后才替换正式配置，按需要重启服务；改单元才需 daemon-reload。
3. 修改防火墙保留 SSH 与控制台恢复入口，通过新会话确认可登录。服务／机器重启会断连，按对应授权执行，不把它当作只读检查。
4. 变更后重新检查服务、独立连接及受影响的真实客户端。失败恢复本次变更前的配置／单元／二进制中实际变更部分，恢复权限后再次验收。

初装的 `config-before.json` 可能为空配置，恢复它不能恢复可用节点。远端部署目录与服务同机，需另行加密离线备份；不自动开通付费云备份。

`deploy-server.sh` 仅用于新机安装，已有 Xray 或初装目录会拒绝执行，不删除保护文件绕过。若 SSH 不可用，先区分本地材料、主机身份、实例停止或系统故障，必要时使用用户自己的官方控制台只读检查。重装、销毁、重建、停用服务或删除资源需要对应授权，且要说明数据和费用影响。

## 更新客户端与凭据

规则只在 `templates/clash-profile.yaml` 维护，再生成私有配置。Mac 客户端源配置、最终运行配置与项目副本可能不同；使用其配置索引动态定位本项目条目，不在教程固定 UID。运行 YAML 是生成物，只改它可能被覆盖；修改前备份，保留其他订阅和全局设置。

复杂第三方 YAML safe_load 失败时只安全提取需要的顶层规则和组，不使用不安全反序列化，也不输出完整订阅。

导出器读取运行配置和远端部署凭据文件并检查对应字段一致；手工轮换时必须同步维护凭据记录。公钥与私钥的密码学对应仍需实际握手验证，不能只依赖字符串核对。导出器先检查全部已有内容冲突，有差异即退出不写；写盘故障不保证整批原子性。先备份审查，不清空 `private/`。

三端各持配置副本，没有统一自动订阅更新。IP、凭据或规则变更后逐端更新和实际验收，Shadowrocket 路由需兼容的原生配置。轮换凭据可能同时中断各端，需要明确授权和分发计划。

## 日常维护与交接

按故障、升级或用户巡检请求做匹配风险的检查，关注资源、流量和实际账单。不自动设置定时任务、升级软件或停用 API Key。SSH 足够时无需 API Key；处理它前核对其他使用方及授权。

备份自己的环境配置、SSH 材料、凭据、实际配置、版本及需要的历史，使用加密离线存储。Git 忽略不是备份。将现场结果写入 `private/records/`，公共 ROADMAP 仅记录工具变更。

```text
时间与故障范围：
环境配置引用及现场版本：
根因／仍待确认的边界：
变更、备份与恢复办法：
服务端验证：
各客户端验证（AI 实测／用户反馈）：
未测项目与下一步：
```
