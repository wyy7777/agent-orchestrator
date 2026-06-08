// 任务状态颜色映射
export const statusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  paused: "warning",
  completed: "success",
  failed: "error",
  rolled_back: "default",
};

// 步骤状态颜色
export const stepStatusColors: Record<string, string> = {
  pending: "default",
  running: "processing",
  waiting_approval: "warning",
  completed: "success",
  failed: "error",
  skipped: "default",
};

// 审批状态颜色
export const approvalStatusColors: Record<string, string> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
};

// 步骤类型中文名
export const stepTypeLabels: Record<string, string> = {
  analyze: "分析",
  execute: "执行",
  review: "审查",
  approval: "审批",
  merge: "合并",
  script: "脚本",
};

// 任务状态中文名
export const statusLabels: Record<string, string> = {
  pending: "待执行",
  running: "运行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "已失败",
  rolled_back: "已回滚",
};
