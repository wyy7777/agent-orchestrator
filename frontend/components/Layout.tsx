import React, { useState } from "react";
import { Layout as AntLayout, Menu, Typography, theme, Button, Tooltip, Space } from "antd";
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
} from "@ant-design/icons";
import { useRouter } from "next/router";
import { useI18n } from "@/lib/i18n";

const { Header, Sider, Content } = AntLayout;

interface AppLayoutProps {
  children: React.ReactNode;
  darkMode?: boolean;
  toggleDark?: () => void;
}

export default function AppLayout({ children, darkMode, toggleDark }: AppLayoutProps) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();
  const { locale, t, setLocale } = useI18n();

  const menuItems = [
    { key: "/", icon: <DashboardOutlined />, label: t("nav.dashboard") },
    { key: "/workflows", icon: <BranchesOutlined />, label: t("nav.workflows") },
    { key: "/tasks", icon: <PlayCircleOutlined />, label: t("nav.tasks") },
    { key: "/approvals", icon: <CheckCircleOutlined />, label: t("nav.approvals") },
    { key: "/triggers", icon: <ThunderboltOutlined />, label: t("nav.triggers") },
    { key: "/plugins", icon: <ApiOutlined />, label: t("nav.plugins") },
  ];

  const toggleLocale = () => {
    setLocale(locale === "zh" ? "en" : "zh");
  };

  return (
    <AntLayout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        theme="dark"
        style={{ background: "#001529" }}
      >
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
          {!collapsed && (
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
          onClick={({ key }) => router.push(key)}
        />
      </Sider>
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
            {React.createElement(
              collapsed ? MenuUnfoldOutlined : MenuFoldOutlined,
              {
                style: { fontSize: 18, cursor: "pointer" },
                onClick: () => setCollapsed(!collapsed),
              }
            )}
            <Typography.Title level={4} style={{ margin: "0 0 0 16px" }}>
              {menuItems.find((m) => m.key === router.pathname)?.label || "Agent Orchestrator"}
            </Typography.Title>
          </div>
          <Space>
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
    </AntLayout>
  );
}
