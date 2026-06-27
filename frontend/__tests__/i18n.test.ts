/**
 * Tests for i18n utility — highest-priority lib since all UI depends on it.
 */
import { t } from "@/lib/i18n";

describe("i18n translations", () => {
  describe("t() — look-up function", () => {
    it("returns Chinese text for zh locale", () => {
      expect(t("zh", "common.loading")).toBe("加载中...");
      expect(t("zh", "nav.dashboard")).toBe("仪表盘");
      expect(t("zh", "login.title")).toBe("Agent Orchestrator");
    });

    it("returns English text for en locale", () => {
      expect(t("en", "common.loading")).toBe("Loading...");
      expect(t("en", "nav.dashboard")).toBe("Dashboard");
      expect(t("en", "login.title")).toBe("Agent Orchestrator");
    });

    it("falls back to key when translation is missing", () => {
      expect(t("zh", "nonexistent.key")).toBe("nonexistent.key");
      expect(t("en", "missing.translation")).toBe("missing.translation");
    });

    it("falls back to key when locale is unknown", () => {
      // @ts-expect-error — testing runtime fallback for invalid locale
      expect(t("fr", "common.loading")).toBe("common.loading");
    });
  });

  describe("i18n key parity between zh and en", () => {
    it("has matching keys for all sections", () => {
      // We import the raw translations to compare keys
      // Using t() with known keys that exist in both
      const commonKeys = [
        "common.loading", "common.error", "common.success",
        "common.confirm", "common.cancel", "common.save",
        "common.delete", "common.edit", "common.create",
        "common.search", "common.reset", "common.refresh",
        "common.export", "common.back", "common.submit",
        "common.close", "common.yes", "common.no",
        "common.all", "common.none", "common.dark_mode",
        "common.light_mode",
      ];
      for (const key of commonKeys) {
        const zhVal = t("zh", key);
        const enVal = t("en", key);
        expect(zhVal).not.toBe(key); // should be translated
        expect(enVal).not.toBe(key); // should be translated
        expect(zhVal).toBeTruthy();
        expect(enVal).toBeTruthy();
      }
    });

    it("has navigation keys in both locales", () => {
      const navKeys = [
        "nav.dashboard", "nav.workflows", "nav.tasks",
        "nav.approvals", "nav.triggers", "nav.plugins", "nav.settings",
      ];
      for (const key of navKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has dashboard keys in both locales", () => {
      const dashKeys = [
        "dashboard.title", "dashboard.total_tasks", "dashboard.running_tasks",
        "dashboard.success_rate", "dashboard.total_tokens",
        "dashboard.recent_tasks", "dashboard.task_trend",
        "dashboard.token_usage", "dashboard.top_workflows",
      ];
      for (const key of dashKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has task status keys in both locales", () => {
      const taskStatusKeys = [
        "task.status.pending", "task.status.running", "task.status.paused",
        "task.status.completed", "task.status.failed", "task.status.rolled_back",
      ];
      for (const key of taskStatusKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has login keys in both locales", () => {
      const loginKeys = [
        "login.title", "login.subtitle", "login.skip", "login.login",
        "login.register", "login.username", "login.password",
        "login.email", "login.success", "login.init_success",
      ];
      for (const key of loginKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has audit report keys in both locales", () => {
      const auditKeys = [
        "audit.title", "audit.desc", "audit.generate", "audit.history",
        "audit.date_range", "audit.format", "audit.sha256", "audit.size",
        "audit.no_reports",
      ];
      for (const key of auditKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has updater keys in both locales", () => {
      const updaterKeys = [
        "updater.check", "updater.checking", "updater.up_to_date",
        "updater.new_version", "updater.current_version",
        "updater.downloading", "updater.install_now", "updater.later",
        "updater.error",
      ];
      for (const key of updaterKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });

    it("has API config keys in both locales", () => {
      const apiKeys = [
        "api.title", "api.default_model", "api.provider", "api.model",
        "api.key_management", "api.key_configured", "api.key_not_configured",
        "api.test", "api.edit", "api.set", "api.save", "api.cancel",
        "api.save_success", "api.save_failed", "api.test_success", "api.test_failed",
      ];
      for (const key of apiKeys) {
        expect(t("zh", key)).not.toBe(key);
        expect(t("en", key)).not.toBe(key);
      }
    });
  });
});
