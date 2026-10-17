# Testing policy

1. 在日常开发过程中，优先运行与当前修改直接相关的针对性测试（Targeted Tests）。
2. 只有当当前开发阶段趋于稳定，准备进行最终验收或版本冻结（Freeze）时，才运行完整的回归测试（Full Regression Tests）。
3. 对于仅涉及数据、地点映射、文档或其他非核心功能的修改，除非这些修改影响了核心业务行为，否则不需要重新运行全部历史回归测试。
4. 真实 API 调用测试（Live API Tests）通常只需在最终验收阶段执行一次。如果当前修改直接涉及相应的第三方服务或 API 集成，则应针对受影响的接口进行测试。
5. 应根据实际修改所涉及的模块和层级，合理扩大回归测试范围。不要默认每次代码修改后都重新运行所有历史测试。

# Git Version Control Rules

1. 每次完成一项相对独立的功能开发、Bug 修复或重构，并通过相关测试后，创建一个 Git Commit。
2. Commit 前运行 `git status` 和必要的 `git diff`，检查修改范围。
3. 只暂存本次任务相关的文件，避免直接使用 `git add .` 将无关修改一并提交。
4. 使用 Conventional Commits 风格：
   - `feat:` 新功能
   - `fix:` Bug 修复
   - `refactor:` 代码重构
   - `docs:` 文档修改
   - `chore:` 项目维护
   - `test:` 测试相关
5. Commit message 使用简短、明确的中文，描述本次改动。
6. 不允许提交 API Key、`.env`、缓存或其他敏感文件。
7. 测试失败时不得将改动标记为已完成；如需要保留未完成进度，应明确说明并等待确认。
8. 不得擅自执行 `git reset --hard`、`git clean -fd`、强制推送或删除分支。
9. 不得自动执行 `git push` 或合并至 `main`，除非用户明确要求。
10. 完成后汇报 Commit Hash、修改摘要、测试结果和剩余问题。
