## 3. 核心数据模型

### 3.1 Pydantic 模型定义

```python
# agent/core/models.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Action(BaseModel):
    """工具调用动作"""
    tool_name: str = Field(..., description="工具名称")
    tool_input: dict[str, Any] = Field(..., description="工具输入参数")
    
class Observation(BaseModel):
    """工具执行结果"""
    success: bool = Field(..., description="是否成功")
    result: Any = Field(None, description="工具返回结果")
    error: Optional[str] = Field(None, description="错误信息")
    latency_ms: float = Field(..., description="耗时 (毫秒)")

class Thought(BaseModel):
    """思考过程"""
    content: str = Field(..., description="思考内容")
    action: Optional[Action] = Field(None, description="决定的动作")
    is_final: bool = Field(False, description="是否是最终答案")
    final_answer: Optional[str] = Field(None, description="最终答案")

class TaskStep(BaseModel):
    """任务步骤"""
    step_id: str = Field(..., description="步骤 ID")
    thought: Thought = Field(..., description="思考")
    observation: Optional[Observation] = Field(None, description="观察结果")
    created_at: datetime = Field(default_factory=datetime.now)

class Task(BaseModel):
    """任务"""
    task_id: str = Field(..., description="任务 ID")
    session_id: str = Field(..., description="会话 ID")
    user_query: str = Field(..., description="用户查询")
    status: TaskStatus = Field(TaskStatus.CREATED, description="状态")
    steps: list[TaskStep] = Field(default_factory=list, description="步骤列表")
    final_result: Optional[str] = Field(None, description="最终结果")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class AgentState(BaseModel):
    """Agent 状态"""
    session_id: str
    current_task: Optional[Task] = None
    conversation_history: list[dict] = Field(default_factory=list)
    short_term_memory: list[str] = Field(default_factory=list)
```

---
