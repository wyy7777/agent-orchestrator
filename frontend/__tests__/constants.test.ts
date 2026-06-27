/**
 * Tests for constants module.
 */
import {
  statusColors,
  stepStatusColors,
  approvalStatusColors,
  stepTypeLabels,
  statusLabels,
} from "@/lib/constants";

describe("constants", () => {
  describe("statusColors", () => {
    it("maps each status to a color", () => {
      const statuses = ["pending", "running", "paused", "completed", "failed", "rolled_back"];
      for (const s of statuses) {
        expect(statusColors[s]).toBeDefined();
      }
    });

    it("pending status has default color", () => {
      expect(statusColors.pending).toBe("default");
    });

    it("running status has processing color", () => {
      expect(statusColors.running).toBe("processing");
    });

    it("completed status has success color", () => {
      expect(statusColors.completed).toBe("success");
    });

    it("failed status has error color", () => {
      expect(statusColors.failed).toBe("error");
    });

    it("paused status has warning color", () => {
      expect(statusColors.paused).toBe("warning");
    });
  });

  describe("stepStatusColors", () => {
    it("maps step statuses", () => {
      expect(stepStatusColors.pending).toBe("default");
      expect(stepStatusColors.running).toBe("processing");
      expect(stepStatusColors.waiting_approval).toBe("warning");
      expect(stepStatusColors.completed).toBe("success");
      expect(stepStatusColors.failed).toBe("error");
      expect(stepStatusColors.skipped).toBe("default");
    });
  });

  describe("approvalStatusColors", () => {
    it("maps approval statuses", () => {
      expect(approvalStatusColors.pending).toBe("warning");
      expect(approvalStatusColors.approved).toBe("success");
      expect(approvalStatusColors.rejected).toBe("error");
    });
  });

  describe("stepTypeLabels", () => {
    it("provides Chinese labels for step types", () => {
      expect(stepTypeLabels.analyze).toBe("分析");
      expect(stepTypeLabels.execute).toBe("执行");
      expect(stepTypeLabels.review).toBe("审查");
      expect(stepTypeLabels.approval).toBe("审批");
      expect(stepTypeLabels.merge).toBe("合并");
      expect(stepTypeLabels.script).toBe("脚本");
    });
  });

  describe("statusLabels", () => {
    it("provides Chinese labels for task statuses", () => {
      expect(statusLabels.pending).toBe("待执行");
      expect(statusLabels.running).toBe("运行中");
      expect(statusLabels.paused).toBe("已暂停");
      expect(statusLabels.completed).toBe("已完成");
      expect(statusLabels.failed).toBe("已失败");
      expect(statusLabels.rolled_back).toBe("已回滚");
    });
  });
});
