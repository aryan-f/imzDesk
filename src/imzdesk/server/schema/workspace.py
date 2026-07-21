from pydantic import BaseModel, Field


class Label(BaseModel):
    id: str
    name: str
    color: str


class WorkspaceSettings(BaseModel):
    labels: list[Label] = Field(default_factory=lambda: [
        Label(id='positive', name='Positive', color='#16a34a'),
        Label(id='negative', name='Negative', color='#dc2626'),
    ])
