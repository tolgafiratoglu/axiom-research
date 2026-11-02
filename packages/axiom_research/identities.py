from enum import StrEnum


class AgentId(StrEnum):
    PLANNER = "planner"
    INVESTIGATOR = "investigator"
    DATA_ANALYST = "data_analyst"
    CHALLENGER = "challenger"
    VERIFIER = "verifier"
    FINALIZER = "finalizer"
