# Live Teaching Platform

Use this reference when building a classroom assistant page that may host multiple teaching activities, especially activities with participant devices.

## Modes

- Static mode: a self-contained HTML page for teacher-operated demos, fallback classrooms, or offline review.
- Local multiplayer mode: a teacher computer runs `server.mjs`; the host screen and participant phones connect through the same LAN.

Use local multiplayer when the activity needs per-participant state, shared budgets, real-time rankings, locking, revealing, or exportable classroom decisions.

## Home Page and Identity

The live teaching platform should open as a classroom home page, not directly inside one activity, when multiple activities or games may be used in the same session.

Required home-page behavior:

- Host role shows a teacher dashboard with the student join URL, available application cards, classroom counts, and group rosters.
- Participant role first asks the learner to select a group.
- The server assigns each participant a stable in-group number by join order, starting from 1 for each group.
- Display participant identity as `第 N 组 · M号`.
- Store participant identity per browser tab or device session so two student tabs can simulate two devices without overwriting each other.
- Activity cards on the home page can link to built-in multiplayer activities or standalone mini-games.
- Built-in activities should use URLs such as `?role=player&app=golden-sample-auction` and `?role=host&app=golden-sample-auction`.

## Golden Sample Auction

Use the golden sample auction for evaluation-set construction, quality review prioritization, rubric negotiation, or deciding which cases deserve scarce review capacity.

Required mechanics:

- Each participant receives a fixed budget, default 100 virtual coins.
- Each participant must join through the platform home page and receive a group/member number before bidding.
- Show 8-10 candidate sample classes on the host screen and participant screen.
- Participants allocate coins across candidates. Total allocation must not exceed the budget.
- The host can start, lock, reveal, and reset the session.
- The host screen shows live totals, participant count, submitted count, bidders per candidate, and final top-N winners.
- Candidate cards must include title, scenario description, representative example, selection value, and risk if omitted.
- The activity must force tradeoffs; do not implement it as ordinary one-vote polling.

Default candidate classes:

- 高频用户问题
- 低频但高风险问题
- 领导汇报场景
- 投诉类 Badcase
- 边界表达 / 错别字 / 口语输入
- 多轮追问场景
- 权限 / 合规敏感问题
- 历史已修复问题
- 跨模块 / 跨部门协作场景
- 业务关键路径问题

## Deployment Conditions

For local multiplayer:

- The teacher computer and participant phones must be on the same Wi-Fi or LAN.
- Start the service with `node server.mjs --host=0.0.0.0 --port=8787`.
- Open the host screen at `http://localhost:8787?role=host`.
- Participants open `http://<teacher-lan-ip>:8787?role=player`.
- If phones cannot connect, check firewall rules, VPN isolation, guest Wi-Fi isolation, and whether the printed LAN IP is reachable.

## Validation

- Verify the host page loads and shows the join URL.
- Verify at least two simulated participants can join, allocate coins, and submit.
- Verify totals update on the host page without refresh.
- Verify lock prevents further participant submission.
- Verify reveal highlights top-N candidates.
- Verify reset clears participants and returns status to setup.
