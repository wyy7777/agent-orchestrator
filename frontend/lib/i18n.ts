/** 国际化配置。 */
import { createContext, useContext } from "react";

export type Locale = "zh" | "en";

export interface I18nContextType {
  locale: Locale;
  t: (key: string) => string;
  setLocale: (locale: Locale) => void;
}

export const I18nContext = createContext<I18nContextType>({
  locale: "zh",
  t: (key) => key,
  setLocale: () => {},
});

export function useI18n() {
  return useContext(I18nContext);
}

// 翻译字典
const translations: Record<Locale, Record<string, string>> = {
  zh: {
    // 通用
    "common.loading": "加载中...",
    "common.error": "错误",
    "common.success": "成功",
    "common.confirm": "确认",
    "common.cancel": "取消",
    "common.save": "保存",
    "common.delete": "删除",
    "common.edit": "编辑",
    "common.create": "创建",
    "common.search": "搜索",
    "common.reset": "重置",
    "common.refresh": "刷新",
    "common.export": "导出",
    "common.back": "返回",
    "common.submit": "提交",
    "common.close": "关闭",
    "common.yes": "是",
    "common.no": "否",
    "common.all": "全部",
    "common.none": "无",
    "common.dark_mode": "暗色模式",
    "common.light_mode": "亮色模式",

    // 导航
    "nav.dashboard": "仪表盘",
    "nav.workflows": "工作流",
    "nav.tasks": "任务",
    "nav.approvals": "审批",
    "nav.triggers": "触发器",
    "nav.plugins": "插件",
    "nav.settings": "设置",

    // 仪表盘
    "dashboard.title": "仪表盘",
    "dashboard.total_tasks": "总任务数",
    "dashboard.running_tasks": "运行中",
    "dashboard.success_rate": "成功率",
    "dashboard.total_tokens": "总 Token",
    "dashboard.recent_tasks": "最近任务",
    "dashboard.task_trend": "任务趋势",
    "dashboard.token_usage": "Token 消耗",
    "dashboard.top_workflows": "热门工作流",

    // 工作流
    "workflow.title": "工作流",
    "workflow.create": "创建工作流",
    "workflow.name": "名称",
    "workflow.description": "描述",
    "workflow.yaml_definition": "YAML 定义",
    "workflow.steps": "步骤",
    "workflow.status": "状态",
    "workflow.actions": "操作",
    "workflow.trigger": "立即执行",
    "workflow.edit": "编辑",
    "workflow.delete": "删除",
    "workflow.delete_confirm": "确定删除此工作流？",

    // 任务
    "task.title": "任务",
    "task.id": "任务 ID",
    "task.workflow": "工作流",
    "task.status": "状态",
    "task.token": "Token",
    "task.trigger_type": "触发方式",
    "task.created_at": "创建时间",
    "task.started_at": "开始时间",
    "task.completed_at": "完成时间",
    "task.error": "错误信息",
    "task.pr_url": "PR 链接",
    "task.retry": "重试",
    "task.rollback": "回滚",

    // 任务状态
    "task.status.pending": "等待中",
    "task.status.running": "运行中",
    "task.status.paused": "暂停",
    "task.status.completed": "已完成",
    "task.status.failed": "失败",
    "task.status.rolled_back": "已回滚",

    // 审批
    "approval.title": "审批",
    "approval.pending": "待审批",
    "approval.approved": "已批准",
    "approval.rejected": "已拒绝",
    "approval.approve": "批准",
    "approval.reject": "拒绝",

    // 触发器
    "trigger.title": "触发器",
    "trigger.webhook": "Webhook",
    "trigger.schedule": "定时任务",
    "trigger.create_webhook": "创建 Webhook",
    "trigger.create_schedule": "创建定时任务",
    "trigger.webhook_url": "Webhook URL",
    "trigger.cron_expr": "Cron 表达式",
    "trigger.enabled": "启用",

    // 插件
    "plugin.title": "插件",
    "plugin.name": "名称",
    "plugin.description": "描述",
    "plugin.config_schema": "配置 Schema",
    "plugin.test": "测试",

    // 通知
    "notification.title": "通知设置",
    "notification.slack": "Slack",
    "notification.dingtalk": "钉钉",
    "notification.webhook_url": "Webhook URL",
    "notification.test": "测试通知",
    "notification.on_complete": "任务完成时通知",
    "notification.on_fail": "任务失败时通知",
    "notification.on_approval": "需要审批时通知",

    // 搜索
    "search.keyword": "关键词搜索",
    "search.status": "状态筛选",
    "search.date_range": "日期范围",
    "search.sort_by": "排序方式",
    "search.sort_order": "排序方向",
    "search.created_at": "创建时间",
    "search.started_at": "开始时间",
    "search.tokens_used": "Token 消耗",
    "search.asc": "升序",
    "search.desc": "降序",

    // 欢迎
    "welcome.title": "欢迎使用 Agent Orchestrator",
    "welcome.desc": "AI Agent 工作流编排平台 — 让 AI 可靠、可控、可审计。",
    "welcome.quick_start": "快速开始",
    "welcome.import_demo": "一键导入示例工作流",
    "welcome.create_first": "创建第一个工作流",
    "welcome.auto_fix": "自动修 Bug",
    "welcome.code_review": "代码审查",
    "welcome.security_scan": "安全扫描",

    // 通知
    "notification.pending": "待审批",
    "notification.browser": "浏览器通知",
    "notification.request_permission": "开启通知",

    // 审计报告
    "audit.title": "审计报告",
    "audit.desc": "生成合规审计报告（EU AI Act），含 SHA-256 防篡改签名。",
    "audit.generate": "生成并下载",
    "audit.history": "历史报告",
    "audit.date_range": "日期范围",
    "audit.format": "格式",
    "audit.format_csv": "任务摘要 (CSV)",
    "audit.format_detailed": "步骤详情 (Detailed CSV)",
    "audit.sha256": "SHA-256 签名",
    "audit.size": "大小",
    "audit.no_reports": "暂无报告，选择日期范围并点击"生成并下载"",

    // 沙箱
    "sandbox.title": "沙箱",
    "sandbox.create": "创建沙箱",
    "sandbox.destroy": "销毁",
    "sandbox.execute": "执行命令",
    "sandbox.mode": "模式",
    "sandbox.local": "本地",
    "sandbox.docker": "Docker",
  },
  en: {
    // Common
    "common.loading": "Loading...",
    "common.error": "Error",
    "common.success": "Success",
    "common.confirm": "Confirm",
    "common.cancel": "Cancel",
    "common.save": "Save",
    "common.delete": "Delete",
    "common.edit": "Edit",
    "common.create": "Create",
    "common.search": "Search",
    "common.reset": "Reset",
    "common.refresh": "Refresh",
    "common.export": "Export",
    "common.back": "Back",
    "common.submit": "Submit",
    "common.close": "Close",
    "common.yes": "Yes",
    "common.no": "No",
    "common.all": "All",
    "common.none": "None",
    "common.dark_mode": "Dark Mode",
    "common.light_mode": "Light Mode",

    // Navigation
    "nav.dashboard": "Dashboard",
    "nav.workflows": "Workflows",
    "nav.tasks": "Tasks",
    "nav.approvals": "Approvals",
    "nav.triggers": "Triggers",
    "nav.plugins": "Plugins",
    "nav.settings": "Settings",

    // Dashboard
    "dashboard.title": "Dashboard",
    "dashboard.total_tasks": "Total Tasks",
    "dashboard.running_tasks": "Running",
    "dashboard.success_rate": "Success Rate",
    "dashboard.total_tokens": "Total Tokens",
    "dashboard.recent_tasks": "Recent Tasks",
    "dashboard.task_trend": "Task Trend",
    "dashboard.token_usage": "Token Usage",
    "dashboard.top_workflows": "Top Workflows",

    // Workflow
    "workflow.title": "Workflows",
    "workflow.create": "Create Workflow",
    "workflow.name": "Name",
    "workflow.description": "Description",
    "workflow.yaml_definition": "YAML Definition",
    "workflow.steps": "Steps",
    "workflow.status": "Status",
    "workflow.actions": "Actions",
    "workflow.trigger": "Run Now",
    "workflow.edit": "Edit",
    "workflow.delete": "Delete",
    "workflow.delete_confirm": "Are you sure to delete this workflow?",

    // Task
    "task.title": "Tasks",
    "task.id": "Task ID",
    "task.workflow": "Workflow",
    "task.status": "Status",
    "task.token": "Tokens",
    "task.trigger_type": "Trigger",
    "task.created_at": "Created",
    "task.started_at": "Started",
    "task.completed_at": "Completed",
    "task.error": "Error",
    "task.pr_url": "PR URL",
    "task.retry": "Retry",
    "task.rollback": "Rollback",

    // Task Status
    "task.status.pending": "Pending",
    "task.status.running": "Running",
    "task.status.paused": "Paused",
    "task.status.completed": "Completed",
    "task.status.failed": "Failed",
    "task.status.rolled_back": "Rolled Back",

    // Approval
    "approval.title": "Approvals",
    "approval.pending": "Pending",
    "approval.approved": "Approved",
    "approval.rejected": "Rejected",
    "approval.approve": "Approve",
    "approval.reject": "Reject",

    // Trigger
    "trigger.title": "Triggers",
    "trigger.webhook": "Webhook",
    "trigger.schedule": "Schedules",
    "trigger.create_webhook": "Create Webhook",
    "trigger.create_schedule": "Create Schedule",
    "trigger.webhook_url": "Webhook URL",
    "trigger.cron_expr": "Cron Expression",
    "trigger.enabled": "Enabled",

    // Plugin
    "plugin.title": "Plugins",
    "plugin.name": "Name",
    "plugin.description": "Description",
    "plugin.config_schema": "Config Schema",
    "plugin.test": "Test",

    // Notification
    "notification.title": "Notification Settings",
    "notification.slack": "Slack",
    "notification.dingtalk": "DingTalk",
    "notification.webhook_url": "Webhook URL",
    "notification.test": "Test Notification",
    "notification.on_complete": "Notify on task complete",
    "notification.on_fail": "Notify on task fail",
    "notification.on_approval": "Notify on approval needed",

    // Search
    "search.keyword": "Keyword Search",
    "search.status": "Status Filter",
    "search.date_range": "Date Range",
    "search.sort_by": "Sort By",
    "search.sort_order": "Sort Order",
    "search.created_at": "Created At",
    "search.started_at": "Started At",
    "search.tokens_used": "Tokens Used",
    "search.asc": "Ascending",
    "search.desc": "Descending",

    // Welcome
    "welcome.title": "Welcome to Agent Orchestrator",
    "welcome.desc": "AI Agent workflow orchestration platform — make AI reliable, controllable, and auditable.",
    "welcome.quick_start": "Quick Start",
    "welcome.import_demo": "Import Demo Workflow",
    "welcome.create_first": "Create First Workflow",
    "welcome.auto_fix": "Auto Fix Bugs",
    "welcome.code_review": "Code Review",
    "welcome.security_scan": "Security Scan",

    // Notification
    "notification.pending": "Pending",
    "notification.browser": "Browser Notification",
    "notification.request_permission": "Enable Notifications",

    // Audit Reports
    "audit.title": "Audit Reports",
    "audit.desc": "Generate compliance audit reports (EU AI Act) with SHA-256 tamper-proof signatures.",
    "audit.generate": "Generate & Download",
    "audit.history": "Report History",
    "audit.date_range": "Date Range",
    "audit.format": "Format",
    "audit.format_csv": "Task Summary (CSV)",
    "audit.format_detailed": "Step Details (Detailed CSV)",
    "audit.sha256": "SHA-256 Signature",
    "audit.size": "Size",
    "audit.no_reports": "No reports yet. Select a date range and click "Generate & Download"",

    // Sandbox
    "sandbox.title": "Sandboxes",
    "sandbox.create": "Create Sandbox",
    "sandbox.destroy": "Destroy",
    "sandbox.execute": "Run Command",
    "sandbox.mode": "Mode",
    "sandbox.local": "Local",
    "sandbox.docker": "Docker",
  },
};

export function t(locale: Locale, key: string): string {
  return translations[locale]?.[key] || key;
}
