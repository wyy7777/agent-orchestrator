import React, { useState, useEffect } from "react";
import { Modal, Steps, Button, Card, Typography, Space, message, Spin } from "antd";
import {
  RocketOutlined, PlayCircleOutlined, CheckCircleOutlined,
  BugOutlined, CodeOutlined, SafetyOutlined, FileTextOutlined, SearchOutlined,
} from "@ant-design/icons";
import { workflowApi } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

const TEMPLATE_ICONS = [BugOutlined, CodeOutlined, SafetyOutlined, FileTextOutlined, SearchOutlined];
const TEMPLATE_COLORS = ["#ff4d4f", "#1677ff", "#52c41a", "#722ed1", "#fa8c16"];

interface OnboardingWizardProps {
  open: boolean;
  onClose: () => void;
  onNavigate?: (path: string) => void;
}

export default function OnboardingWizard({ open, onClose, onNavigate }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [templates, setTemplates] = useState<Array<{ name: string; description: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState<number | null>(null);

  useEffect(() => {
    if (open && currentStep === 0) {
      setLoading(true);
      workflowApi.templates()
        .then((t) => setTemplates(t))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [open, currentStep]);

  const handleImport = async (index: number) => {
    setImporting(index);
    try {
      const wf = await workflowApi.importTemplate(index);
      message.success(`已导入工作流: ${wf.name}`);
      setCurrentStep(1);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setImporting(null);
    }
  };

  const handleSkip = () => {
    localStorage.setItem("onboarding_completed", "true");
    onClose();
  };

  const handleDone = () => {
    localStorage.setItem("onboarding_completed", "true");
    onClose();
    if (onNavigate) onNavigate("/tasks");
  };

  const steps = [
    {
      title: "选择模板",
      icon: <RocketOutlined />,
      content: (
        <div>
          <Paragraph type="secondary" style={{ marginBottom: 16 }}>
            选择一个预设工作流模板快速开始，或稍后自行创建工作流。
          </Paragraph>
          {loading ? (
            <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
              {templates.slice(0, 5).map((tpl, i) => {
                const Icon = TEMPLATE_ICONS[i] || BugOutlined;
                const color = TEMPLATE_COLORS[i] || "#1677ff";
                return (
                  <Card
                    key={i}
                    hoverable
                    size="small"
                    onClick={() => handleImport(i)}
                    style={{ borderColor: importing === i ? color : undefined }}
                  >
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      <Space>
                        <Icon style={{ color, fontSize: 20 }} />
                        <Text strong>{tpl.name}</Text>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {tpl.description?.substring(0, 60) || "预设工作流模板"}
                      </Text>
                      {importing === i && <Spin size="small" />}
                    </Space>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      ),
    },
    {
      title: "运行 Demo",
      icon: <PlayCircleOutlined />,
      content: (
        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <CheckCircleOutlined style={{ fontSize: 48, color: "#52c41a", marginBottom: 16 }} />
          <Title level={4}>工作流已导入！</Title>
          <Paragraph type="secondary">
            现在您可以创建任务并运行它。AI 将按照工作流定义的步骤自动执行。
          </Paragraph>
          <Paragraph type="secondary">
            在工作流详情页点击"立即执行"来启动第一个任务。
          </Paragraph>
        </div>
      ),
    },
    {
      title: "完成",
      icon: <CheckCircleOutlined />,
      content: (
        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <RocketOutlined style={{ fontSize: 48, color: "#1677ff", marginBottom: 16 }} />
          <Title level={4}>准备就绪！</Title>
          <Paragraph type="secondary">
            您已成功设置 Agent Orchestrator。以下是快速提示：
          </Paragraph>
          <div style={{ textAlign: "left", maxWidth: 400, margin: "0 auto" }}>
            <ul style={{ color: "var(--text-color-secondary, #666)" }}>
              <li>在 <strong>工作流</strong> 页面管理您的 AI 工作流</li>
              <li>在 <strong>任务</strong> 页面查看执行历史和结果</li>
              <li>在 <strong>审批</strong> 页面处理待审批的步骤</li>
              <li>在 <strong>触发器</strong> 页面设置 Webhook 或定时任务</li>
              <li>在 <strong>审计</strong> 页面生成合规报告</li>
            </ul>
          </div>
        </div>
      ),
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={handleSkip}
      footer={null}
      width={640}
      closable
      maskClosable={false}
      title={
        <Space>
          <RocketOutlined />
          <span>欢迎使用 Agent Orchestrator</span>
        </Space>
      }
    >
      <Steps
        current={currentStep}
        items={steps.map((s) => ({ title: s.title, icon: s.icon }))}
        style={{ marginBottom: 24 }}
        size="small"
      />
      <div style={{ minHeight: 200 }}>{steps[currentStep].content}</div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
        <Button onClick={handleSkip} type="text">
          跳过引导
        </Button>
        <Space>
          {currentStep > 0 && (
            <Button onClick={() => setCurrentStep((s) => s - 1)}>上一步</Button>
          )}
          {currentStep < steps.length - 1 ? (
            <Button
              type="primary"
              onClick={() => setCurrentStep((s) => s + 1)}
              disabled={currentStep === 0 && templates.length === 0}
            >
              {currentStep === 0 ? "跳过选择" : "下一步"}
            </Button>
          ) : (
            <Button type="primary" onClick={handleDone}>
              开始使用
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  );
}
