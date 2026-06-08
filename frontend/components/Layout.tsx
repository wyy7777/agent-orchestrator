import React, { useState } from "react";
import { Layout as AntLayout, Menu, Typography, theme } from "antd";
import {
  DashboardOutlined,
  BranchesOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { useRouter } from "next/router";

const { Header, Sider, Content } = AntLayout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "仪表盘" },
  { key: "/workflows", icon: <BranchesOutlined />, label: "工作流" },
  { key: "/tasks", icon: <PlayCircleOutlined />, label: "任务" },
  { key: "/approvals", icon: <CheckCircleOutlined />, label: "审批" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

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
              Agent 编排
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
            borderBottom: "1px solid #f0f0f0",
          }}
        >
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
