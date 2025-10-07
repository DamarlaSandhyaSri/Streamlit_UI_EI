from pydantic import BaseModel

class PageRecord(BaseModel):
    Title: str | None
    Source: str | None
    URL: str
    ReasonIdentified: str | None
    Concerns: str | None
    Description: str | None
    Data: str | None
    EmergingRiskName: str | None
    MiscTopics: str | None
    NAICSCODE: str | None
    NAICSDescription: str | None
    DateTime: str
    Tag: str | None