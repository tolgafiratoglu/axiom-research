from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from axiom_research.identities import AgentId
from axiom_research.ledger import VerificationVerdict


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientAsk(Envelope):
    type: Literal["ask"] = "ask"
    question: str
    last_event_id: str | None = None


class ClientCancel(Envelope):
    type: Literal["cancel"] = "cancel"
    run_id: str | None = None


class Heartbeat(Envelope):
    type: Literal["heartbeat"] = "heartbeat"
    last_event_id: str | None = None


class ServerEvent(Envelope):
    event_id: str
    ts: datetime
    session_id: str
    run_id: str


class AgentStarted(ServerEvent):
    type: Literal["agent.started"] = "agent.started"
    agent_id: AgentId


class AgentHandoff(ServerEvent):
    type: Literal["agent.handoff"] = "agent.handoff"
    from_agent: AgentId
    to_agent: AgentId
    reason: str | None = None


class ToolSummary(ServerEvent):
    type: Literal["tool.summary"] = "tool.summary"
    agent_id: AgentId
    tool_name: str
    summary: str
    ok: bool = True


class EvidenceUpdated(ServerEvent):
    type: Literal["evidence.updated"] = "evidence.updated"
    evidence_id: str | None = None
    claim_id: str | None = None
    revision: int | None = None


class HypothesisCreated(ServerEvent):
    type: Literal["hypothesis.created"] = "hypothesis.created"
    hypothesis_id: str
    author_agent: AgentId


class A2AVerification(ServerEvent):
    type: Literal["a2a.verification"] = "a2a.verification"
    verification_id: str
    claim_id: str
    status: VerificationVerdict
    verified_revision: int | None = None


class VerificationGate(ServerEvent):
    type: Literal["verification.gate"] = "verification.gate"
    passed: bool
    detail: str | None = None


class AnswerFinal(ServerEvent):
    type: Literal["answer.final"] = "answer.final"
    conclusions: str
    citations: list[str] = Field(default_factory=list)
    disputed: list[str] = Field(default_factory=list)
    uncertainty: str | None = None


class RunFailed(ServerEvent):
    type: Literal["run.failed"] = "run.failed"
    reason: str


class ServerHeartbeat(ServerEvent):
    type: Literal["heartbeat"] = "heartbeat"
    last_event_id: str | None = None


ClientMessage = Annotated[
    ClientAsk | ClientCancel | Heartbeat,
    Field(discriminator="type"),
]

ServerMessage = Annotated[
    AgentStarted
    | AgentHandoff
    | ToolSummary
    | EvidenceUpdated
    | HypothesisCreated
    | A2AVerification
    | VerificationGate
    | AnswerFinal
    | RunFailed
    | ServerHeartbeat,
    Field(discriminator="type"),
]

CLIENT_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
SERVER_ADAPTER: TypeAdapter[ServerMessage] = TypeAdapter(ServerMessage)

SERVER_EVENT_TYPES = (
    "agent.started",
    "agent.handoff",
    "tool.summary",
    "evidence.updated",
    "hypothesis.created",
    "a2a.verification",
    "verification.gate",
    "answer.final",
    "run.failed",
)


def parse_client(data: object) -> ClientMessage:
    return CLIENT_ADAPTER.validate_python(data)


def parse_server(data: object) -> ServerMessage:
    return SERVER_ADAPTER.validate_python(data)
