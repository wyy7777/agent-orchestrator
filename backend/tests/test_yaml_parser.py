import pytest
from app.engine.yaml_parser import parse_workflow_yaml, validate_workflow_yaml


class TestParseWorkflowYaml:
    def test_valid_workflow(self):
        yaml_str = """
name: 测试工作流
description: 一个测试
steps:
  - name: 分析
    type: analyze
    timeout: 120
    config:
      provider: deepseek
"""
        wf = parse_workflow_yaml(yaml_str)
        assert wf.name == "测试工作流"
        assert len(wf.steps) == 1
        assert wf.steps[0].name == "分析"
        assert wf.steps[0].type == "analyze"
        assert wf.steps[0].timeout == 120
        assert wf.steps[0].config["provider"] == "deepseek"

    def test_multiple_steps(self):
        yaml_str = """
name: 完整流程
steps:
  - name: 分析
    type: analyze
  - name: 审批
    type: approval
  - name: 执行
    type: execute
  - name: 审查
    type: review
  - name: 合并
    type: merge
"""
        wf = parse_workflow_yaml(yaml_str)
        assert len(wf.steps) == 5
        types = [s.type for s in wf.steps]
        assert types == ["analyze", "approval", "execute", "review", "merge"]

    def test_missing_name(self):
        yaml_str = """
steps:
  - name: 分析
    type: analyze
"""
        with pytest.raises(ValueError, match="name"):
            parse_workflow_yaml(yaml_str)

    def test_missing_steps(self):
        yaml_str = "name: 测试\n"
        with pytest.raises(ValueError, match="steps"):
            parse_workflow_yaml(yaml_str)

    def test_empty_steps(self):
        yaml_str = "name: 测试\nsteps: []\n"
        with pytest.raises(ValueError, match="至少有一个步骤"):
            parse_workflow_yaml(yaml_str)

    def test_invalid_step_type(self):
        yaml_str = """
name: 测试
steps:
  - name: 坏步骤
    type: invalid_type
"""
        with pytest.raises(ValueError, match="无效"):
            parse_workflow_yaml(yaml_str)

    def test_step_missing_type(self):
        yaml_str = """
name: 测试
steps:
  - name: 无类型步骤
"""
        with pytest.raises(ValueError, match="type"):
            parse_workflow_yaml(yaml_str)

    def test_invalid_yaml(self):
        with pytest.raises(ValueError, match="YAML"):
            parse_workflow_yaml("{{invalid")

    def test_not_dict(self):
        with pytest.raises(ValueError, match="字典"):
            parse_workflow_yaml("- item1\n- item2")

    def test_default_values(self):
        yaml_str = """
name: 默认值测试
steps:
  - name: 步骤1
    type: analyze
"""
        wf = parse_workflow_yaml(yaml_str)
        assert wf.description == ""
        assert wf.steps[0].timeout == 300
        assert wf.steps[0].config == {}
        assert wf.steps[0].prompt_template is None


class TestValidateWorkflowYaml:
    def test_valid(self):
        valid, err = validate_workflow_yaml("name: test\nsteps:\n  - name: s\n    type: analyze\n")
        assert valid is True
        assert err is None

    def test_invalid(self):
        valid, err = validate_workflow_yaml("name: test\n")
        assert valid is False
        assert "steps" in err
