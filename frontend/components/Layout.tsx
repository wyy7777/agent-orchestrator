import React, { useState, useEffect } from "react";
import { Layout as AntLayout, Menu, Typography, theme, Button, Tooltip, Space, Badge, Drawer, message } from "antd";
import {
  DashboardOutlined,
  BranchesOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RocketOutlined,
  BulbOutlined,
  BulbFilled,
  ThunderboltOutlined,
  ApiOutlined,
  GlobalOutlined,
  BellOutlined,
  SettingOutlined,
  MenuOutlined,
  CloudServerOutlined,
  RobotOutlined,
  LinkOutlined,
  CloudDownloadOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { useI18n } from "@/lib/i18n";
import { dashboardApi } from "@/lib/api";
import { useUpdater } from "@/lib/useUpdater";
import UpdateDialog from "@/components/UpdateDialog";
import { settingsApi } from "@/lib/api";

const { Header, Sider, Content } = AntLayout;

interface AppLayoutProps {
  children: React.ReactNode;
  darkMode?: boolean;
  toggleDark?: () => void;
}

export default function AppLayout({ children, darkMode, toggleDark }: AppLayoutProps) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const updater = useUpdater();
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();
  const { locale, t, setLocale } = useI18n();

  // 检测是否为移动设备
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // 获取待审批数量
  useEffect(() => {
    const fetchPending = async () => {
      try {
        const stats = await dashboardApi.stats();
        setPendingCount(stats.pending_approvals);
      } catch {
        // 静默失败
      }
    };
    fetchPending();
    const interval = setInterval(fetchPending, 60000); // 每分钟刷新
    return () => clearInterval(interval);
  }, []);

  // 请求浏览器通知权限
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  // 全局键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K 快速搜索/跳转
      if (e.ctrlKey && e.key === "k") {
        e.preventDefault();
        // 可以打开搜索模态框
      }
      // Ctrl+/ 显示快捷键帮助
      if (e.ctrlKey && e.key === "/") {
        e.preventDefault();
        message.info("快捷键: Ctrl+K 搜索 | Ctrl+Shift+O 打开窗口");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // 自动弹出更新对话框（静默检查发现更新时）
  useEffect(() => {
    if (updater.updateAvailable && updater.update && !updateDialogOpen) {
      setUpdateDialogOpen(true);
    }
  }, [updater.updateAvailable, updater.update]);

  // 监听托盘菜单"检查更新"事件
  useEffect(() => {
    const handleTrayCheckUpdate = () => {
      updater.checkForUpdates().then(() => {
        setUpdateDialogOpen(true);
      });
    };
    window.addEventListener("tray-check-update", handleTrayCheckUpdate);
    return () => window.removeEventListener("tray-check-update", handleTrayCheckUpdate);
  }, [updater.checkForUpdates]);

  const menuItems = [
    { key: "/", icon: <DashboardOutlined />, label: t("nav.dashboard") },
    { key: "/workflows", icon: <BranchesOutlined />, label: t("nav.workflows") },
    { key: "/tasks", icon: <PlayCircleOutlined />, label: t("nav.tasks") },
    { key: "/approvals", icon: <CheckCircleOutlined />, label: t("nav.approvals") },
    { key: "/triggers", icon: <ThunderboltOutlined />, label: t("nav.triggers") },
    { key: "/plugins", icon: <ApiOutlined />, label: t("nav.plugins") },
    { key: "/sandboxes", icon: <CloudServerOutlined />, label: locale === "zh" ? "沙箱" : "Sandboxes" },
    { key: "/settings/agents", icon: <RobotOutlined />, label: locale === "zh" ? "Agent 管理" : "Agents" },
    { key: "/settings/api", icon: <KeyOutlined />, label: locale === "zh" ? "API 配置" : "API Config" },
    { key: "/settings/integrations", icon: <LinkOutlined />, label: locale === "zh" ? "集成" : "Integrations" },
    { key: "/settings/notifications", icon: <SettingOutlined />, label: t("nav.settings") },
  ];

  const toggleLocale = () => {
    setLocale(locale === "zh" ? "en" : "zh");
  };

  // 移动端侧边栏抽屉
  const sidebarContent = (
    <>
      <div
        style={{
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <RocketOutlined style={{ fontSize: 24, color: "#1677ff" }} />
        {(!collapsed || isMobile) && (
          <Typography.Title level={4} style={{ margin: 0, color: "#fff" }}>
            Agent Orchestrator
          </Typography.Title>
        )}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[router.pathname]}
        items={menuItems}
        onClick={({ key }) => {
          router.push(key);
          if (isMobile) setMobileMenuOpen(false);
        }}
      />
    </>
  );

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      {/* 移动端抽屉菜单 */}
      {isMobile ? (
        <Drawer
          placement="left"
          open={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          width={240}
          styles={{ body: { padding: 0, background: "#001529" } }}
        >
          {sidebarContent}
        </Drawer>
      ) : (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          trigger={null}
          theme="dark"
          style={{ background: "#001529" }}
        >
          {sidebarContent}
        </Sider>
      )}
      <AntLayout>
        <Header
          style={{
            padding: "0 24px",
            background: colorBgContainer,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(128,128,128,0.15)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center" }}>
            {isMobile ? (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setMobileMenuOpen(true)}
                style={{ fontSize: 18 }}
              />
            ) : (
              React.createElement(
                collapsed ? MenuUnfoldOutlined : MenuFoldOutlined,
                {
                  style: { fontSize: 18, cursor: "pointer" },
                  onClick: () => setCollapsed(!collapsed),
                }
              )
            )}
            <Typography.Title level={4} style={{ margin: "0 0 0 16px", fontSize: isMobile ? 16 : undefined }}>
              {menuItems.find((m) => m.key === router.pathname)?.label || "Agent Orchestrator"}
            </Typography.Title>
          </div>
          <Space>
            {/* 待审批通知铃铛 */}
            <Tooltip title={locale === "zh" ? "待审批" : "Pending Approvals"}>
              <Badge count={pendingCount} size="small">
                <Button
                  type="text"
                  icon={<BellOutlined />}
                  onClick={() => router.push("/approvals")}
                />
              </Badge>
            </Tooltip>
            {/* 检查更新 */}
            <Tooltip title={locale === "zh" ? "检查更新" : "Check for Updates"}>
              <Button
                type="text"
                icon={<CloudDownloadOutlined />}
                loading={checkingUpdate}
                onClick={async () => {
                  setCheckingUpdate(true);
                  try {
                    const result = await settingsApi.checkUpdate();
                    if (result.update_available) {
                      message.success(
                        locale === "zh"
                          ? `发现新版本 v${result.latest_version}（当前 v${result.current_version}）`
                          : `New version v${result.latest_version} available (current v${result.current_version})`
                      );
                      if (result.release_url) {
                        window.open(result.release_url, "_blank");
                      }
                    } else if (result.error) {
                      message.error(result.error);
                    } else {
                      message.success(
                        locale === "zh"
                          ? `已是最新版本 v${result.current_version}`
                          : `Already up to date v${result.current_version}`
                      );
                    }
                  } catch (err) {
                    message.error((err as Error).message || "检查更新失败");
                  } finally {
                    setCheckingUpdate(false);
                  }
                }}
              />
            </Tooltip>
            {/* 检查更新（仅桌面环境显示） */}
            {updater.isTauri && (
              <Tooltip title={updater.checking ? t("updater.checking") : t("updater.check")}>
                <Badge dot={updater.updateAvailable} offset={[-2, 2]}>
                  <Button
                    type="text"
                    icon={<CloudDownloadOutlined spin={updater.checking} />}
                    onClick={() => {
                      if (updater.updateAvailable) {
                        setUpdateDialogOpen(true);
                      } else {
                        updater.checkForUpdates().then(() => {
                          if (updater.updateAvailable) {
                            setUpdateDialogOpen(true);
                          } else if (!updater.error) {
                            message.success(t("updater.up_to_date"));
                          }
                        });
                      }
                    }}
                  />
                </Badge>
              </Tooltip>
            )}
            <Tooltip title={locale === "zh" ? "设置" : "Settings"}>
              <Button
                type="text"
                icon={<SettingOutlined />}
                onClick={() => router.push("/settings/notifications")}
              />
            </Tooltip>
            <Tooltip title={locale === "zh" ? "Switch to English" : "切换到中文"}>
              <Button
                type="text"
                icon={<GlobalOutlined />}
                onClick={toggleLocale}
              >
                {locale === "zh" ? "EN" : "中"}
              </Button>
            </Tooltip>
            {toggleDark && (
              <Tooltip title={darkMode ? t("common.light_mode") : t("common.dark_mode")}>
                <Button
                  type="text"
                  icon={darkMode ? <BulbFilled style={{ color: "#faad14" }} /> : <BulbOutlined />}
                  onClick={toggleDark}
                />
              </Tooltip>
            )}
          </Space>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
            minHeight: 280,
          }}
        >
          {children}
        </Content>
      </AntLayout>

      {/* 更新对话框 */}
      <UpdateDialog
        open={updateDialogOpen}
        onClose={() => setUpdateDialogOpen(false)}
        update={updater.update}
        downloading={updater.downloading}
        downloadProgress={updater.downloadProgress}
        onInstall={updater.installUpdate}
      />
    </AntLayout>
  );
}
