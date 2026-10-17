# Phase 3A 人工 Live Acceptance

当前 **IMPLEMENTATION_COMPLETE**；以下人工验收尚未执行。自动化只跑 mock，不代表 DeepSeek live 已通过。此入口复用现有 DeepSeekLLMClient，真实调用可能收费；不把密钥写入文件、截图或提交。

## 环境和启动

在项目根目录打开 PowerShell，安全输入密钥到进程环境；可选模型保持已有provider默认。

```powershell
$taskApiKey = Read-Host 'DEEPSEEK_API_KEY' -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new('', $taskApiKey).Password
$env:PYTHONIOENCODING = 'utf-8'
python tools/demos/trip_agent_demo.py --live
```

确认 banner 为 LIVE DeepSeek。缺少密钥、超时、HTTP或schema错误必须明确显示，保持Trip不变，不回退mock。不要公开密钥或启用会输出密钥的shell日志。完成后可 `Remove-Item Env:DEEPSEEK_API_KEY`。不需要安装依赖。

## 必测真实输入

按顺序逐句输入，不加引号：

1. `I have three hours and want to explore architecture and local neighborhoods.`
2. 若初次提问，按显示问题回答；检查未创建Trip。接受路线后为PLANNED/ROUTE_READY。
3. `show original route`，确认原始地点名称和顺序。
4. `start`，进入ACTIVE_TRIP；再输`start`不得清空进度。
5. `I've finished this stop.`，显示完成地点、下一计划站点、remaining count/minutes。
6. `Skip this place.`，检查skip持久化；成功时显示v2及修改理由。失败时skip仍保存、偏好不提交。
7. `I'm a little tired, I only have one hour left, and I don't want to visit museums anymore.`，检查同一句预算/节奏/avoid仅一次重规划。成功才增加版本；若composition或must-go不可行，应明确失败、偏好不提交，不能强升角色或偷偷放宽边界。
8. 选择**当前实际zone**内、未visited/skipped、适合预算的production地点作为must-go，输入`I want to visit <显示的地点名称>.`。例如实际武康区可选择Wukang Mansion，西岸可选择West Bund Art Center；按显示路线和进度选择，不能照抄跨区点。若预算无法容纳，应明确infeasible，不新增版本。
9. `Why did you change my route?`，理由应对应实际已提交ReplanRecord。
10. `What changes have been made to my route?`，显示v1/v2/v3及每次路线、预算、原因。
11. `Show me my original route.`，与第3步一致。
12. 重复`I've finished this stop.`直到COMPLETED。显示visited/skipped、最终/原始路线、版本和预算总结。
13. `show history`、`show final route`、`summary`仍可读；`start`、`Skip this place.`和偏好变更被拒绝，不重开行程。

架构/街区输入当前真实route在60分钟约束下可能出现composition_gap，这是合法约束结果；不能据此声称完整成功链路已验收。需要另开进程做下面具有足够连续候选的完整链路。

## 完整 v1 → v2 → v3 链路

重新执行 `python tools/demos/trip_agent_demo.py --live`，初次输入：

```text
I have three hours and want architecture, industrial heritage and river views around West Bund.
start
I've finished this stop.
Skip this place.
I only have one hour left.
Why did you change my route?
What changes have been made to my route?
Show me my original route.
```

模型提取可能与mock不同，按实际澄清回答，检查硬约束；不得用fixture替换live生成。若三版本成功，继续complete到COMPLETED。另一次完整预算session在完成首站后输入`I want to visit West Bund Art Center.`，检查真实同区must-go。复合句也在独立充分预算session验证；不要把互相冲突的验收步骤塞进已结束的Trip。

## 澄清、放弃与结构化审计

新进程初句`I want to explore Shanghai.`，回答`Three hours, mainly architecture and local life.`。检查两个初次字段被原澄清层合并，Trip只在成功后创建。初次`cancel`回NEW，无Trip。另一个已开始session输入`I want to visit the old residence.`，若有多个选项，选显示名称或编号/B；不得要求手工POI ID。`cancel`只取消pending，Trip不变。输入`I'm done for today.`放弃，remaining不标visited/skipped，终态仍可读。

需检查完整字段时启动 `python tools/demos/trip_agent_demo.py --live --json`，JSON模式按行输出，不显示普通提示。检查同一次运行的session_id/trip_id不变；PLANNED→ACTIVE→COMPLETED；original_route不变；visited/skipped不回流；版本只有成功重规划增加；只读query不增加Trip事件/版本。provider异常后重新尝试不创建重复Trip；stale_state_conflict应提示基于最新路线重试。手工记录输入、输出和结果，密钥不入验收文件。

结论由人工填写：日期、provider/model、成功/失败步骤、实际zone、同一session/trip、版本、原路线和错误保护证据。只有真实验收通过后才能改为 **HUMAN_ACCEPTED / FROZEN**，再授权Phase3B。目前停在3A实现完成。
