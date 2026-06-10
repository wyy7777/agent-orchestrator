import React, { useState, useEffect } from "react";
import { Typography, Card, Button, Input, message, Space, Divider, List, Tag } from "antd";
import { useRouter } from "next/router";
import { ImportOutlined, LinkOutlined, FileTextOutlined, DownloadOutlined } from "@ant-design/icons";
import { workflowApi } from "@/lib/api";
import type { WorkflowItem } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function ImportWorkflowPage() {
  const router = useRouter();
  const { locale } = useI18n();
  const [shareCode, setShareCode] = useState("");
  const [yamlContent, setYamlContent] = useState("");
  const [importing, setImporting] = useState(false);
  const [templates, setTemplates] = useState<Array<{ name: string; description: string; yaml_definition: string }>>([]);

  // 从 URL 参数获取分享代码
  useEffect(() => {
    const code = router.query.code as string;
    if (code) {
      setShareCode(code);
    }
  }, [router.query]);

  // 加载模板列表
  useEffect(() => {
    workflowApi.templates().then(setTemplates).catch(() => {});
  }, []);

  // 从分享代码导入
  const handleImportShare = async () => {
    if (!shareCode.trim()) {
      message.warning(locale === "zh" ? "请输入分享代码" : "Please enter share code");
      return;
    }
    setImporting(true);
    try {
      const workflow = await workflowApi.importShare(shareCode);
      message.success(locale === "zh" ? "导入成功！" : "Imported successfully!");
      router.push(`/workflows/detail?id=${workflow.id}`);
    } catch (err) {
      message.error((err as Error).message || (locale === "zh" ? "导入失败" : "Import failed"));
    } finally {
      setImporting(false);
    }
  };

  // 从 YAML 导入
  const handleImportYaml = async () => {
    if (!yamlContent.trim()) {
      message.warning(locale === "zh" ? "请输入 YAML 内容" : "Please enter YAML content");
      return;
    }
    setImporting(true);
    try {
      // 解析 YAML 获取名称
      const lines = yamlContent.split("\n");
      let name = "导入的工作流";
      for (const line of lines) {
        if (line.startsWith("name:")) {
          name = line.replace("name:", "").trim();
          break;
        }
      }
      const workflow = await workflowApi.create({
        name,
        yaml_definition: yamlContent,
      });
      message.success(locale === "zh" ? "导入成功！" : "Imported successfully!");
      router.push(`/workflows/detail?id=${workflow.id}`);
    } catch (err) {
      message.error((err as Error).message || (locale === "zh" ? "导入失败" : "Import failed"));
    } finally {
      setImporting(false);
    }
  };

  // 从模板导入
  const handleImportTemplate = async (index: number) => {
    try {
      const workflow = await workflowApi.importTemplate(index);
      message.success(locale === "zh" ? "导入成功！" : "Imported successfully!");
      router.push(`/workflows/detail?id=${workflow.id}`);
    } catch (err) {
      message.error((err as Error).message || (locale === "zh" ? "导入失败" : "Import failed"));
    }
  };

  return (
    <div>
      <Title level={3}>
        <ImportOutlined /> {locale === "zh" ? "导入工作流" : "Import Workflow"}
      </Title>

      <Card title={locale === "zh" ? "从分享代码导入" : "Import from Share Code"} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary">
          {locale === "zh"
            ? "粘贴他人分享的工作流代码，一键导入到你的工作流列表。"
            : "Paste a shared workflow code to import it into your workflow list."}
        </Paragraph>
        <Input.Search
          placeholder={locale === "zh" ? "粘贴分享代码..." : "Paste share code..."}
          value={shareCode}
          onChange={(e) => setShareCode(e.target.value)}
          onSearch={handleImportShare}
          enterButton={locale === "zh" ? "导入" : "Import"}
          loading={importing}
          size="large"
        />
      </Card>

      <Card title={locale === "zh" ? "从 YAML 导入" : "Import from YAML"} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary">
          {locale === "zh"
            ? "直接粘贴 YAML 工作流定义内容。"
            : "Paste YAML workflow definition content directly."}
        </Paragraph>
        <TextArea
          rows={8}
          placeholder={locale === "zh" ? "粘贴 YAML 内容..." : "Paste YAML content..."}
          value={yamlContent}
          onChange={(e) => setYamlContent(e.target.value)}
          style={{ fontFamily: "monospace" }}
        />
        <Button
          type="primary"
          icon={<FileTextOutlined />}
          onClick={handleImportYaml}
          loading={importing}
          style={{ marginTop: 12 }}
        >
          {locale === "zh" ? "从 YAML 导入" : "Import from YAML"}
        </Button>
      </Card>

      <Card title={locale === "zh" ? "从模板库导入" : "Import from Template Library"}>
        <List
          dataSource={templates}
          renderItem={(tpl, index) => (
            <List.Item
              actions={[
                <Button
                  key="import"
                  type="link"
                  icon={<DownloadOutlined />}
                  onClick={() => handleImportTemplate(index)}
                >
                  {locale === "zh" ? "导入" : "Import"}
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={tpl.name}
                description={tpl.description}
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
